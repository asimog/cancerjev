"""Strict, bounded V1 engine declarations; no dynamic function imports."""

from dataclasses import dataclass
from typing import Literal

from pydantic import Field, FiniteFloat, model_validator

from packages.schemas.identity import StrictRecord

RNAType = Literal["unstranded", "stranded_first", "stranded_second", "tpm_unstranded",
                  "fpkm_unstranded", "fpkm_uq_unstranded"]


class Parameters(StrictRecord):
    materialization_ids: tuple[str, ...] = Field(default=(), max_length=10000)


class Genes(Parameters):
    genes: tuple[str, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_genes(self):
        if len(set(self.genes)) != len(self.genes) or any(not gene for gene in self.genes):
            raise ValueError("genes must be nonempty and unique")
        return self


class MutationGenes(Genes):
    variant_classes: tuple[str, ...] = ()


class MutationCounts(Parameters):
    variant_classes: tuple[str, ...] = ()


class Pairs(MutationGenes):
    genes: tuple[str, ...] = Field(min_length=2, max_length=100)


class RNA(Genes):
    measurement_type: RNAType


class MutationRNA(RNA):
    variant_classes: tuple[str, ...] = ()


class Outlier(RNA):
    threshold: FiniteFloat = Field(default=3.5, gt=0)


class CNVFrequency(Genes):
    amplification_threshold: FiniteFloat = Field(ge=0)
    deletion_threshold: FiniteFloat = Field(ge=0)

    @model_validator(mode="after")
    def ordered_thresholds(self):
        if self.deletion_threshold >= self.amplification_threshold:
            raise ValueError("deletion threshold must be below amplification threshold")
        return self


class Comparison(RNA):
    comparison_cohort_id: str = Field(min_length=1)


class Groups(Parameters):
    comparison_cohort_id: str = Field(min_length=1)


@dataclass(frozen=True)
class Engine:
    name: str
    parameters: type[Parameters]
    modalities: tuple[str, ...]
    unit: Literal["case", "sample"]
    finding_types: tuple[str, ...]
    minimum_n: int
    version: str = "1"
    schema_versions: tuple[str, ...] = ("2",)
    parser_versions: tuple[str, ...] = ("1",)
    rna_measurement_required: bool = False


ENGINES = {
    e.name: e for e in (
        Engine("mutation_frequency", MutationGenes, ("mutation",), "case", ("frequency",), 1),
        Engine("eligible_somatic_mutation_count", MutationCounts, ("mutation",), "sample", ("count",), 1),
        Engine("mutation_cooccurrence", Pairs, ("mutation",), "case", ("contingency",), 4),
        Engine("cnv_frequency", CNVFrequency, ("cnv",), "sample", ("cnv_frequency",), 1),
        Engine("rna_outlier", Outlier, ("expression",), "sample", ("outlier",), 3, rna_measurement_required=True),
        Engine("mutation_rna", MutationRNA, ("mutation", "expression"), "sample", ("association",), 4, rna_measurement_required=True),
        Engine("cnv_rna", RNA, ("cnv", "expression"), "sample", ("association",), 4, rna_measurement_required=True),
        Engine("survival", Groups, ("clinical",), "case", ("survival",), 4),
        Engine("cohort_comparison", Comparison, ("expression",), "sample", ("association",), 4, rna_measurement_required=True),
        Engine("confounder_check", Groups, ("clinical",), "case", ("qc",), 2),
    )
}


def resolve_engine(name: str, version: str, parameters: dict):
    engine = ENGINES.get(name)
    if engine is None or engine.version != version:
        raise ValueError("unknown_engine_or_version")
    params = engine.parameters.model_validate(parameters)
    normalized = params.model_dump(mode="json")
    for key in ("genes", "materialization_ids", "variant_classes"):
        if key in normalized:
            normalized[key] = sorted(set(normalized[key]))
    return engine, engine.parameters.model_validate(normalized)
