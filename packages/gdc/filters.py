from typing import Any

from packages.gdc.policy import open_filter


def equals(field: str, value: Any) -> dict[str, Any]:
    return {"op": "=", "content": {"field": field, "value": value}}


def and_(*filters: dict[str, Any]) -> dict[str, Any]:
    return {"op": "and", "content": list(filters)}


def open_project_files(project_id: str) -> dict[str, Any]:
    """The non-overridable V1 access boundary for project file discovery."""
    return open_filter(equals("cases.project.project_id", project_id))
