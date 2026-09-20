import logging
import os
import socket
import time
from collections.abc import Callable

from packages.database.jobs import claim, fail, start, succeed
from packages.database.session import session_factory

log = logging.getLogger(__name__)


def run_worker(job_types: tuple[str, ...], handlers: dict[str, Callable[[dict], dict]]) -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s"
    )
    factory = session_factory(os.environ["CANCERJEV_DATABASE_URL"])
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    while True:
        with factory.begin() as session:
            job = claim(session, worker_id, job_types)
        if job is None:
            time.sleep(1)
            continue
        try:
            with factory.begin() as session:
                start(session, job.job_id, worker_id)
            result = handlers[job.job_type](job.payload)
            with factory.begin() as session:
                succeed(session, job.job_id, worker_id, result)
        except Exception as exc:
            log.exception("job_failed job_id=%s job_type=%s", job.job_id, job.job_type)
            with factory.begin() as session:
                fail(
                    session, job.job_id, worker_id, str(exc), bool(getattr(exc, "retryable", False))
                )
