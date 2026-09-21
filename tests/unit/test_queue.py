import time
import uuid
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from packages.database.jobs import (
    FAILURE_REASONS,
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


def make_job(state: str = "queued", *, expired: bool = False, attempts: int | None = None) -> Job:
    now = datetime.now(UTC)
    count = 0 if state == "queued" else 1
    return Job(
        job_id=uuid.uuid4(),
        job_type="test",
        state=state,
        payload={},
        lease_owner=None if state == "queued" else "worker-1",
        lease_expires_at=now - timedelta(seconds=1) if expired else now + timedelta(seconds=30),
        attempt_token=None if state == "queued" else "t" * 64,
        attempt_count=attempts if attempts is not None else count,
        max_attempts=3,
    )


def test_claim_returns_immutable_fenced_context() -> None:
    job = make_job()
    session = FakeSession(job)
    claimed = claim(session, "worker-1", ("test",), lease_seconds=10)
    assert isinstance(claimed, ClaimedJob)
    assert claimed.job_id == job.job_id and claimed.worker_id == "worker-1"
    assert claimed.attempt_token and len(claimed.attempt_token) == 64
    assert job.attempt_token == claimed.attempt_token
    assert job.state == "claimed" and job.attempt_count == 1
    assert isinstance(session.added[0], JobAttempt)
    assert session.added[0].attempt_token == claimed.attempt_token
    with pytest.raises(FrozenInstanceError):
        claimed.worker_id = "worker-2"


def test_heartbeat_and_transitions_require_the_current_attempt_token() -> None:
    job = make_job("running")
    before = job.lease_expires_at
    heartbeat(FakeSession(job), job.job_id, "worker-1", "t" * 64, lease_seconds=60)
    assert job.lease_expires_at > before
    for stale in ("", "x" * 64, None):
        with pytest.raises(LeaseLostError, match="attempt"):
            heartbeat(FakeSession(job), job.job_id, "worker-1", stale)
    with pytest.raises(LeaseLostError):
        heartbeat(FakeSession(job), job.job_id, "worker-2", "t" * 64)
    with pytest.raises(LeaseLostError, match="attempt"):
        succeed(FakeSession(job), job.job_id, "worker-1", "wrong" * 16, {"ok": True})
    assert job.state == "running" and job.result is None


def test_expired_job_is_recovered_with_a_new_token() -> None:
    job = make_job("running", expired=True)
    attempt = JobAttempt(
        job_id=job.job_id, attempt_number=1, worker_id="worker-1", started_at=datetime.now(UTC)
    )
    session = FakeSession(job, attempt)
    claimed = claim(session, "worker-2", ("test",))
    assert job.state == "claimed" and job.lease_owner == "worker-2" and job.attempt_count == 2
    assert job.attempt_token == claimed.attempt_token != "t" * 64
    assert attempt.completed_at is not None and "reclaimed" in attempt.error


def test_stale_attempt_cannot_complete_after_reclaim() -> None:
    job = make_job("running")
    old_token = "t" * 64
    # The same worker process reclaimed the job and now holds a new attempt token.
    job.attempt_token = "n" * 64
    with pytest.raises(LeaseLostError, match="attempt"):
        succeed(FakeSession(job), job.job_id, "worker-1", old_token, {"ok": True})
    with pytest.raises(LeaseLostError, match="attempt"):
        fail(FakeSession(job), job.job_id, "worker-1", old_token, "late", False)
    assert job.state == "running" and job.result is None and job.error is None


def test_completion_after_expiry_fails_safely() -> None:
    job = make_job("running", expired=True)
    with pytest.raises(LeaseLostError, match="expired"):
        succeed(FakeSession(job), job.job_id, "worker-1", "t" * 64, {"ok": True})
    assert job.state == "running" and job.result is None


def test_fail_from_claimed_and_reason_validation() -> None:
    claimed_state = make_job("claimed")
    attempt = JobAttempt(
        job_id=claimed_state.job_id,
        attempt_number=1,
        worker_id="worker-1",
        started_at=datetime.now(UTC),
    )
    state = fail(
        FakeSession(claimed_state, attempt),
        claimed_state.job_id,
        "worker-1",
        "t" * 64,
        "crash before start",
        False,
        "INVALID_SCIENTIFIC_INPUT",
    )
    assert state == "failed"
    assert claimed_state.failure_reason == "INVALID_SCIENTIFIC_INPUT"
    assert claimed_state.attempt_token is None
    assert attempt.error == "crash before start"

    job = make_job("claimed")
    with pytest.raises(ValueError, match="unknown failure reason"):
        fail(FakeSession(job), job.job_id, "worker-1", "t" * 64, "x", False, "MADE_UP")


def test_retryable_failure_requeues_until_exhausted() -> None:
    job = make_job("running", attempts=3)
    attempt = JobAttempt(
        job_id=job.job_id, attempt_number=3, worker_id="worker-1", started_at=datetime.now(UTC)
    )
    state = fail(
        FakeSession(job, attempt), job.job_id, "worker-1", "t" * 64, "flaky", True, None
    )
    assert state == "failed"
    assert job.failure_reason == "RETRY_EXHAUSTED"
    early = make_job("running", attempts=1)
    state = fail(FakeSession(early), early.job_id, "worker-1", "t" * 64, "flaky", True)
    assert state == "queued" and early.failure_reason is None


def test_invalid_transitions() -> None:
    job = make_job("claimed")
    with pytest.raises(JobStateError):
        succeed(FakeSession(job), job.job_id, "worker-1", "t" * 64, {})
    start(FakeSession(job), job.job_id, "worker-1", "t" * 64)
    assert job.state == "running"


def test_failure_reasons_are_the_bounded_contract() -> None:
    assert {
        "UNAVAILABLE_ACCESS",
        "INVALID_SCIENTIFIC_INPUT",
        "INTEGRITY_FAILURE",
        "UNSUPPORTED_ENGINE_OR_VERSION",
        "TRANSIENT_INFRASTRUCTURE",
        "RETRY_EXHAUSTED",
    } == FAILURE_REASONS


def test_reaper_classifies_expired_jobs() -> None:
    exhausted = make_job("running", expired=True, attempts=3)
    exhausted.job_id, exhausted.job_type, exhausted.payload = uuid.uuid4(), "x", {"a": 1}
    active = make_job("running")

    class ReapSession:
        def __init__(self):
            self.calls = 0

        def scalars(self, statement):
            self.calls += 1
            return iter([exhausted])

        def scalar(self, statement):
            return JobAttempt(
                job_id=exhausted.job_id,
                attempt_number=3,
                worker_id="worker-1",
                started_at=datetime.now(UTC),
            )

        def flush(self):
            pass

    reaped = reap_expired(ReapSession())
    assert reaped == [(exhausted.job_id, "x", {"a": 1})]
    assert exhausted.state == "failed" and exhausted.failure_reason == "RETRY_EXHAUSTED"
    assert exhausted.completed_at is not None and exhausted.attempt_token is None
    assert active.state == "running"


def test_heartbeat_thread_stops_and_stale_thread_gives_up(monkeypatch) -> None:
    calls = []

    @contextmanager
    def transaction():
        yield object()

    class Factory:
        begin = staticmethod(transaction)

    monkeypatch.setattr("workers.runtime.heartbeat", lambda *args: calls.append(args))
    claimed = ClaimedJob(uuid.uuid4(), "test", {}, "worker-1", "t" * 64)
    lease = LeaseHeartbeat(Factory(), claimed, 1)
    lease.start()
    time.sleep(0.4)
    lease.stop()
    count = len(calls)
    time.sleep(0.4)
    assert count >= 1 and len(calls) == count
    assert calls[0][2] == "worker-1" and calls[0][3] == "t" * 64
