"""Artifact-backed statistics engine dispatcher.

Delegates to AnalysisExecutionService for the lease-checked,
transaction-safe execution lifecycle.
"""

import logging

from packages.database.config import resolve_database_url
from packages.database.session import session_factory
from packages.resources.execution import AnalysisExecutionService
from packages.resources.resolver import AnalysisInputResolver
from packages.resources.service import DurableResourceService
from packages.storage.config import StorageSettings

log = logging.getLogger(__name__)


def run_analysis_from_artifacts(payload: dict) -> dict:
    fencing_ctx = payload.get("_fencing", {})
    worker_id = fencing_ctx.get("worker_id")
    job_id = fencing_ctx.get("job_id")
    attempt_token = fencing_ctx.get("attempt_token")
    analysis_id = payload.get("analysis_id")
    if not analysis_id:
        raise ValueError("payload must contain analysis_id")
    if not worker_id or not job_id or not attempt_token:
        raise ValueError("payload must contain _fencing with worker_id, job_id, attempt_token")

    factory = session_factory(resolve_database_url())
    settings = StorageSettings()
    store = settings.store()

    with factory() as session:
        resources = DurableResourceService(session)
        resolver = AnalysisInputResolver(session, resources, store, settings)
        execution = AnalysisExecutionService(session, resources, resolver)
        import uuid
        return execution.execute_with_fencing(
            analysis_id,
            uuid.UUID(job_id),
            worker_id,
            attempt_token,
            purpose="EXPLORATORY",
        )