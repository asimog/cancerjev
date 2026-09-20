"""Local, deterministic identifiers; this is not a gene-symbol mapping service."""

import re

NORMALIZATION_VERSION = "ensembl-gene-suffix-v1"


def normalize_gene(source: str) -> dict:
    match = re.fullmatch(r"(ENSG[0-9]{11})(?:\.([0-9]+))?(_PAR_Y)?", source)
    if not match:
        raise ValueError("unsupported_gene_identifier")
    return {
        "gene_id": match[1] + (match[3] or ""),
        "source_gene_id": source,
        "gene_version": match[2],
        "normalization_version": NORMALIZATION_VERSION,
    }
