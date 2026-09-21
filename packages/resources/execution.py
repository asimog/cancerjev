"""Atomic analysis execution lifecycle service.

Owns the lease-checked transactional boundary for:
- Transitioning Analysis queued -> running
- Resolving frozen inputs
- Invoking the declared engine
- Persisting typed findings
- Transitioning Analysis running -> completed
- Marking Job succeeded

All on a stale-attempt-rejected, lease-verified transaction."""

import hashlib
import json
import logging
import uuid

from sqlalchemy.orm import Session

from packages.database.jobs import fail as _fail_job
from packages.database.jobs import succeed as _succeed_job
from packages.provenance.hashing import canonical_hash
from packages.resources.resolver import AnalysisInputResolver
from packages.resources.service import DurableResourceService, InvalidTransitionError

log = logging.getLogger(__name__)


class AnalysisExecutionError(RuntimeError):
    def __init__(self, reason: str, retryable: bool = False):
        self.reason = reason
        self.retryable = retryable
        super().__init__(reason)


ENGINE_HANDLERS = {}


def _register(name: str):
    def wrapper(fn):
        ENGINE_HANDLERS[name] = fn
        return fn
    return wrapper


class AnalysisExecutionService:
    """Lease-checked, transaction-safe analysis execution."""

    def __init__(
        self,
        session: Session,
        resources: DurableResourceService,
        resolver: AnalysisInputResolver,
    ):
        self.session = session
        self.resources = resources
        self.resolver = resolver

    def execute(
        self,
        analysis_id: str,
        job_id: uuid.UUID,
        worker_id: str,
        attempt_token: str,
        purpose: str = "EXPLORATORY",
    ) -> dict:
        """Execute an analysis atomically within a lease-fenced transaction."""
        analysis = self.resources.analyses.get(analysis_id)
        if analysis is None:
            raise AnalysisExecutionError(f"analysis not found: {analysis_id}")
        if analysis.state != "queued":
            raise AnalysisExecutionError(
                f"analysis {analysis_id} is in state {analysis.state}, expected queued"
            )

        # Transition analysis to running
        try:
            self.resources.transition_analysis(analysis_id, "running")
        except InvalidTransitionError as exc:
            raise AnalysisExecutionError(str(exc)) from exc

        # Generate frozen execution manifest before calculation
        manifest = self.resolver.resolve(analysis_id, purpose=purpose)
        manifest_hash = canonical_hash(manifest.parameters)
        analysis.execution_manifest_hash = manifest_hash
        self.session.flush()

        # Find and run the engine
        engine_handler = ENGINE_HANDLERS.get(manifest.engine)
        if engine_handler is None:
            raise AnalysisExecutionError(
                f"unsupported engine: {manifest.engine}", retryable=False
            )

        try:
            result = engine_handler(manifest)
        except Exception as exc:
            log.exception(
                "engine execution failed analysis_id=%s engine=%s",
                analysis_id,
                manifest.engine,
            )
            raise AnalysisExecutionError(str(exc), retryable=False) from exc

        findings_data = result.get("findings", [])
        if not findings_data:
            log.warning(
                "engine produced no findings analysis_id=%s engine=%s",
                analysis_id,
                manifest.engine,
            )

        # Persist findings within the completion transaction
        persisted_findings = []
        for finding_data in findings_data:
            finding_id = f"F-{uuid.uuid4().hex[:12]}"
            result_hash = "sha256:" + hashlib.sha256(
                json.dumps(finding_data, sort_keys=True).encode()
            ).hexdigest()
            try:
                finding = self.resources.persist_finding({
                    "finding_id": finding_id,
                    "analysis_id": uuid.UUID(manifest.analysis_id),
                    "finding_type": manifest.engine,
                    "gene_id": finding_data.get("gene_id"),
                    "gene_symbol": finding_data.get("gene_symbol"),
                    "analysis_version": manifest.engine_version,
                    "result_hash": result_hash,
                    "payload": finding_data,
                })
                persisted_findings.append(finding)
            except Exception as exc:
                log.warning("finding persistence failed: %s", exc)
                raise AnalysisExecutionError(
                    f"finding persistence failed: {exc}", retryable=False
                ) from exc

        # Transition to completed
        try:
            self.resources.transition_analysis(analysis_id, "completed")
        except InvalidTransitionError as exc:
            raise AnalysisExecutionError(str(exc)) from exc

        # Mark job succeeded
        _succeed_job(
            self.session,
            job_id,
            worker_id,
            {"analysis_id": analysis_id, "status": "completed"},
            attempt_token=attempt_token,
        )
        self.session.commit()
        return {
            "analysis_id": analysis_id,
            "engine": manifest.engine,
            "status": "completed",
            "findings_count": len(persisted_findings),
        }

    def execute_with_fencing(
        self,
        analysis_id: str,
        job_id: uuid.UUID,
        worker_id: str,
        attempt_token: str,
        purpose: str = "EXPLORATORY",
    ) -> dict:
        """Execute with fencing error handling.

        Returns a dict suitable for the Job result.
        On failure: transitions Analysis to failed, Job to failed/retryable.
        """
        try:
            return self.execute(
                analysis_id, job_id, worker_id, attempt_token, purpose=purpose
            )
        except AnalysisExecutionError as exc:
            try:
                self.resources.transition_analysis(
                    analysis_id, "failed", error=exc.reason
                )
                _fail_job(
                    self.session,
                    job_id,
                    worker_id,
                    exc.reason,
                    retryable=exc.retryable,
                    attempt_token=attempt_token,
                )
                self.session.commit()
            except Exception as cleanup_err:
                log.exception(
                    "cleanup after execution failure failed: %s", cleanup_err
                )
                self.session.rollback()
            return {
                "analysis_id": analysis_id,
                "status": "failed",
                "error": exc.reason,
            }
        except Exception as exc:
            reason = str(exc)
            try:
                self.resources.transition_analysis(
                    analysis_id, "failed", error=reason
                )
                _fail_job(
                    self.session,
                    job_id,
                    worker_id,
                    reason,
                    retryable=False,
                    attempt_token=attempt_token,
                )
                self.session.commit()
            except Exception as cleanup_err:
                log.exception(
                    "cleanup after unexpected failure failed: %s", cleanup_err
                )
                self.session.rollback()
            return {
                "analysis_id": analysis_id,
                "status": "failed",
                "error": reason,
            }


