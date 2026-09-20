import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from packages.database.jobs import (
    JobStateError,
    LeaseLostError,
    claim,
    fail,
    heartbeat,
    start,
    succeed,
)
from packages.database.models import Job, JobAttempt
from workers.runtime import LeaseHeartbeat


class FakeSession:
    def __init__(self, job: Job | None, attempt: JobAttempt | None = None):
        self.job = job
        self.attempt = attempt
        self.added = []

    def scalar(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        return self.attempt if entity is JobAttempt else self.job

    def add(self, value):
        self.added.append(value)

    def flush(self):
        pass


def make_job(state: str = "queued", *, expired: bool = False) -> Job:
    now = datetime.now(UTC)
    return Job(
        job_id=uuid.uuid4(),
        job_type="test",
        state=state,
        payload={},
        lease_owner=None if state == "queued" else "worker-1",
        lease_expires_at=(now - timedelta(seconds=1) if expired else now + timedelta(seconds=30)),
        attempt_count=0 if state == "queued" else 1,
        max_attempts=3,
    )


def test_claim_and_healthy_second_worker_rejection() -> None:
    job = make_job()
    session = FakeSession(job)
    assert claim(session, "worker-1", ("test",), lease_seconds=10) is job
    assert job.state == "claimed" and job.lease_owner == "worker-1" and job.attempt_count == 1
    assert isinstance(session.added[0], JobAttempt)
    # PostgreSQL's locked eligibility query returns no row while this lease is healthy.
    assert claim(FakeSession(None), "worker-2", ("test",), lease_seconds=10) is None


def test_heartbeat_renews_only_current_owner() -> None:
    job = make_job("running")
    before = job.lease_expires_at
    heartbeat(FakeSession(job), job.job_id, "worker-1", lease_seconds=60)
    assert job.lease_expires_at > before
    with pytest.raises(LeaseLostError):
        heartbeat(FakeSession(job), job.job_id, "worker-2")


def test_expired_job_is_recovered_and_attempt_is_audited() -> None:
    job = make_job("running", expired=True)
    attempt = JobAttempt(
        job_id=job.job_id, attempt_number=1, worker_id="worker-1", started_at=datetime.now(UTC)
    )
    session = FakeSession(job, attempt)
    claim(session, "worker-2", ("test",))
    assert job.state == "claimed" and job.lease_owner == "worker-2" and job.attempt_count == 2
    assert attempt.completed_at is not None and "reclaimed" in attempt.error


def test_completion_after_expiry_fails_safely() -> None:
    job = make_job("running", expired=True)
    with pytest.raises(LeaseLostError, match="expired"):
        succeed(FakeSession(job), job.job_id, "worker-1", {"ok": True})
    assert job.state == "running" and job.result is None


def test_retry_and_invalid_transitions() -> None:
    job = make_job("claimed")
    with pytest.raises(JobStateError):
        succeed(FakeSession(job), job.job_id, "worker-1", {})
    start(FakeSession(job), job.job_id, "worker-1")
    attempt = JobAttempt(
        job_id=job.job_id, attempt_number=1, worker_id="worker-1", started_at=datetime.now(UTC)
    )
    fail(FakeSession(job, attempt), job.job_id, "worker-1", "temporary", retryable=True)
    assert job.state == "queued" and job.lease_owner is None and attempt.error == "temporary"


def test_heartbeat_thread_stops(monkeypatch) -> None:
    calls = []

    @contextmanager
    def transaction():
        yield object()

    class Factory:
        begin = staticmethod(transaction)

    monkeypatch.setattr("workers.runtime.heartbeat", lambda *args: calls.append(args))
    lease = LeaseHeartbeat(Factory(), uuid.uuid4(), "worker-1", 1)
    lease.start()
    time.sleep(0.4)
    lease.stop()
    count = len(calls)
    time.sleep(0.4)
    assert count >= 1 and len(calls) == count
