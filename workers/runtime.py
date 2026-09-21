"""Background worker runtime with lease management and attempt fencing."""

import logging
import os
import socket
import threading
import time
from collections.abc import Callable

from packages.database.config import resolve_database_url
from packages.database.jobs import LeaseLostError, claim, fail, heartbeat, reaper, start, succeed
from packages.database.session import session_factory

log = logging.getLogger(__name__)


class LeaseHeartbeat:
    """Renew a running job from a dedicated thread with attempt token."""

    def __init__(
        self,
        factory,
        job_id,
        worker_id: str,
        lease_seconds: int,
        attempt_token: str,
    ):
        self.factory = factory
        self.job_id = job_id
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.attempt_token = attempt_token
        self._stop = threading.Event()
        self.lost = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name=f"heartbeat-{job_id}", daemon=True
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
                        self.job_id,
                        self.worker_id,
                        self.lease_seconds,
                        attempt_token=self.attempt_token,
                    )
            except LeaseLostError:
                self.lost.set()
                return
            except Exception:
                log.exception("job_heartbeat_failed job_id=%s", self.job_id)


def run_worker(
    job_types: tuple[str, ...],
    handlers: dict[str, Callable[[dict], dict]],
) -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    factory = session_factory(resolve_database_url())
    lease_seconds = int(os.getenv("CANCERJEV_JOB_LEASE_SECONDS", "60"))
    if lease_seconds < 1:
        raise ValueError("CANCERJEV_JOB_LEASE_SECONDS must be positive")
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    _reaper_interval = int(os.getenv("CANCERJEV_REAPER_INTERVAL", "300"))
    _last_reap = 0.0
    while True:
        now = time.time()
        if now - _last_reap > _reaper_interval:
            try:
                with factory.begin() as session:
                    reaped = reaper(session)
                    if reaped:
                        log.warning("reaper terminalized jobs: %s", reaped)
            except Exception:
                log.exception("reaper run failed")
            _last_reap = now

        with factory.begin() as session:
            job = claim(session, worker_id, job_types, lease_seconds)
        if job is None:
            time.sleep(1)
            continue
        attempt_token = getattr(job, "_attempt_token", None)
        if not attempt_token:
            log.error("claimed job missing attempt_token job_id=%s", job.job_id)
            continue
        exec_context = {
            "worker_id": worker_id,
            "job_id": str(job.job_id),
            "attempt_token": attempt_token,
        }
        try:
            with factory.begin() as session:
                start(
                    session,
                    job.job_id,
                    worker_id,
                    attempt_token=attempt_token,
                )
            lease = LeaseHeartbeat(
                factory,
                job.job_id,
                worker_id,
                lease_seconds,
                attempt_token=attempt_token,
            )
            lease.start()
            try:
                result = handlers[job.job_type](
                    fencing(exec_context, job.payload)
                )
            finally:
                lease.stop()
            if lease.lost.is_set():
                raise LeaseLostError("job lease was lost while handler executed")
            with factory.begin() as session:
                succeed(
                    session,
                    job.job_id,
                    worker_id,
                    result,
                    attempt_token=attempt_token,
                )
        except LeaseLostError:
            log.warning(
                "job_lease_lost job_id=%s job_type=%s",
                job.job_id,
                job.job_type,
            )
        except Exception as exc:
            log.exception(
                "job_failed job_id=%s job_type=%s",
                job.job_id,
                job.job_type,
            )
            try:
                with factory.begin() as session:
                    fail(
                        session,
                        job.job_id,
                        worker_id,
                        str(exc),
                        bool(getattr(exc, "retryable", False)),
                        attempt_token=attempt_token,
                    )
            except LeaseLostError:
                log.warning(
                    "job_failure_not_recorded_after_lease_loss job_id=%s",
                    job.job_id,
                )


def fencing(context: dict, payload: dict) -> dict:
    """Merge execution context into payload so handlers can verify lease ownership."""
    return {"_fencing": context, **payload}