# Register dispatcher-compatible engine handlers
@_register("mutation_frequency")
def _mutation_frequency(manifest):
    from scientific.mutation.engines import mutation_frequency
    mat = manifest.materializations.get("mutation", [])
    all_rows = []
    for m in mat:
        all_rows.extend(m.parsed)
    return mutation_frequency(
        all_rows,
        manifest.cohort_case_ids,
        variant_classes=manifest.parameters.get("variant_classes", ()),
        genes=manifest.parameters.get("genes"),
    )


@_register("cnv_frequency")
def _cnv_frequency(manifest):
    from scientific.cnv.engines import cnv_frequency
    mat = manifest.materializations.get("cnv", [])
    all_rows = []
    for m in mat:
        all_rows.extend(m.parsed)
    params = manifest.parameters
    return cnv_frequency(
        all_rows,
        manifest.cohort_sample_ids,
        amplification_threshold=params.get("amplification_threshold", 0.2),
        deletion_threshold=params.get("deletion_threshold", -0.2),
        genes=params.get("genes"),
    )


@_register("cnv_rna")
def _cnv_rna(manifest):
    from scientific.crossmodal.engines import cnv_rna
    cnv_mat = manifest.materializations.get("cnv", [])
    rna_mat = manifest.materializations.get("expression", [])
    cnv_rows = [r for m in cnv_mat for r in m.parsed]
    rna_rows = [r for m in rna_mat for r in m.parsed]
    return cnv_rna(
        cnv_rows,
        rna_rows,
        set(manifest.cohort_sample_ids),
        genes=manifest.parameters.get("genes"),
    )


