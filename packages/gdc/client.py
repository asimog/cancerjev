from collections.abc import Mapping
from typing import Any, Self

import httpx

from packages.gdc.filters import open_project_files


class GDCClient:
    """Small async adapter around supported public GDC REST endpoints."""

    def __init__(self, base_url: str, *, timeout: float = 30, max_connections: int = 8):
        self.base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_connections,
            ),
            headers={"User-Agent": "CancerJev/0.1 (research use only)"},
        )

    @classmethod
    def from_settings(cls, settings: Any) -> Self:
        return cls(
            str(settings.gdc_base_url),
            timeout=settings.gdc_timeout_seconds,
            max_connections=settings.gdc_max_connections,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: Mapping[str, Any]) -> dict[str, Any]:
        response = await self._http.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def get_projects(self, *, size: int = 20) -> dict[str, Any]:
        return await self._get(
            "/projects",
            {"format": "JSON", "size": size, "fields": "project_id,name,primary_site"},
        )

    async def get_open_files(self, project_id: str, *, size: int = 10_000) -> dict[str, Any]:
        return await self._get(
            "/files",
            {
                "format": "JSON",
                "size": size,
                "filters": _compact_json(open_project_files(project_id)),
                "fields": (
                    "file_id,file_name,file_size,md5sum,access,data_type,data_format,"
                    "cases.case_id,cases.samples.sample_id"
                ),
            },
        )


def _compact_json(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))
