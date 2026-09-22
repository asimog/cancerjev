import pytest

from packages.provenance.hashing import canonical_hash


def test_canonical_hash_is_key_order_independent() -> None:
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_hash_rejects_non_finite_json(value: float) -> None:
    with pytest.raises(ValueError, match="JSON|finite|range"):
        canonical_hash({"nested": {"value": value}})
