"""Explicit GDC format registry. All parser output crosses canonical validation."""

import csv
import gzip
import json
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ValidationError

from packages.gdc.identity import FrozenIdentityResolver, IdentityError
from packages.gdc.normalization import normalize_gene
from packages.schemas.molecular import (
    MOLECULAR_SCHEMA_VERSION,
    ClinicalRecord,
    CNVRecord,
    ExpressionRecord,
    MutationRecord,
    SegmentCNVRecord,
)
from packages.schemas.snapshot import SnapshotObject

MAX_LINE_BYTES = 1024 * 1024
MAX_CLINICAL_BYTES = 8 * 1024 * 1024
MEASUREMENTS = (
    "unstranded",
    "stranded_first",
    "stranded_second",
    "tpm_unstranded",
    "fpkm_unstranded",
    "fpkm_uq_unstranded",
)
STAR_SPECIAL = frozenset({"N_unmapped", "N_multimapping", "N_noFeature", "N_ambiguous"})


def canonical_json(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


@dataclass
class Diagnostics:
    rows_seen: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    rows_excluded: int = 0
    samples_excluded: int = 0
    reasons: Counter = field(default_factory=Counter)
    emit: Callable[[dict], None] = field(default=lambda _: None, repr=False)

    def reject(
        self, line: int, reason: str, *, excluded: bool = False, candidates: int = 0
    ) -> None:
        if excluded:
            self.rows_excluded += 1
        else:
            self.rows_rejected += 1
        self.reasons[reason] += 1
        self.emit(
            {"row": line, "reason": reason, "excluded": excluded, "identity_candidates": candidates}
        )

    def summary(self) -> dict:
        return {
            "rows_seen": self.rows_seen,
            "rows_accepted": self.rows_accepted,
            "rows_rejected": self.rows_rejected,
            "rows_excluded": self.rows_excluded,
            "samples_excluded": self.samples_excluded,
            "reasons": dict(sorted(self.reasons.items())),
        }


@dataclass(frozen=True)
class ParseContext:
    path: Path
    source_file_id: str
    source_sha256: str
    identity: FrozenIdentityResolver
    measurement: str = ""


class Parser(Protocol):
    name: str
    version: str
    modality: str
    model: type[BaseModel]
    schema_version: str
    identity_level: str
    metadata: tuple[str, str, str, str, str]
    measurements: tuple[str, ...]

    def records(self, context: ParseContext, diagnostics: Diagnostics) -> Iterator[BaseModel]: ...


def optional(value):
    return None if value in (None, "", "--", "NA", "N/A", "Not Reported", "not reported") else value


def molecular_identity(
    row: dict, ctx: ParseContext, *, uuid_column: str = "", barcode_column: str = ""
) -> dict:
    barcode = optional(row.get(barcode_column))
    if uuid_column and not optional(row.get(uuid_column)) and not barcode:
        raise IdentityError("missing_aliquot_identity")
    resolved = ctx.identity.resolve(
        ctx.source_file_id,
        aliquot_id=optional(row.get(uuid_column)),
        submitter_id=barcode,
    )
    if uuid_column and resolved["aliquot_id"] is None:
        raise IdentityError("ambiguous_aliquot_identity")
    return resolved | {"source_file_id": ctx.source_file_id, "source_submitter_id": barcode}


def mutation(row: dict, ctx: ParseContext) -> dict:
    return (
        molecular_identity(
            row, ctx, uuid_column="Tumor_Sample_UUID", barcode_column="Tumor_Sample_Barcode"
        )
        | normalize_gene(row["Gene"])
        | {
            "gene_symbol": optional(row.get("Hugo_Symbol")),
            "chromosome": row["Chromosome"],
            "position": row["Start_Position"],
            "end_position": row["End_Position"],
            "ref": row["Reference_Allele"],
            "alt": row["Tumor_Seq_Allele2"],
            "consequence": optional(row.get("Consequence")),
            "variant_classification": optional(row.get("Variant_Classification")),
            "protein_change": optional(row.get("HGVSp_Short")),
            "transcript_id": optional(row.get("Transcript_ID")),
            "ssm_id": optional(row.get("ssm_id")),
        }
    )


def expression(row: dict, ctx: ParseContext) -> dict:
    value = row[ctx.measurement]
    if ctx.measurement in MEASUREMENTS[:3]:
        # Counts are integral source measurements even though the shared value type is float64.
        int(value)
    return (
        molecular_identity(row, ctx)
        | normalize_gene(row["gene_id"])
        | {
            "gene_symbol": optional(row.get("gene_name")),
            "value": value,
            "measurement_type": ctx.measurement,
        }
    )


def gene_cnv(row: dict, ctx: ParseContext) -> dict:
    return (
        molecular_identity(row, ctx)
        | normalize_gene(row["gene_id"])
        | {
            "gene_symbol": optional(row.get("gene_name")),
            "cnv_value": optional(row["copy_number"]),
            "min_copy_number": optional(row["min_copy_number"]),
            "max_copy_number": optional(row["max_copy_number"]),
        }
    )


def segment(row: dict, ctx: ParseContext) -> dict:
    return molecular_identity(row, ctx, uuid_column="GDC_Aliquot") | {
        "chromosome": row["Chromosome"],
        "start": row["Start"],
        "end": row["End"],
        "probe_count": optional(row["Num_Probes"]),
        "segment_mean": row["Segment_Mean"],
    }


@dataclass(frozen=True)
class TabularParser:
    name: str
    modality: str
    metadata: tuple[str, str, str, str, str]
    model: type[BaseModel]
    required: frozenset[str]
    map_row: Callable[[dict, ParseContext], dict]
    identity_level: str = "sample"
    measurements: tuple[str, ...] = ()
    version: str = "1"
    schema_version: str = MOLECULAR_SCHEMA_VERSION

    def records(self, context: ParseContext, diagnostics: Diagnostics) -> Iterator[BaseModel]:
        if self.measurements and context.measurement not in self.measurements:
            raise ValueError("unsupported_measurement")
        with context.path.open("rb") as probe:
            compressed = probe.read(2) == b"\x1f\x8b"
        opener = gzip.open if compressed else open
        with opener(context.path, "rb") as stream:
            header = None
            line_number = 0
            while raw := stream.readline(MAX_LINE_BYTES + 1):
                line_number += 1
                if len(raw) > MAX_LINE_BYTES:
                    raise ValueError("source_line_exceeds_limit")
                line = raw.decode("utf-8").rstrip("\r\n")
                if not line or line.startswith("#"):
                    continue
                values = next(csv.reader([line], delimiter="\t", quoting=csv.QUOTE_NONE))
                if header is None:
                    header = values
                    if len(set(header)) != len(header) or not self.required.issubset(header):
                        raise ValueError("malformed_header")
                    continue
                diagnostics.rows_seen += 1
                if len(values) != len(header):
                    diagnostics.reject(line_number, "malformed_row")
                    continue
                row = dict(zip(header, values, strict=True))
                if self.modality == "expression" and row["gene_id"] in STAR_SPECIAL:
                    diagnostics.reject(line_number, "star_summary_row", excluded=True)
                    continue
                try:
                    record = self.model.model_validate(self.map_row(row, context))
                except IdentityError as exc:
                    diagnostics.reject(
                        line_number,
                        exc.reason,
                        excluded=exc.reason == "not_primary_tumor",
                        candidates=exc.candidates,
                    )
                    continue
                except ValidationError:
                    diagnostics.reject(line_number, "invalid_canonical_record")
                    continue
                except ValueError:
                    diagnostics.reject(line_number, "invalid_source_value")
                    continue
                diagnostics.rows_accepted += 1
                yield record
            if header is None:
                raise ValueError("missing_header")


@dataclass(frozen=True)
class ClinicalParser:
    name: str = "gdc-cases-clinical"
    version: str = "1"
    modality: str = "clinical"
    model: type[BaseModel] = ClinicalRecord
    schema_version: str = MOLECULAR_SCHEMA_VERSION
    identity_level: str = "case"
    metadata: tuple[str, str, str, str, str] = (
        "Clinical",
        "GDC Cases",
        "",
        "API",
        "JSON",
    )
    measurements: tuple[str, ...] = ()

    def records(self, context: ParseContext, diagnostics: Diagnostics) -> Iterator[BaseModel]:
        # One bounded GDC API page per source artifact, never an unbounded cohort JSON.
        with context.path.open("rb") as stream:
            raw = stream.read(MAX_CLINICAL_BYTES + 1)
        if len(raw) > MAX_CLINICAL_BYTES:
            raise ValueError("clinical_page_exceeds_limit")
        payload = json.loads(raw)
        hits = payload.get("data", {}).get("hits")
        if not isinstance(hits, list):
            raise ValueError("malformed_clinical_page")
        for case in hits:
            if not isinstance(case, dict) or not isinstance(case.get("diagnoses", []), list):
                raise ValueError("malformed_clinical_case")
            demographic = case.get("demographic") or {}
            # Case-only rows retain real demographics when no diagnosis was supplied.
            for diagnosis in case.get("diagnoses") or [{}]:
                diagnostics.rows_seen += 1
                try:
                    record = ClinicalRecord(
                        case_id=context.identity.case(case.get("case_id", "")),
                        source_artifact_sha256=context.source_sha256,
                        diagnosis_id=optional(diagnosis.get("diagnosis_id")),
                        age_at_diagnosis=optional(diagnosis.get("age_at_diagnosis")),
                        stage=optional(diagnosis.get("ajcc_pathologic_stage")),
                        vital_status=optional(demographic.get("vital_status")),
                        days_to_death=optional(demographic.get("days_to_death")),
                        days_to_last_follow_up=optional(diagnosis.get("days_to_last_follow_up")),
                        gender=optional(demographic.get("gender")),
                        race=optional(demographic.get("race")),
                        ethnicity=optional(demographic.get("ethnicity")),
                        diagnosis_json=canonical_json(diagnosis),
                        demographic_json=canonical_json(demographic),
                        follow_ups_json=canonical_json(diagnosis.get("follow_ups", [])),
                        exposures_json=canonical_json(case.get("exposures", [])),
                    )
                except IdentityError as exc:
                    diagnostics.reject(diagnostics.rows_seen, exc.reason)
                    continue
                except (ValidationError, ValueError):
                    diagnostics.reject(diagnostics.rows_seen, "invalid_clinical_record")
                    continue
                diagnostics.rows_accepted += 1
                yield record


PARSERS: tuple[Parser, ...] = (
    TabularParser(
        "gdc-masked-maf",
        "mutation",
        (
            "Simple Nucleotide Variation",
            "Masked Somatic Mutation",
            "WXS",
            "Aliquot Ensemble Somatic Variant Merging and Masking",
            "MAF",
        ),
        MutationRecord,
        frozenset(
            {
                "Gene",
                "Chromosome",
                "Start_Position",
                "End_Position",
                "Reference_Allele",
                "Tumor_Seq_Allele2",
                "Tumor_Sample_UUID",
                "Tumor_Sample_Barcode",
            }
        ),
        mutation,
        identity_level="aliquot",
    ),
    TabularParser(
        "gdc-star-counts",
        "expression",
        (
            "Transcriptome Profiling",
            "Gene Expression Quantification",
            "RNA-Seq",
            "STAR - Counts",
            "TSV",
        ),
        ExpressionRecord,
        frozenset({"gene_id", "gene_name", "gene_type", *MEASUREMENTS}),
        expression,
        measurements=MEASUREMENTS,
    ),
    TabularParser(
        "gdc-ascat3-gene-cnv",
        "cnv",
        ("Copy Number Variation", "Gene Level Copy Number", "Genotyping Array", "ASCAT3", "TSV"),
        CNVRecord,
        frozenset({"gene_id", "gene_name", "copy_number", "min_copy_number", "max_copy_number"}),
        gene_cnv,
    ),
    TabularParser(
        "gdc-dnacopy-masked-segment",
        "segment_cnv",
        (
            "Copy Number Variation",
            "Masked Copy Number Segment",
            "Genotyping Array",
            "DNAcopy",
            "TXT",
        ),
        SegmentCNVRecord,
        frozenset({"GDC_Aliquot", "Chromosome", "Start", "End", "Num_Probes", "Segment_Mean"}),
        segment,
        identity_level="aliquot",
    ),
    ClinicalParser(),
)


def select_parser(
    *, modality: str, version: str, source: SnapshotObject | None, measurement: str = ""
) -> Parser:
    metadata = (
        (
            source.data_category,
            source.data_type,
            source.experimental_strategy,
            source.workflow_type,
            source.data_format,
        )
        if source
        else ClinicalParser.metadata
    )
    matches = [
        p
        for p in PARSERS
        if p.modality == modality and p.version == version and p.metadata == metadata
    ]
    if len(matches) != 1:
        raise ValueError("unknown_parser_combination")
    parser = matches[0]
    if (parser.measurements and measurement not in parser.measurements) or (
        not parser.measurements and measurement
    ):
        raise ValueError("unsupported_measurement")
    return parser
