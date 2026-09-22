import logging
import os
import socket
import threading
import time
from collections.abc import Callable

from packages.database.config import resolve_database_url
from packages.database.jobs import (
    ClaimedJob,
    JobStateError,
    LeaseLostError,
    claim,
    fail,
    heartbeat,
    reap_expired,
    start,
    succeed,
)
from packages.database.session import session_factory

log = logging.getLogger(__name__)

#: Invoked after a job reaches terminal failure; receives the durable payload
#: context and the bounded failure reason. Never receives molecular data.
TerminalFailureHook = Callable[[str, dict, str], None]


class LeaseHeartbeat:
    """Renew a running job from a dedicated thread and independent DB sessions."""

    def __init__(self, factory, claimed: ClaimedJob, lease_seconds: int):
        self.factory = factory
        self.claimed = claimed
        self.lease_seconds = lease_seconds
        self._stop = threading.Event()
        self.lost = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name=f"heartbeat-{claimed.job_id}", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=max(1.0, self.lease_seconds))

    def _run(self) -> None:
        interval = max(0.1, self.lease_seconds / 3)
        while not self._stop.wait(interval):
            try:
                with self.factory.begin() as session:
                    heartbeat(
                        session,
                        self.claimed.job_id,
                        self.claimed.worker_id,
                        self.claimed.attempt_token,
                        self.lease_seconds,
                    )
            except (LeaseLostError, JobStateError):
                # A reclaimed or resolved job invalidates this attempt's lease.
                self.lost.set()
                return
            except Exception:
                log.exception("job_heartbeat_failed job_id=%s", self.claimed.job_id)


def run_worker(
    job_types: tuple[str, ...],
    handlers: dict[str, Callable[[ClaimedJob], dict]],
    *,
    terminal_failure_hooks: dict[str, TerminalFailureHook] | None = None,
) -> None:
    """Claim fenced jobs and dispatch them with an immutable execution context.

    Handlers receive the ``ClaimedJob`` context, never a live ORM job. Every
    mutating transition proves ``job_id + worker_id + attempt_token`` so a
    stale attempt cannot succeed, fail, or publish after lease loss.
    """
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s"
    )
    factory = session_factory(resolve_database_url())
    lease_seconds = int(os.getenv("CANCERJEV_JOB_LEASE_SECONDS", "60"))
    if lease_seconds < 1:
        raise ValueError("CANCERJEV_JOB_LEASE_SECONDS must be positive")
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    hooks = terminal_failure_hooks or {}
    while True:
        with factory.begin() as session:
            reaped = reap_expired(session)
        for job_id, job_type, payload in reaped:
            _notify_terminal_failure(hooks, job_type, job_id, payload, "RETRY_EXHAUSTED")
        with factory.begin() as session:
            claimed = claim(session, worker_id, job_types, lease_seconds)
        if claimed is None:
            time.sleep(1)
            continue
        try:
            with factory.begin() as session:
                start(session, claimed.job_id, worker_id, claimed.attempt_token)
            lease = LeaseHeartbeat(factory, claimed, lease_seconds)
            lease.start()
            try:
                result = handlers[claimed.job_type](claimed)
            finally:
                lease.stop()
            if lease.lost.is_set():
                raise LeaseLostError("job lease was lost while handler executed")
            with factory.begin() as session:
                succeed(session, claimed.job_id, worker_id, claimed.attempt_token, result)
        except LeaseLostError:
            # The stale attempt's result is dropped without publication.
            log.warning("job_lease_lost job_id=%s job_type=%s", claimed.job_id, claimed.job_type)
        except Exception as exc:
            reason = getattr(exc, "failure_reason", None)
            retryable = bool(getattr(exc, "retryable", False))
            if reason is None and not retryable:
                reason = "INTERNAL_ERROR"
            log.exception("job_failed job_id=%s job_type=%s", claimed.job_id, claimed.job_type)
            state = None
            try:
                with factory.begin() as session:
                    state = fail(
                        session,
                        claimed.job_id,
                        worker_id,
                        claimed.attempt_token,
                        str(exc),
                        retryable,
                        reason,
                    )
            except (LeaseLostError, JobStateError):
                log.warning(
                    "job_failure_not_recorded_after_lease_loss job_id=%s", claimed.job_id
                )
            if state == "failed":
                _notify_terminal_failure(
                    hooks, claimed.job_type, claimed.job_id, claimed.payload, reason
                )


def _notify_terminal_failure(
    hooks: dict[str, TerminalFailureHook],
    job_type: str,
    job_id,
    payload: dict,
    reason: str | None,
) -> None:
    hook = hooks.get(job_type)
    if hook is None:
        return
    reason = reason or "INTERNAL_ERROR"
    try:
        hook(str(job_id), dict(payload), reason)
    except Exception:
        log.exception("terminal_failure_hook_failed job_id=%s job_type=%s", job_id, job_type)
