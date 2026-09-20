"""Resolve only identities frozen in the snapshot, never names from the filesystem."""

from dataclasses import dataclass
from functools import cached_property

from packages.gdc.selection import select_primary_tumor
from packages.schemas.identity import AliquotRecord, CaseRecord, FileSampleLink, SampleRecord

SELECTION_VERSION = "primary-tumor-retain-ties-v1"


class IdentityError(ValueError):
    def __init__(self, reason: str, candidates: int = 0):
        self.reason = reason
        self.candidates = candidates
        super().__init__(reason)


@dataclass(frozen=True)
class FrozenIdentityResolver:
    cases: tuple[CaseRecord, ...]
    samples: tuple[SampleRecord, ...]
    aliquots: tuple[AliquotRecord, ...]
    links: tuple[FileSampleLink, ...]

    def __post_init__(self):
        for records, key in (
            (self.cases, "case_id"),
            (self.samples, "sample_id"),
            (self.aliquots, "aliquot_id"),
        ):
            if len({getattr(r, key) for r in records}) != len(records):
                raise IdentityError("duplicate_frozen_identity")
        cases = {c.case_id for c in self.cases}
        samples = {s.sample_id: s for s in self.samples}
        aliquots = {a.aliquot_id: a for a in self.aliquots}
        if any(s.case_id not in cases for s in self.samples) or any(
            a.sample_id not in samples for a in self.aliquots
        ):
            raise IdentityError("inconsistent_frozen_identity")
        for link in self.links:
            if (
                link.case_id not in cases
                or (
                    link.sample_id
                    and (
                        link.sample_id not in samples
                        or samples[link.sample_id].case_id != link.case_id
                    )
                )
                or (
                    link.aliquot_id
                    and (
                        link.aliquot_id not in aliquots
                        or aliquots[link.aliquot_id].sample_id != link.sample_id
                    )
                )
            ):
                raise IdentityError("inconsistent_frozen_link")

    def case(self, case_id: str) -> str:
        if case_id not in self.case_ids:
            raise IdentityError("missing_case_identity")
        return case_id

    @cached_property
    def case_ids(self):
        return frozenset(c.case_id for c in self.cases)

    @cached_property
    def primary_ids(self):
        return frozenset(s.sample_id for s in select_primary_tumor(list(self.samples)).selected)

    @cached_property
    def file_links(self):
        indexed = {}
        for link in self.links:
            if link.sample_id:
                indexed.setdefault(link.file_id, set()).add(
                    (link.case_id, link.sample_id, link.aliquot_id)
                )
        return indexed

    @cached_property
    def submitter_links(self):
        indexed = {}
        for aliquot in self.aliquots:
            if aliquot.submitter_id:
                indexed.setdefault(aliquot.submitter_id, set()).add(("aliquot", aliquot.aliquot_id))
        for sample in self.samples:
            if sample.sample_submitter_id:
                indexed.setdefault(sample.sample_submitter_id, set()).add(
                    ("sample", sample.sample_id)
                )
        return indexed

    def resolve(
        self, file_id: str, *, aliquot_id: str | None = None, submitter_id: str | None = None
    ) -> dict:
        candidates = self.file_links.get(file_id, set())
        if aliquot_id:
            candidates = {v for v in candidates if v[2] == aliquot_id}
        if submitter_id:
            known = {
                a.submitter_id
                for a in self.aliquots
                if a.aliquot_id == aliquot_id and a.submitter_id
            }
            if known and submitter_id not in known:
                raise IdentityError("conflicting_identity")
            matches = {
                value
                for kind, value in self.submitter_links.get(submitter_id, ())
                if kind == "aliquot"
            }
            sample_matches = {
                value
                for kind, value in self.submitter_links.get(submitter_id, ())
                if kind == "sample"
            }
            # Older snapshots lack aliquot barcodes. UUID resolution remains
            # authoritative; an unknown barcode alone cannot resolve identity.
            if matches or sample_matches or not aliquot_id:
                candidates = {v for v in candidates if v[2] in matches or v[1] in sample_matches}
        if not candidates:
            raise IdentityError("missing_identity")
        candidates = {v for v in candidates if v[1] in self.primary_ids}
        if not candidates:
            raise IdentityError("not_primary_tumor")
        sample_pairs = {(c, s) for c, s, _ in candidates}
        if len(sample_pairs) != 1:
            raise IdentityError("ambiguous_sample_identity", len(sample_pairs))
        case_id, sample_id = next(iter(sample_pairs))
        aliquots = {a for _, _, a in candidates}
        if aliquot_id and len(aliquots) != 1:
            raise IdentityError("ambiguous_aliquot_identity", len(aliquots))
        return {
            "case_id": case_id,
            "sample_id": sample_id,
            "aliquot_id": next(iter(aliquots)) if len(aliquots) == 1 else None,
        }