@_register("mutation_rna")
def _mutation_rna(manifest):
    from scientific.crossmodal.engines import mutation_rna
    mut_mat = manifest.materializations.get("mutation", [])
    rna_mat = manifest.materializations.get("expression", [])
    mut_rows = [r for m in mut_mat for r in m.parsed]
    rna_rows = [r for m in rna_mat for r in m.parsed]
    return mutation_rna(
        mut_rows,
        rna_rows,
        set(manifest.cohort_sample_ids),
        variant_classes=manifest.parameters.get("variant_classes", ()),
        genes=manifest.parameters.get("genes"),
    )


@_register("rna_outlier")
def _rna_outlier(manifest):
    from scientific.expression.engines import rna_outlier
    mat = manifest.materializations.get("expression", [])
    all_rows = [r for m in mat for r in m.parsed]
    return rna_outlier(
        all_rows,
        manifest.cohort_sample_ids,
        threshold=manifest.parameters.get("threshold", 3.5),
        genes=manifest.parameters.get("genes"),
    )


@_register("survival")
def _survival(manifest):
    from scientific.survival.engines import survival
    mat = manifest.materializations.get("clinical", [])
    all_rows = [r for m in mat for r in m.parsed]
    all_ids = manifest.cohort_case_ids
    return survival(
        all_rows,
        {"all": all_ids},
        {"all": "cohort"},
    )


@_register("confounder_check")
def _confounder_check(manifest):
    from scientific.qc.engines import confounder_check
    mat = manifest.materializations.get("clinical", [])
    all_rows = [r for m in mat for r in m.parsed]
    all_ids = manifest.cohort_case_ids
    return confounder_check(
        all_rows,
        {"all": all_ids},
    )


@_register("eligible_somatic_mutation_count")
def _eligible_somatic_mutation_count(manifest):
    from scientific.mutation.engines import eligible_somatic_mutation_count
    mat = manifest.materializations.get("mutation", [])
    all_rows = [r for m in mat for r in m.parsed]
    return eligible_somatic_mutation_count(
        all_rows,
        manifest.cohort_sample_ids,
        variant_classes=manifest.parameters.get("variant_classes", ()),
        genes=manifest.parameters.get("genes"),
    )


@_register("mutation_cooccurrence")
def _mutation_cooccurrence(manifest):
    from scientific.mutation.engines import mutation_cooccurrence
    mat = manifest.materializations.get("mutation", [])
    all_rows = [r for m in mat for r in m.parsed]
    genes = manifest.parameters.get("genes", ())
    if len(genes) != 2:
        return {
            "result": {
                "kind": "non_estimable",
                "reason": "mutation_cooccurrence requires exactly 2 genes",
            }
        }
    return mutation_cooccurrence(
        all_rows,
        manifest.cohort_case_ids,
        genes[0],
        genes[1],
    )


@_register("cohort_comparison")
def _cohort_comparison(manifest):
    from scientific.expression.engines import cohort_comparison
    mat = manifest.materializations.get("expression", [])
    all_rows = [r for m in mat for r in m.parsed]
    comparison_cohort_id = manifest.parameters.get("comparison_cohort_id")
    comparison_cohort = None
    if comparison_cohort_id:
        comparison_cohort = manifest.resources.cohorts.get(comparison_cohort_id)
    cohort_case_ids = set(manifest.cohort_case_ids)
    g1 = [
        r.get("value", 0) for r in all_rows
        if r.get("case_id") in cohort_case_ids
        and isinstance(r.get("value"), (int, float))
    ]
    g2 = []
    g2_ids: tuple[str, ...] = ()
    if comparison_cohort:
        comp_case_ids = set(comparison_cohort.case_ids)
        g2 = [
            r.get("value", 0) for r in all_rows
            if r.get("case_id") in comp_case_ids
            and isinstance(r.get("value"), (int, float))
        ]
    return cohort_comparison(
        g1,
        g2 or [0.0],
        tuple(manifest.cohort_case_ids),
        g2_ids or tuple(manifest.cohort_case_ids),
    )