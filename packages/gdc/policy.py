"""Single production authority and access policy for GDC V1."""

from typing import Any

GDC_API = "https://api.gdc.cancer.gov"
SOURCE_POLICY_VERSION = "official-gdc-open-v1"

#: Terminal reason code shared with the bounded job failure-reason contract.
UNAVAILABLE_ACCESS = "UNAVAILABLE_ACCESS"


class GDCUnavailableAccess(RuntimeError):
    """Terminal public-access boundary failure.

    A GDC authorization/access-policy outcome is permanent: no credential
    seeking, authenticated retry, or broader acquisition may follow it.
    """

    retryable = False
    failure_reason = UNAVAILABLE_ACCESS


def official_api(value: str) -> str:
    if value.rstrip("/") != GDC_API:
        raise ValueError("production scientific sources require the official GDC API host")
    return GDC_API


def require_open(access: Any) -> None:
    if access != "open":
        raise ValueError(
            "controlled file or missing/unknown access rejected; explicit open required"
        )


def open_filter(caller_filter: dict | None = None) -> dict:
    required = {"op": "=", "content": {"field": "files.access", "value": "open"}}
    return {"op": "and", "content": [required, caller_filter] if caller_filter else [required]}
