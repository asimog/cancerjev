"""Source-only overall survival endpoint; missingness is never an event or duration."""

import math

ENDPOINT_VERSION = "gdc-overall-survival-v1"


def endpoint(record: dict):
    status = (record.get("vital_status") or "").lower()
    death, follow = record.get("days_to_death"), record.get("days_to_last_follow_up")
    if status == "dead":
        value, event = death, True
        if death is not None and follow is not None and follow > death:
            return None, "follow_up_after_death"
    elif status == "alive":
        if death is not None:
            return None, "alive_with_death_time"
        value, event = follow, False
    else:
        return None, "unknown_vital_status"
    if value is None or not math.isfinite(value) or value < 0:
        return None, "missing_or_invalid_duration"
    return (float(value), event), None
