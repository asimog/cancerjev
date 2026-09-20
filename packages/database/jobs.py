import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from packages.database.models import Job, JobAttempt


def enqueue(session: Session, job_type: str, payload: dict, max_attempts: int = 3) -> Job:
    job = Job(job_type=job_type, payload=payload, max_attempts=max_attempts)
    session.add(job)
    session.flush()
    return job


def claim(
    session: Session, worker_id: str, job_types: tuple[str, ...], lease_seconds: int = 60
) -> Job | None:
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
    job.state = "claimed"
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.attempt_count += 1
    session.add(
        JobAttempt(job_id=job.job_id, attempt_number=job.attempt_count, worker_id=worker_id)
    )
    session.flush()
    return job


def start(session: Session, job_id: uuid.UUID, worker_id: str) -> None:
    _owned(session, job_id, worker_id).state = "running"
    _owned(session, job_id, worker_id).started_at = datetime.now(UTC)


def heartbeat(session: Session, job_id: uuid.UUID, worker_id: str, lease_seconds: int = 60) -> None:
    job = _owned(session, job_id, worker_id)
    job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)


def succeed(session: Session, job_id: uuid.UUID, worker_id: str, result: dict) -> None:
    job = _owned(session, job_id, worker_id)
    job.state, job.result, job.completed_at = "succeeded", result, datetime.now(UTC)
    job.lease_expires_at = None
    _finish_attempt(session, job, None)


def fail(session: Session, job_id: uuid.UUID, worker_id: str, error: str, retryable: bool) -> None:
    job = _owned(session, job_id, worker_id)
    job.error = error[:8000]
    job.state = "queued" if retryable and job.attempt_count < job.max_attempts else "failed"
    job.completed_at = None if job.state == "queued" else datetime.now(UTC)
    job.lease_owner = None
    job.lease_expires_at = None
    _finish_attempt(session, job, error[:8000])


def _owned(session: Session, job_id: uuid.UUID, worker_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.lease_owner != worker_id:
        raise RuntimeError("job lease is not owned by worker")
    return job


def _finish_attempt(session: Session, job: Job, error: str | None) -> None:
    attempt = session.scalar(
        select(JobAttempt)
        .where(JobAttempt.job_id == job.job_id)
        .order_by(JobAttempt.started_at.desc())
        .limit(1)
    )
    if attempt:
        attempt.completed_at, attempt.error = datetime.now(UTC), error
