from workers.runtime import run_worker


def materialize(payload: dict) -> dict:
    from workers.ingest.materialize import materialize_snapshot

    return materialize_snapshot(payload)


if __name__ == "__main__":
    run_worker(("materialize_snapshot",), {"materialize_snapshot": materialize})
