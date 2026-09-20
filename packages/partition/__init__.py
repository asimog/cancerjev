"""Dataset partition assignment for discovery/validation firewall."""

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
        discovery_cases = []
        validation_cases = []
        for cid in sorted_cases:
            h = hashlib.sha256(f"{seed}:{cid}".encode()).hexdigest()
            bucket = int(h[:8], 16) % 100
            if bucket < split_fraction * 100:
                discovery_cases.append(cid)
            else:
                validation_cases.append(cid)

        if not discovery_cases:
            discovery_cases.append(sorted_cases[0])
            validation_cases = sorted_cases[1:]
        if not validation_cases:
            validation_cases.append(sorted_cases[-1])
            discovery_cases = sorted_cases[:-1]

        def _build_assignment(partition_cases: list[str], partition: Partition):
            pid = f"P{partition.value[0]}-{uuid.uuid4().hex[:8]}"
            return DatasetPartitionAssignment(
                partition_id=pid,
                snapshot_id=snapshot_id,
                partition=partition,
                case_ids=tuple(sorted(set(partition_cases))),
                sample_ids=tuple(sorted(set(sample_ids))),
                aliquot_ids=tuple(sorted(set(aliquot_ids))),
                seed=seed,
                split_fraction=split_fraction,
                assignment_hash=canonical_hash({
                    "snapshot_id": snapshot_id,
                    "partition": partition.value,
                    "seed": seed,
                    "split_fraction": split_fraction,
                    "cases": sorted(set(partition_cases)),
                }),
            )

        discovery = _build_assignment(discovery_cases, Partition.DISCOVERY)
        validation = _build_assignment(validation_cases, Partition.VALIDATION)
        return discovery, validation


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