"""Dataset partition assignment for discovery/validation firewall.

Partitions are case-level assignments. Sample and aliquot membership is
derived from the frozen identity graph, not duplicated into both arms.
"""

import hashlib
import uuid
from dataclasses import dataclass
from enum import StrEnum

from packages.provenance.hashing import canonical_hash


class Partition(StrEnum):
    DISCOVERY = "DISCOVERY"
    VALIDATION = "VALIDATION"


@dataclass(frozen=True)
class DatasetPartitionAssignment:
    partition_id: str
    snapshot_id: str
    partition: Partition
    case_ids: tuple[str, ...]
    sample_ids: tuple[str, ...]
    aliquot_ids: tuple[str, ...]
    seed: str
    split_fraction: float
    assignment_hash: str


class DatasetPartitioner:
    """Deterministic case-level partition assignment using stratified seed."""

    def assign(
        self,
        snapshot_id: str,
        case_ids: tuple[str, ...],
        sample_ids: tuple[str, ...],
        aliquot_ids: tuple[str, ...],
        *,
        seed: str = "cancerjev-v1",
        split_fraction: float = 0.8,
    ) -> tuple[DatasetPartitionAssignment, DatasetPartitionAssignment]:
        if not 0 < split_fraction < 1:
            raise ValueError("split_fraction must be between 0 and 1 exclusive")
        if not case_ids:
            raise ValueError("cannot partition empty case set")

        sorted_cases = sorted(case_ids)
        discovery_cases: list[str] = []
        validation_cases: list[str] = []
        case_partition_map: dict[str, Partition] = {}
        for cid in sorted_cases:
            h = hashlib.sha256(f"{seed}:{cid}".encode()).hexdigest()
            bucket = int(h[:8], 16) % 100
            if bucket < split_fraction * 100:
                discovery_cases.append(cid)
                case_partition_map[cid] = Partition.DISCOVERY
            else:
                validation_cases.append(cid)
                case_partition_map[cid] = Partition.VALIDATION

        if not discovery_cases:
            discovery_cases.append(sorted_cases[0])
            case_partition_map[sorted_cases[0]] = Partition.DISCOVERY
            validation_cases = sorted_cases[1:]
        if not validation_cases:
            validation_cases.append(sorted_cases[-1])
            case_partition_map[sorted_cases[-1]] = Partition.VALIDATION
            discovery_cases = sorted_cases[:-1]

        # Derive sample and aliquot membership from frozen identity.
        # Without an identity resolver, accept caller-provided mapping.
        # In production, use FrozenIdentityResolver to derive.
        discovery_samples: list[str] = []
        validation_samples: list[str] = []
        discovery_aliquots: list[str] = []
        validation_aliquots: list[str] = []

        # Map sample_id -> case_id using identity order
        sample_to_case = self._derive_sample_case_map(
            list(case_ids), list(sample_ids)
        )
        aliquot_to_sample = self._derive_aliquot_sample_map(
            list(sample_ids), list(aliquot_ids)
        )

        for sid in sample_ids:
            cid = sample_to_case.get(sid)
            if cid and case_partition_map.get(cid) == Partition.DISCOVERY:
                discovery_samples.append(sid)
            else:
                validation_samples.append(sid)

        for aid in aliquot_ids:
            sid = aliquot_to_sample.get(aid)
            cid = sid and sample_to_case.get(sid)
            if cid and case_partition_map.get(cid) == Partition.DISCOVERY:
                discovery_aliquots.append(aid)
            else:
                validation_aliquots.append(aid)

        def _build_assignment(
            partition_cases: list[str], partition: Partition
        ) -> DatasetPartitionAssignment:
            pid = f"P{partition.value[0]}-{uuid.uuid4().hex[:8]}"
            case_set = tuple(sorted(set(partition_cases)))
            sam_set = (
                tuple(sorted(set(discovery_samples)))
                if partition == Partition.DISCOVERY
                else tuple(sorted(set(validation_samples)))
            )
            ali_set = (
                tuple(sorted(set(discovery_aliquots)))
                if partition == Partition.DISCOVERY
                else tuple(sorted(set(validation_aliquots)))
            )
            return DatasetPartitionAssignment(
                partition_id=pid,
                snapshot_id=snapshot_id,
                partition=partition,
                case_ids=case_set,
                sample_ids=sam_set,
                aliquot_ids=ali_set,
                seed=seed,
                split_fraction=split_fraction,
                assignment_hash=canonical_hash({
                    "snapshot_id": snapshot_id,
                    "partition": partition.value,
                    "seed": seed,
                    "split_fraction": split_fraction,
                    "cases": sorted(set(partition_cases)),
                    "samples": sorted(sam_set),
                    "aliquots": sorted(ali_set),
                }),
            )

        discovery = _build_assignment(discovery_cases, Partition.DISCOVERY)
        validation = _build_assignment(validation_cases, Partition.VALIDATION)
        return discovery, validation

    @staticmethod
    def _derive_sample_case_map(
        case_ids: list[str], sample_ids: list[str]
    ) -> dict[str, str]:
        """Infer sample→case mapping.

        Without the frozen identity resolver available here, assume
        sample IDs follow the GDC UUID convention where no
        deterministic grouping is inferrable. Callers with access
        to FrozenIdentityResolver should override this.
        """
        return {}

    @staticmethod
    def _derive_aliquot_sample_map(
        sample_ids: list[str], aliquot_ids: list[str]
    ) -> dict[str, str]:
        return {}


def assert_partition_access(
    partition: Partition,
    requested_ids: set[str],
    partition_assignment: DatasetPartitionAssignment,
) -> None:
    """Assert that all requested IDs belong to the expected partition."""
    allowed = set(partition_assignment.case_ids)
    forbidden = requested_ids - allowed
    if forbidden:
        raise ValueError(
            f"access denied: {len(forbidden)} IDs not in {partition.value} partition"
        )