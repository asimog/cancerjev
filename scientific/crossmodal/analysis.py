"""Deterministic CNV/RNA association engine with complete scientific identity.

The engine is infrastructure-free: it receives cohort-filtered canonical rows
and a frozen context, rejects duplicate biological keys, applies finite-value
eligibility before the minimum-pairs check, and computes a result identity
that binds every material scientific input and output. Row ordering and
execution timing never affect the identity.
"""

import platform
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import scipy

from packages.provenance.hashing import canonical_hash
from packages.schemas.finding import Finding
from packages.statistics.core import benjamini_hochberg
from packages.statistics.crossmodal import cnv_expression

FINDING_TYPE = "cnv_expression_association"
IDENTITY_CONTRACT_VERSION = "cj-r00-result-v1"
ELIGIBILITY_VERSION = "cnv-rna-eligibility-v1"
MIN_PAIRS = 4


def runtime_environment() -> dict:
    """Identity-bearing runtime versions for deterministic engines."""
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


@dataclass(frozen=True)
class EngineContext:
    """Frozen identity-bearing inputs; nothing here is worker or UI state."""

    snapshot_id: str
    snapshot_hash: str
    cohort_id: str | None
    cohort_content_hash: str | None
    cohort_size: int
    engine_version: str
    method_version: str
    parameters: dict
    input_hashes: tuple[str, ...]
    environment: dict = field(default_factory=runtime_environment)


def analyze_cnv_rna(
    context: EngineContext, cnv_rows: list[dict], rna_rows: list[dict]
) -> list[Finding]:
    """Inner-join exact case/sample/gene identity and disclose the analyzed population."""
    cnv = _unique_keys(cnv_rows, "cnv")
    rna = _unique_keys(rna_rows, "rna")
    pairs = defaultdict(list)
    for key in sorted(cnv.keys() & rna.keys()):
        pairs[key[2]].append((key, cnv[key], rna[key]))
    tested = []
    for gene, rows in sorted(pairs.items()):
        # Finite-value eligibility precedes the minimum-pairs check so the
        # reported population is exactly the population the statistic used.
        finite = [
            (key, cnv_row, rna_row)
            for key, cnv_row, rna_row in rows
            if _is_finite(cnv_row.get("cnv_value")) and _is_finite(rna_row.get("value"))
        ]
        if len(finite) < MIN_PAIRS:
            continue
        try:
            result = cnv_expression(
                [row["cnv_value"] for _, row, _ in finite],
                [row["value"] for _, _, row in finite],
            )
        except ValueError:
            # Zero-variance genes are untestable, not analysis failures.
            continue
        tested.append((gene, finite, result))
    q_values = benjamini_hochberg([result.p_value for _, _, result in tested])
    tested_gene_ids = tuple(gene for gene, _, _ in tested)
    findings = []
    for (gene, finite, result), q in zip(tested, q_values, strict=True):
        cases = tuple(sorted({key[0] for key, _, _ in finite}))
        samples = tuple(sorted({key[1] for key, _, _ in finite}))
        payload = {
            "effect_size": result.effect_size,
            "p_value": result.p_value,
            "q_value": q,
            "confidence_interval": list(result.confidence_interval),
            "n_effective": len(finite),
            "eligible_case_ids": list(cases),
            "eligible_sample_ids": list(samples),
            "missing_n": max(context.cohort_size - len(cases), 0),
        }
        result_hash = result_identity(context, gene, payload, tested_gene_ids)
        findings.append(
            Finding(
                snapshot_id=context.snapshot_id,
                finding_type=FINDING_TYPE,
                gene=gene,
                cohort_size=context.cohort_size,
                eligible_cases=len(cases),
                eligible_case_ids=cases,
                eligible_sample_ids=samples,
                n_effective=len(finite),
                effect_size=result.effect_size,
                confidence_interval=result.confidence_interval,
                p_value=result.p_value,
                q_value=q,
                missing_n=payload["missing_n"],
                missing_fraction=(
                    payload["missing_n"] / context.cohort_size if context.cohort_size else 0
                ),
                analysis_version=context.method_version,
                input_object_hashes=tuple(sorted(context.input_hashes)),
                tested_gene_ids=tested_gene_ids,
                result_hash=result_hash,
            )
        )
    return findings


def result_identity(
    context: EngineContext,
    gene: str,
    payload: dict,
    tested_gene_ids: tuple[str, ...],
) -> str:
    """Canonical scientific identity: every material input and output is bound."""
    for name in ("effect_size", "p_value", "q_value"):
        if not _is_finite(payload[name]):
            raise ValueError(f"non-finite {name} cannot enter scientific identity")
    low, high = payload["confidence_interval"]
    if not _is_finite(low) or not _is_finite(high):
        raise ValueError("non-finite confidence interval cannot enter scientific identity")
    identity = {
        "identity_contract_version": IDENTITY_CONTRACT_VERSION,
        "snapshot": {"snapshot_id": context.snapshot_id, "snapshot_hash": context.snapshot_hash},
        "cohort": {
            "cohort_id": context.cohort_id,
            "content_hash": context.cohort_content_hash,
        },
        "input_artifacts": sorted(context.input_hashes),
        "engine": {
            "engine": "cnv_rna",
            "engine_version": context.engine_version,
            "method_version": context.method_version,
        },
        "parameters": context.parameters,
        "family": {
            "finding_type": FINDING_TYPE,
            "gene_id": gene,
            "tested_gene_ids": sorted(tested_gene_ids),
            "multiple_testing": "benjamini-hochberg-v1",
        },
        "eligibility": {
            "min_pairs": MIN_PAIRS,
            "finite_required": True,
            "eligibility_version": ELIGIBILITY_VERSION,
        },
        "environment": context.environment,
        "output": {
            "effect_size": payload["effect_size"],
            "p_value": payload["p_value"],
            "q_value": payload["q_value"],
            "confidence_interval": payload["confidence_interval"],
            "n_effective": payload["n_effective"],
            "eligible_case_ids": payload["eligible_case_ids"],
            "eligible_sample_ids": payload["eligible_sample_ids"],
            "missing_n": payload["missing_n"],
        },
    }
    return canonical_hash(identity)


def _unique_keys(rows: list[dict], label: str) -> dict[tuple[str, str, str], dict]:
    """Duplicate biological keys are a deterministic input failure, never a policy."""
    indexed: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        key = (row["case_id"], row["sample_id"], row["gene_id"])
        if key in indexed:
            raise ValueError(
                f"duplicate_{label}_key: ({key[0]}, {key[1]}, {key[2]}) appears more than once"
            )
        indexed[key] = row
    return indexed


def _is_finite(value) -> bool:
    return isinstance(value, (int, float)) and np.isfinite(value)
