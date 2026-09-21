"""Async, bounded adapter for public GDC APIs."""

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator, Mapping
from typing import Any, Self
from uuid import UUID

import httpx

from packages.gdc.filters import open_project_files
from packages.gdc.policy import (
    GDC_API,
    GDCUnavailableAccess,
    official_api,
    open_filter,
    require_open,
)
from packages.schemas.snapshot import SnapshotRecord

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
    "cases.samples.portions.analytes.aliquots.submitter_id",
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
        self.base_url = official_api(base_url)
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
            trust_env=False,
        )
        if self._http.auth is not None:
            raise ValueError("GDC authentication is not permitted")

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

    async def _request(
        self, method: str, path: str, *, max_response_bytes: int | None = None, **kwargs: Any
    ) -> httpx.Response:
        response_limit = min(self.max_response_bytes, max_response_bytes or self.max_response_bytes)
        for attempt in range(self.max_retries + 1):
            try:
                log.info("GDC request method=%s path=%s attempt=%d", method, path, attempt + 1)
                request = self._http.build_request(method, self.base_url + path, **kwargs)
                if any(h in request.headers for h in ("x-auth-token", "authorization", "cookie")):
                    raise ValueError("GDC authentication headers are not permitted")
                response = await self._http.send(request, stream=True, follow_redirects=False)
                try:
                    declared = response.headers.get("content-length")
                    if declared is not None:
                        try:
                            if int(declared) > response_limit:
                                raise GDCResponseTooLarge(
                                    "GDC response exceeds configured byte limit"
                                )
                        except ValueError:
                            pass
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > response_limit:
                            raise GDCResponseTooLarge("GDC response exceeds configured byte limit")
                    # aiter_bytes has decoded transport compression already. Retaining the
                    # original encoding would decompress the bounded body a second time.
                    headers = {
                        key: value
                        for key, value in response.headers.items()
                        if key not in {"content-encoding", "content-length", "transfer-encoding"}
                    }
                    bounded = httpx.Response(
                        response.status_code,
                        headers=headers,
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
                    if response.status_code in (401, 403):
                        # Authorization outcomes are permanent public-access
                        # failures; never retry and never seek credentials.
                        raise GDCUnavailableAccess(
                            "GDC authorization failure; only anonymous public open access"
                            " is supported"
                        )
                    if response.is_error or response.is_redirect:
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

    async def _json(
        self, path: str, params: Mapping[str, Any], *, max_response_bytes: int | None = None
    ) -> dict[str, Any]:
        response = await self._request(
            "GET", path, params=params, max_response_bytes=max_response_bytes
        )
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
        if path not in {"/projects", "/cases", "/files"}:
            raise ValueError("unsupported GDC discovery endpoint")
        params = dict(params or {})
        if path == "/files":
            caller_filter = params.get("filters")
            if isinstance(caller_filter, str):
                caller_filter = json.loads(caller_filter)
            if caller_filter is not None and not isinstance(caller_filter, dict):
                raise ValueError("GDC filters must be an object")
            params["filters"] = compact_json(open_filter(caller_filter))
            fields = set(str(params.get("fields", ",".join(OPEN_FILE_FIELDS))).split(",")) - {""}
            params["fields"] = ",".join(sorted(fields | {"access"}))
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
                if path == "/files":
                    require_open(hit.get("access"))
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

    async def clinical_pages(self, case_ids: tuple[str, ...]):
        """Yield bounded official cases pages for frozen UUIDs and acquisition provenance."""
        from datetime import UTC, datetime

        from packages.gdc.parsers import MAX_CLINICAL_BYTES, canonical_json

        if self.base_url != GDC_API:
            raise ValueError("clinical acquisition requires the official GDC API")
        ordered = sorted(set(case_ids))
        for start in range(0, len(ordered), 100):
            selected = ordered[start : start + 100]
            query = {
                "filters": compact_json(
                    {
                        "op": "in",
                        "content": {
                            "field": "case_id",
                            "value": selected,
                        },
                    }
                ),
                "expand": "demographic,diagnoses,diagnoses.follow_ups,exposures",
                "sort": "case_id:asc",
                "size": len(selected),
                "from": 0,
                "format": "JSON",
            }
            seen = set()
            while True:
                page = await self._json("/cases", query, max_response_bytes=MAX_CLINICAL_BYTES)
                encoded = canonical_json(page).encode("utf-8")
                if len(encoded) > MAX_CLINICAL_BYTES:
                    raise GDCResponseTooLarge("clinical page exceeds parser byte limit")
                hits = page["data"].get("hits")
                if not isinstance(hits, list):
                    raise GDCResponseError("clinical response lacks hits")
                for hit in hits:
                    case_id = hit.get("case_id") if isinstance(hit, dict) else None
                    if case_id not in selected or case_id in seen:
                        raise GDCResponseError("clinical response identity mismatch")
                    seen.add(case_id)
                total = int(page["data"].get("pagination", {}).get("total", len(hits)))
                if total > len(selected):
                    raise GDCResponseError("clinical response exceeds requested case membership")
                if not hits and query["from"] < total:
                    raise GDCResponseError("clinical pagination made no progress")
                yield (
                    encoded,
                    {
                        "endpoint": self.base_url + "/cases",
                        "query": dict(query),
                        "acquired_at": datetime.now(UTC).isoformat(),
                        "acquisition_version": "gdc-cases-pages-v1",
                    },
                )
                query["from"] += len(hits)
                if query["from"] >= total:
                    if seen != set(selected):
                        raise GDCResponseError("clinical response missing frozen cases")
                    break

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
        allowed = {"projects", "cases", "files"}
        if name not in allowed:
            raise ValueError(f"unsupported GDC endpoint: {name}")
        return await self.collect(f"/{name}", params=params)

    async def _document(self, method: str, path: str, **kwargs: Any) -> dict | list:
        response = await self._request(method, path, **kwargs)
        try:
            value = response.json()
        except ValueError as exc:
            raise GDCResponseError("GDC returned malformed JSON") from exc
        if not isinstance(value, (dict, list)):
            raise GDCResponseError("GDC returned an invalid document")
        return value

    async def status(self) -> dict:
        value = await self._document("GET", "/status")
        if (
            not isinstance(value, dict)
            or type(value.get("version")) not in (str, int)
            or not str(value["version"])
            or not isinstance(value.get("data_release"), str)
            or not value["data_release"]
        ):
            raise GDCResponseError("GDC status lacks API version/data release")
        return value

    async def file_versions(self, file_ids: list[str]) -> dict | list:
        ids = sorted({str(UUID(value)) for value in file_ids})
        if not 1 <= len(ids) <= 100:
            raise ValueError("version lookup requires between 1 and 100 UUIDs")
        return await self._document("GET", "/files/versions/" + ",".join(ids))

    async def history(self, uuid: str) -> dict | list:
        return await self._document("GET", f"/history/{UUID(uuid)}")

    async def mapping(self, endpoint: str) -> dict | list:
        if endpoint not in {"projects", "cases", "files"}:
            raise ValueError("unsupported GDC mapping endpoint")
        return await self._document("GET", f"/{endpoint}/_mapping")

    async def manifest(self, snapshot: SnapshotRecord, file_ids: list[str] | None = None) -> bytes:
        """Internal adapter contract: use a snapshot resolved by the resource service."""
        from packages.gdc.manifest import validate_manifest

        if not isinstance(snapshot, SnapshotRecord):
            raise ValueError("manifest requires a frozen snapshot")
        official_api(snapshot.source_api)
        for item in snapshot.objects:
            require_open(item.access)
        allowed = {item.file_id: item for item in snapshot.objects}
        selected = sorted(allowed if file_ids is None else set(file_ids))
        if not selected or not set(selected).issubset(allowed):
            raise ValueError("manifest IDs must be a nonempty frozen open snapshot subset")
        response = await self._request("POST", "/manifest", json={"ids": selected})
        validate_manifest(response.content, [allowed[key] for key in selected])
        return response.content


def compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
