from dataclasses import dataclass

from packages.schemas.identity import SampleRecord


@dataclass(frozen=True)
class Selection:
    selected: tuple[SampleRecord, ...]
    excluded: tuple[tuple[str, str], ...]


def select_primary_tumor(samples: list[SampleRecord]) -> Selection:
    """Keep primary tumors; retain all tied UUID-sorted samples so ambiguity stays visible."""
    chosen, excluded = [], []
    for sample in sorted(samples, key=lambda x: x.sample_id):
        if sample.sample_type == "Primary Tumor" and sample.tissue_type != "Normal":
            chosen.append(sample)
        else:
            excluded.append((sample.sample_id, "not_primary_tumor"))
    return Selection(tuple(chosen), tuple(excluded))
