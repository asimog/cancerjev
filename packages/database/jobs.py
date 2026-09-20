import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from packages.database.models import Job, JobAttempt


class JobStateError(RuntimeError):
    pass


class LeaseLostError(JobStateError):
    pass


class JobFencingError(JobStateError):
    pass


MAX_PAYLOAD_BYTES = 256 * 1024
MAX_RESULT_BYTES = 256 * 1024


def _check_payload_size(value: dict) -> None:
    import json
    if len(json.dumps(value, separators=(",", ":"))) > MAX_PAYLOAD_BYTES:
        raise ValueError(f"job payload exceeds {MAX_PAYLOAD_BYTES} bytes")


def _check_result_size(value: dict) -> None:
    import json
    if len(json.dumps(value, separators=(",", ":"))) > MAX_RESULT_BYTES:
        raise ValueError(f"job result exceeds {MAX_RESULT_BYTES} bytes")


def enqueue(session: Session, job_type: str, payload: dict, max_attempts: int = 3) -> Job:
    _check_payload_size(payload)
    job = Job(job_type=job_type, payload=payload, max_attempts=max_attempts)
    session.add(job)
    session.flush()
    return job


def claim(
    session: Session, worker_id: str, job_types: tuple[str, ...], lease_seconds: int = 60
) -> Job | None:
    """Atomically lease one queued/recoverable job using PostgreSQL SKIP LOCKED.

    Returns a Job with its attempt_token set for fencing.
    """
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
    job.state = "claimed"
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.attempt_count += 1
    attempt_token = str(uuid.uuid4())
    attempt = JobAttempt(
        job_id=job.job_id,
        attempt_number=job.attempt_count,
        worker_id=worker_id,
        attempt_token=attempt_token,
    )
    session.add(attempt)
    session.flush()
    # Store attempt_token on the returned job via a transient attribute
    job._attempt_token = attempt_token
    return job


def start(session: Session, job_id: uuid.UUID, worker_id: str) -> None:
    job = _owned(session, job_id, worker_id, allowed_states={"claimed"})
    job.state = "running"
    job.started_at = datetime.now(UTC)


def heartbeat(session: Session, job_id: uuid.UUID, worker_id: str, lease_seconds: int = 60) -> None:
    job = _owned(session, job_id, worker_id, allowed_states={"claimed", "running"})
    job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)


def succeed(session: Session, job_id: uuid.UUID, worker_id: str, result: dict) -> None:
    _check_result_size(result)
    job = _owned(session, job_id, worker_id, allowed_states={"running"})
    job.state, job.result, job.completed_at = "succeeded", result, datetime.now(UTC)
    job.lease_expires_at = None
    _finish_attempt(session, job, None)


def fail(session: Session, job_id: uuid.UUID, worker_id: str, error: str, retryable: bool) -> None:
    job = _owned(session, job_id, worker_id, allowed_states={"running"})
    error = error[:8000]
    job.error = error
    job.state = "queued" if retryable and job.attempt_count < job.max_attempts else "failed"
    job.completed_at = None if job.state == "queued" else datetime.now(UTC)
    job.lease_owner = None
    job.lease_expires_at = None
    _finish_attempt(session, job, error)


def _owned(session: Session, job_id: uuid.UUID, worker_id: str, *, allowed_states: set[str]) -> Job:
    job = session.scalar(select(Job).where(Job.job_id == job_id).with_for_update())
    now = datetime.now(UTC)
    if job is None or job.lease_owner != worker_id:
        raise LeaseLostError("job lease is not owned by worker")
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


def reaper(session: Session, max_lease_age_seconds: int = 300) -> list[str]:
    """Reap expired exhausted attempts and mark their jobs as failed."""
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=max_lease_age_seconds)
    expired = session.scalars(
        select(Job)
        .where(
            Job.state.in_(("claimed", "running")),
            Job.lease_expires_at < cutoff,
            Job.attempt_count >= Job.max_attempts,
        )
        .with_for_update(skip_locked=True)
    ).all()
    job_ids = []
    for job in expired:
        job.state = "failed"
        job.completed_at = now
        job.error = "reaper: all attempts exhausted and lease expired"
        job.lease_owner = None
        job.lease_expires_at = None
        _finish_attempt(session, job, job.error)
        job_ids.append(str(job.job_id))
    return job_ids
