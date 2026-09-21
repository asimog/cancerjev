"""Real-PostgreSQL proof of attempt fencing, reaping, and claim exclusivity."""

import os
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from packages.database.jobs import (
    ClaimedJob,
    LeaseLostError,
    claim,
    fail,
    heartbeat,
    reap_expired,
    start,
    succeed,
    verify_lease,
)
from packages.database.models import Job, JobAttempt
from packages.database.session import session_factory

DATABASE_URL = os.getenv("CANCERJEV_DATABASE_URL")
pytestmark = [
    pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL URL is not configured"),
    pytest.mark.postgres,
    pytest.mark.integration,
]


@pytest.fixture
def factory(migrated_database):
    return session_factory(DATABASE_URL)


@pytest.fixture(autouse=True)
def clean_jobs(migrated_database):
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE job_attempts, jobs CASCADE"))
    engine.dispose()


def insert_job(factory, **kwargs) -> uuid.UUID:
    with factory.begin() as session:
        job = Job(job_type="fence", payload={"kind": "fence"}, max_attempts=3, **kwargs)
        session.add(job)
        session.flush()
        return job.job_id


def expire(factory, job_id: uuid.UUID) -> None:
    with factory.begin() as session:
        session.execute(
            text(
                "UPDATE jobs SET lease_expires_at = now() - interval '1 second'"
                " WHERE job_id = :id"
            ),
            {"id": str(job_id)},
        )


def load_job(factory, job_id: uuid.UUID) -> Job:
    with factory() as session:
        job = session.get(Job, job_id)
        assert job is not None
        session.expunge(job)
        return job


def test_stale_attempt_cannot_complete_after_reclaim(factory) -> None:
    job_id = insert_job(factory)
    with factory.begin() as session:
        first = claim(session, "worker-a", ("fence",), lease_seconds=60)
    expire(factory, job_id)
    with factory.begin() as session:
        second = claim(session, "worker-b", ("fence",), lease_seconds=60)
    assert first and second and second.attempt_token != first.attempt_token
    with pytest.raises(LeaseLostError), factory.begin() as session:
        succeed(session, first.job_id, "worker-a", first.attempt_token, {"r": 1})
    row = load_job(factory, job_id)
    assert row.result is None and row.state == "claimed" and row.lease_owner == "worker-b"


def test_stale_heartbeat_cannot_renew_a_newer_attempt_of_the_same_worker(factory) -> None:
    job_id = insert_job(factory)
    with factory.begin() as session:
        first = claim(session, "worker-a", ("fence",), lease_seconds=60)
    expire(factory, job_id)
    with factory.begin() as session:
        second = claim(session, "worker-a", ("fence",), lease_seconds=60)
    assert first and second
    with pytest.raises(LeaseLostError), factory.begin() as session:
        heartbeat(session, first.job_id, "worker-a", first.attempt_token)
    with factory.begin() as session:
        heartbeat(session, second.job_id, "worker-a", second.attempt_token)
    assert load_job(factory, job_id).lease_expires_at > datetime.now(UTC)


def test_exhausted_expired_job_reaches_a_terminal_state(factory) -> None:
    with factory.begin() as session:
        job = Job(
            job_type="fence",
            payload={"kind": "fence"},
            state="running",
            lease_owner="worker-a",
            lease_expires_at=datetime.now(UTC) - timedelta(seconds=5),
            attempt_token="t" * 64,
            attempt_count=3,
            max_attempts=3,
        )
        session.add(job)
        session.flush()
        session.add(
            JobAttempt(
                job_id=job.job_id,
                attempt_number=3,
                worker_id="worker-a",
                attempt_token="t" * 64,
            )
        )
        job_id = job.job_id
    with factory.begin() as session:
        reaped = reap_expired(session)
    assert reaped == [(job_id, "fence", {"kind": "fence"})]
    row = load_job(factory, job_id)
    assert row.state == "failed" and row.failure_reason == "RETRY_EXHAUSTED"
    assert row.completed_at is not None and row.attempt_token is None


def test_reaper_closes_dangling_attempts_and_leaves_recoverable_jobs(factory) -> None:
    job_id = insert_job(factory)
    with factory.begin() as session:
        assert claim(session, "worker-a", ("fence",), lease_seconds=60) is not None
    expire(factory, job_id)
    with factory.begin() as session:
        assert reap_expired(session) == []
    with factory.begin() as session:
        dangling = session.scalar(
            text("SELECT count(*) FROM job_attempts WHERE completed_at IS NULL")
        )
        assert dangling == 0
    with factory.begin() as session:
        second = claim(session, "worker-b", ("fence",), lease_seconds=60)
    assert second is not None
    row = load_job(factory, job_id)
    assert row.attempt_count == 2 and row.state == "claimed" and row.lease_owner == "worker-b"


def test_crash_between_claim_and_start_is_recordable(factory) -> None:
    job_id = insert_job(factory)
    with factory.begin() as session:
        claimed = claim(session, "worker-a", ("fence",))
    with pytest.raises(ValueError), factory.begin() as session:
        fail(
            session,
            claimed.job_id,
            "worker-a",
            claimed.attempt_token,
            "bad reason",
            False,
            "NOT_A_REASON",
        )
    with factory.begin() as session:
        state = fail(
            session,
            claimed.job_id,
            "worker-a",
            claimed.attempt_token,
            "crashed before start",
            False,
            "INVALID_SCIENTIFIC_INPUT",
        )
    assert state == "failed"
    row = load_job(factory, job_id)
    assert row.failure_reason == "INVALID_SCIENTIFIC_INPUT" and row.lease_owner is None


def test_verify_lease_proves_the_current_attempt_inside_a_transaction(factory) -> None:
    job_id = insert_job(factory)
    with factory.begin() as session:
        claimed = claim(session, "worker-a", ("fence",), lease_seconds=60)
    with factory.begin() as session:
        job = verify_lease(session, claimed.job_id, "worker-a", claimed.attempt_token)
        assert job.state == "claimed"
        start(session, claimed.job_id, "worker-a", claimed.attempt_token)
        assert job.state == "running"
    expire(factory, job_id)
    with factory.begin() as session:
        reclaimed = claim(session, "worker-b", ("fence",), lease_seconds=60)
    with pytest.raises(LeaseLostError), factory.begin() as session:
        verify_lease(session, claimed.job_id, "worker-a", claimed.attempt_token)
    with factory.begin() as session:
        verify_lease(session, reclaimed.job_id, "worker-b", reclaimed.attempt_token)


def test_concurrent_claims_assign_exactly_one_attempt(factory) -> None:
    job_id = insert_job(factory)
    results: list[ClaimedJob | None] = []
    barrier = threading.Barrier(2)

    def doclaim(worker: str) -> None:
        with factory.begin() as session:
            barrier.wait(timeout=10)
            results.append(claim(session, worker, ("fence",), lease_seconds=60))

    threads = [threading.Thread(target=doclaim, args=(f"worker-{i}",)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert sum(value is not None for value in results) == 1
    row = load_job(factory, job_id)
    assert row.attempt_count == 1 and row.state == "claimed"
