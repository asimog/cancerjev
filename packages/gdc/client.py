"""Async, bounded adapter for public GDC APIs."""

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator, Mapping
from typing import Any, Self

import httpx

from packages.gdc.filters import open_project_files

log = logging.getLogger(__name__)

OPEN_FILE_FIELDS = (
    "file_id",
    "file_name",
    "file_size",
    "md5sum",
    "access",
    "data_category",
    "data_type",
    "data_format",
    "experimental_strategy",
    "analysis.workflow_type",
    "cases.case_id",
    "cases.submitter_id",
    "cases.project.project_id",
    "cases.samples.sample_id",
    "cases.samples.submitter_id",
    "cases.samples.sample_type",
    "cases.samples.tumor_descriptor",
    "cases.samples.tissue_type",
    "cases.samples.portions.analytes.aliquots.aliquot_id",
)


class GDCError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status, self.retryable = status, retryable


class GDCResponseError(GDCError):
    pass


class GDCResponseTooLarge(GDCResponseError):
    """A deterministic response-size rejection; callers must not retry it."""


class GDCClient:
    """Transport-only adapter. Secrets and response bodies are never logged."""

    RETRYABLE = {408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30,
        max_connections: int = 8,
        max_retries: int = 4,
        page_size: int = 500,
        max_response_bytes: int = 100_000_000,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self.max_retries, self.page_size = max_retries, page_size
        self.max_response_bytes = max_response_bytes
        self._http = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10)),
            limits=httpx.Limits(
                max_connections=max_connections, max_keepalive_connections=max_connections
            ),
            headers={"User-Agent": "CancerJev/0.2 (research use only)"},
        )

    @classmethod
    def from_settings(cls, settings: Any) -> Self:
        return cls(
            str(settings.gdc_base_url),
            timeout=settings.gdc_timeout_seconds,
            max_connections=settings.gdc_max_connections,
            max_response_bytes=settings.gdc_max_response_bytes,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try:
                log.info("GDC request method=%s path=%s attempt=%d", method, path, attempt + 1)
                request = self._http.build_request(method, path, **kwargs)
                response = await self._http.send(request, stream=True)
                try:
                    declared = response.headers.get("content-length")
                    if declared is not None:
                        try:
                            if int(declared) > self.max_response_bytes:
                                raise GDCResponseTooLarge(
                                    "GDC response exceeds configured byte limit"
                                )
                        except ValueError:
                            pass
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self.max_response_bytes:
                            raise GDCResponseTooLarge("GDC response exceeds configured byte limit")
                    bounded = httpx.Response(
                        response.status_code,
                        headers=response.headers,
                        content=bytes(body),
                        request=response.request,
                    )
                finally:
                    await response.aclose()
                response = bounded
            except GDCResponseTooLarge:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == self.max_retries:
                    raise GDCError("GDC transport failed", retryable=True) from exc
            else:
                if response.status_code not in self.RETRYABLE:
                    if response.is_error:
                        raise GDCError(
                            f"GDC returned HTTP {response.status_code}", status=response.status_code
                        )
                    return response
                if attempt == self.max_retries:
                    raise GDCError(
                        "GDC retry limit exceeded", status=response.status_code, retryable=True
                    )
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    await asyncio.sleep(min(float(retry_after), 60))
                    continue
            await asyncio.sleep(min(0.25 * 2**attempt + random.uniform(0, 0.1), 8))
        raise AssertionError("unreachable")

    async def _json(self, path: str, params: Mapping[str, Any]) -> dict[str, Any]:
        response = await self._request("GET", path, params=params)
        try:
            value = response.json()
        except ValueError as exc:
            raise GDCResponseError("GDC returned malformed JSON") from exc
        if not isinstance(value, dict) or not isinstance(value.get("data"), dict):
            raise GDCResponseError("GDC response is missing data object")
        return value

    async def paginate(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        page_size: int | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Handle GDC's `pagination` metadata; never infer completion from a magic size."""
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive")
        offset, emitted, size = 0, 0, page_size or self.page_size
        while True:
            request_size = min(size, limit - emitted) if limit is not None else size
            query = dict(params or {}) | {"from": offset, "size": request_size, "format": "JSON"}
            payload = await self._json(path, query)
            data, hits = payload["data"], payload["data"].get("hits")
            if not isinstance(hits, list):
                raise GDCResponseError(f"{path} response has no hits list")
            for hit in hits:
                if not isinstance(hit, dict):
                    raise GDCResponseError("GDC hit is not an object")
                yield hit
                emitted += 1
                if limit is not None and emitted >= limit:
                    return
            pagination = data.get("pagination", {})
            total = pagination.get("total")
            if total is not None:
                if offset + len(hits) >= int(total):
                    break
            elif len(hits) < size:
                break
            if not hits:
                raise GDCResponseError("GDC pagination made no progress")
            offset += len(hits)

    async def collect(self, path: str, **kwargs: Any) -> list[dict[str, Any]]:
        return [hit async for hit in self.paginate(path, **kwargs)]

    async def get_projects(self, *, size: int = 100) -> dict[str, Any]:
        if not 1 <= size <= 100:
            raise ValueError("project result limit must be between 1 and 100")
        hits = await self.collect(
            "/projects",
            params={"fields": "project_id,name,primary_site", "sort": "project_id:asc"},
            limit=size,
        )
        return {"data": {"hits": hits, "pagination": {"total": len(hits)}}}

    async def get_open_files(
        self, project_id: str, *, size: int = 500, fields: tuple[str, ...] = OPEN_FILE_FIELDS
    ) -> dict[str, Any]:
        hits = await self.collect(
            "/files",
            params={
                "filters": compact_json(open_project_files(project_id)),
                "fields": ",".join(fields),
            },
            page_size=size,
        )
        return {"data": {"hits": hits, "pagination": {"total": len(hits)}}}

    async def endpoint(self, name: str, *, params: Mapping[str, Any] | None = None) -> list[dict]:
        allowed = {
            "cases",
            "files",
            "genes",
            "ssms",
            "ssm_occurrences",
            "cnvs",
            "cnv_occurrences",
            "segment_cnvs",
            "segment_cnv_occurrences",
        }
        if name not in allowed:
            raise ValueError(f"unsupported GDC endpoint: {name}")
        return await self.collect(f"/{name}", params=params)

    async def gene_expression(self, operation: str, *, params: Mapping[str, Any]) -> dict[str, Any]:
        if operation not in {"availability", "values", "gene_selection"}:
            raise ValueError(operation)
        return await self._json(f"/gene_expression/{operation}", params)

    async def survival(self, *, params: Mapping[str, Any]) -> dict[str, Any]:
        return await self._json("/analysis/survival", params)

    async def manifest(self, file_ids: list[str]) -> bytes:
        response = await self._request("POST", "/manifest", json={"ids": sorted(set(file_ids))})
        return response.content


def compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
