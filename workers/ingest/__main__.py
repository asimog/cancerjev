from workers.runtime import run_worker


def materialize(claimed) -> dict:
    from workers.ingest.materialize import materialize_snapshot

    return materialize_snapshot(claimed.payload)


if __name__ == "__main__":
    run_worker(("materialize_snapshot",), {"materialize_snapshot": materialize})
