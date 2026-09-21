import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from packages.database.models import Job, JobAttempt

#: Terminal/bounded failure reason codes shared by jobs, analyses, and audit records.
FAILURE_REASONS = frozenset(
    {
        "UNAVAILABLE_ACCESS",
        "INVALID_SCIENTIFIC_INPUT",
        "INTEGRITY_FAILURE",
        "UNSUPPORTED_ENGINE_OR_VERSION",
        "TRANSIENT_INFRASTRUCTURE",
        "RETRY_EXHAUSTED",
    }
)


class JobStateError(RuntimeError):
    pass


class LeaseLostError(JobStateError):
    pass


@dataclass(frozen=True)
class ClaimedJob:
    """Immutable execution context; no live ORM job crosses the claim transaction."""

    job_id: uuid.UUID
    job_type: str
    payload: dict
    worker_id: str
    attempt_token: str


def claim(
    session: Session, worker_id: str, job_types: tuple[str, ...], lease_seconds: int = 60
) -> ClaimedJob | None:
    """Atomically lease one queued/recoverable job using PostgreSQL SKIP LOCKED."""
    now = datetime.now(UTC)
    job = session.scalar(
        select(Job)
        .where(
            Job.job_type.in_(job_types),
            Job.attempt_count < Job.max_attempts,
            or_(
                Job.state == "queued",
                (Job.state.in_(("claimed", "running"))) & (Job.lease_expires_at < now),
            ),
        )
        .order_by(Job.created_at, Job.job_id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        return None
    if job.state in {"claimed", "running"}:
        _finish_attempt(session, job, "lease expired and job was reclaimed")
    token = secrets.token_hex(32)
    job.state = "claimed"
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.attempt_token = token
    job.attempt_count += 1
    session.add(
        JobAttempt(
            job_id=job.job_id,
            attempt_number=job.attempt_count,
            worker_id=worker_id,
            attempt_token=token,
        )
    )
    session.flush()
    return ClaimedJob(
        job_id=job.job_id,
        job_type=job.job_type,
        payload=dict(job.payload),
        worker_id=worker_id,
        attempt_token=token,
    )


def start(session: Session, job_id: uuid.UUID, worker_id: str, attempt_token: str) -> None:
    job = _owned(session, job_id, worker_id, attempt_token, allowed_states={"claimed"})
    job.state = "running"
    job.started_at = datetime.now(UTC)


def heartbeat(
    session: Session,
    job_id: uuid.UUID,
    worker_id: str,
    attempt_token: str,
    lease_seconds: int = 60,
) -> None:
    job = _owned(
        session, job_id, worker_id, attempt_token, allowed_states={"claimed", "running"}
    )
    job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)


def succeed(
    session: Session, job_id: uuid.UUID, worker_id: str, attempt_token: str, result: dict
) -> None:
    job = _owned(session, job_id, worker_id, attempt_token, allowed_states={"running"})
    job.state, job.result, job.completed_at = "succeeded", result, datetime.now(UTC)
    job.lease_expires_at = None
    _finish_attempt(session, job, None)


def fail(
    session: Session,
    job_id: uuid.UUID,
    worker_id: str,
    attempt_token: str,
    error: str,
    retryable: bool,
    reason: str | None = None,
) -> str:
    """Record an attempt outcome and return the resulting job state.

    ``LEASE_LOST`` never mutates job state and is therefore not a reason.
    """
    if reason is not None and reason not in FAILURE_REASONS:
        raise ValueError(f"unknown failure reason: {reason}")
    job = _owned(
        session, job_id, worker_id, attempt_token, allowed_states={"claimed", "running"}
    )
    exhausted = job.attempt_count >= job.max_attempts
    job.error = error[:8000]
    if retryable and not exhausted:
        job.state = "queued"
        job.failure_reason = None
    else:
        job.state = "failed"
        job.completed_at = datetime.now(UTC)
        # A retryable failure that exhausted its budget is retry-exhausted; a
        # permanent failure keeps its typed deterministic reason.
        job.failure_reason = "RETRY_EXHAUSTED" if retryable and exhausted else reason
    job.lease_owner = None
    job.lease_expires_at = None
    job.attempt_token = None
    _finish_attempt(session, job, error[:8000])
    return job.state


def verify_lease(
    session: Session, job_id: uuid.UUID, worker_id: str, attempt_token: str
) -> Job:
    """Lock and prove the current attempt inside a caller-owned transaction."""
    return _owned(
        session, job_id, worker_id, attempt_token, allowed_states={"claimed", "running"}
    )


def reap_expired(session: Session) -> list[tuple[uuid.UUID, str, dict]]:
    """Close dangling attempts and terminally fail exhausted expired jobs.

    Jobs below the attempt budget keep their expired lease so the normal
    claim-based reclaim path can reassign them; no requeue happens here.
    Returns ``(job_id, job_type, payload)`` for every terminally failed job.
    """
    now = datetime.now(UTC)
    jobs = list(
        session.scalars(
            select(Job)
            .where(
                Job.state.in_(("claimed", "running")),
                Job.lease_expires_at.is_not(None),
                Job.lease_expires_at < now,
            )
            .with_for_update(skip_locked=True)
        )
    )
    reaped: list[tuple[uuid.UUID, str, dict]] = []
    for job in jobs:
        _finish_attempt(session, job, "lease expired")
        if job.attempt_count >= job.max_attempts:
            job.state = "failed"
            job.completed_at = now
            job.error = "lease expired with exhausted attempt budget"
            job.failure_reason = "RETRY_EXHAUSTED"
            job.lease_owner = None
            job.lease_expires_at = None
            job.attempt_token = None
            reaped.append((job.job_id, job.job_type, dict(job.payload)))
    session.flush()
    return reaped


def _owned(
    session: Session,
    job_id: uuid.UUID,
    worker_id: str,
    attempt_token: str,
    *,
    allowed_states: set[str],
) -> Job:
    job = session.scalar(select(Job).where(Job.job_id == job_id).with_for_update())
    now = datetime.now(UTC)
    if job is None or job.lease_owner != worker_id:
        raise LeaseLostError("job lease is not owned by worker")
    if job.attempt_token is None or job.attempt_token != attempt_token:
        raise LeaseLostError("job lease is not owned by the current attempt")
    if job.lease_expires_at is None or job.lease_expires_at <= now:
        raise LeaseLostError("job lease has expired")
    if job.state not in allowed_states:
        raise JobStateError(f"invalid job transition from {job.state}")
    return job


def _finish_attempt(session: Session, job: Job, error: str | None) -> None:
    attempt = session.scalar(
        select(JobAttempt)
        .where(
            JobAttempt.job_id == job.job_id,
            JobAttempt.attempt_number == job.attempt_count,
            JobAttempt.completed_at.is_(None),
        )
        .order_by(JobAttempt.started_at.desc())
        .limit(1)
    )
    if attempt:
        attempt.completed_at, attempt.error = datetime.now(UTC), error
