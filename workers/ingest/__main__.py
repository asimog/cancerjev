"""Ingest worker entry point.

The ``materialize_snapshot`` consumer is pre-positioned for the R04
acquisition path and is not yet enqueued by any R00 component; the underlying
``MaterializationService`` is exercised through the API and integration tests.
"""

from workers.runtime import run_worker


def materialize(claimed) -> dict:
    from workers.ingest.materialize import materialize_snapshot

    return materialize_snapshot(claimed.payload)


if __name__ == "__main__":
    run_worker(("materialize_snapshot",), {"materialize_snapshot": materialize})
