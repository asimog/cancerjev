from packages.provenance.hashing import canonical_hash


def test_canonical_hash_is_key_order_independent() -> None:
    assert canonical_hash({"b": 2, "a": 1}) == canonical_hash({"a": 1, "b": 2})
