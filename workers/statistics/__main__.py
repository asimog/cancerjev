from workers.runtime import run_worker

JOB_TYPES = ("run_analysis_from_artifacts",)


def execute(claimed) -> dict:
    from packages.resources.execution import AnalysisExecutionService

    return AnalysisExecutionService.run_claimed(claimed)


def _fail_analysis(job_id: str, payload: dict, reason: str) -> None:
    """Couple terminal job failure to a consistent terminal Analysis state."""
    import logging

    from packages.database.config import resolve_database_url
    from packages.database.session import session_factory
    from packages.resources.service import DurableResourceService

    analysis_id = payload.get("analysis_id")
    if not analysis_id:
        return
    factory = session_factory(resolve_database_url())
    try:
        with factory.begin() as session:
            service = DurableResourceService(session)
            analysis = service.analyses.get(analysis_id)
            if analysis is not None and analysis.state in {"requested", "queued", "running"}:
                service.transition_analysis(
                    analysis_id, "failed", error=f"job {job_id} failed: {reason}"
                )
    except Exception:
        # The hook must never take the worker loop down; the job state is already terminal.
        logging.getLogger(__name__).exception(
            "analysis_failure_transition_failed job_id=%s analysis_id=%s", job_id, analysis_id
        )


if __name__ == "__main__":
    run_worker(
        JOB_TYPES,
        {"run_analysis_from_artifacts": execute},
        terminal_failure_hooks={"run_analysis_from_artifacts": _fail_analysis},
    )
