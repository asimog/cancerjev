"""Artifact-backed statistics engine dispatcher.

Resolves analysis_id from job payload, loads immutable Parquet via
AnalysisInputResolver, runs the declared engine, persists Findings.
"""

import hashlib
import json
import logging
import uuid

from packages.database.config import resolve_database_url
from packages.database.session import session_factory
from packages.resources.resolver import AnalysisInputResolver, InputResolutionError
from packages.resources.service import DurableResourceService
from packages.schemas.finding import Eligibility
from packages.storage.config import StorageSettings

log = logging.getLogger(__name__)

ENGINE_HANDLERS = {}


def _register(name: str):
    def wrapper(fn):
        ENGINE_HANDLERS[name] = fn
        return fn
    return wrapper


def run_analysis_from_artifacts(payload: dict) -> dict:
    payload.get("_fencing", {})
    analysis_id = payload.get("analysis_id")
    if not analysis_id:
        raise ValueError("payload must contain analysis_id")

    factory = session_factory(resolve_database_url())
    settings = StorageSettings()
    store = settings.store()

    with factory() as session:
        resources = DurableResourceService(session)
        resolver = AnalysisInputResolver(session, resources, store, settings)
        try:
            manifest = resolver.resolve(analysis_id, purpose="EXPLORATORY")
        except InputResolutionError as exc:
            resources.transition_analysis(analysis_id, "failed", error=str(exc))
            return {"analysis_id": analysis_id, "status": "failed", "error": str(exc)}

        engine_handler = ENGINE_HANDLERS.get(manifest.engine)
        if engine_handler is None:
            resources.transition_analysis(analysis_id, "failed", error=f"unsupported engine: {manifest.engine}")
            return {"analysis_id": analysis_id, "status": "failed"}

        try:
            result = engine_handler(manifest)
        except Exception as exc:
            log.exception("engine execution failed analysis_id=%s engine=%s", analysis_id, manifest.engine)
            resources.transition_analysis(analysis_id, "failed", error=str(exc))
            return {"analysis_id": analysis_id, "status": "failed", "error": str(exc)}

        Eligibility(
            unit="sample",
            total_n=manifest.population["total_samples"],
            eligible_n=manifest.population["eligible_samples"],
            eligible_ids=tuple(manifest.cohort_sample_ids),
            eligible_case_ids=tuple(manifest.cohort_case_ids),
            eligible_sample_ids=tuple(manifest.cohort_sample_ids),
            missing_ids=(),
            missing_n=0,
            missing_fraction=0.0,
            excluded=manifest.population.get("excluded", {}),
            modality_eligible_ids={},
        )

        if "findings" in result:
            for finding_data in result["findings"]:
                finding_id = f"F-{uuid.uuid4().hex[:12]}"
                result_hash = "sha256:" + hashlib.sha256(
                    json.dumps(finding_data, sort_keys=True).encode()
                ).hexdigest()
                try:
                    resources.persist_finding({
                        "finding_id": finding_id,
                        "analysis_id": uuid.UUID(manifest.analysis_id),
                        "finding_type": manifest.engine,
                        "gene_id": finding_data.get("gene_id"),
                        "gene_symbol": finding_data.get("gene_symbol"),
                        "analysis_version": manifest.engine_version,
                        "result_hash": result_hash,
                        "payload": finding_data,
                    })
                except Exception as exc:
                    log.warning("finding persistence failed: %s", exc)

        resources.transition_analysis(manifest.analysis_id, "completed")
        return {"analysis_id": manifest.analysis_id, "engine": manifest.engine, "status": "completed"}


# Register engines
@_register("mutation_frequency")
def _mutation_frequency(manifest):
    from scientific.mutation.engines import mutation_frequency
    mat = manifest.materializations.get("mutation", [])
    all_rows = []
    for m in mat:
        all_rows.extend(m.parsed)
    return mutation_frequency(all_rows, manifest.cohort_case_ids)


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
    )


@_register("cnv_rna")
def _cnv_rna(manifest):
    from scientific.crossmodal.engines import cnv_rna
    cnv_mat = manifest.materializations.get("cnv", [])
    rna_mat = manifest.materializations.get("expression", [])
    cnv_rows = [r for m in cnv_mat for r in m.parsed]
    rna_rows = [r for m in rna_mat for r in m.parsed]
    return cnv_rna(cnv_rows, rna_rows, set(manifest.cohort_sample_ids))


@_register("mutation_rna")
def _mutation_rna(manifest):
    from scientific.crossmodal.engines import mutation_rna
    mut_mat = manifest.materializations.get("mutation", [])
    rna_mat = manifest.materializations.get("expression", [])
    mut_rows = [r for m in mut_mat for r in m.parsed]
    rna_rows = [r for m in rna_mat for r in m.parsed]
    return mutation_rna(mut_rows, rna_rows, set(manifest.cohort_sample_ids))


@_register("rna_outlier")
def _rna_outlier(manifest):
    from scientific.expression.engines import rna_outlier
    mat = manifest.materializations.get("expression", [])
    all_rows = [r for m in mat for r in m.parsed]
    return rna_outlier(
        all_rows,
        manifest.cohort_sample_ids,
        threshold=manifest.parameters.get("threshold", 3.5),
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