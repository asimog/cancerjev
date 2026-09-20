"""Remote BAM slicing for targeted genomic regions — no full BAM download needed."""

import logging

import httpx

log = logging.getLogger(__name__)


class BAMSlicingError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        self.status = status
        super().__init__(message)


class GDCBAMSlicingClient:
    """Slice open-access BAM files by gene or genomic region via the GDC slicing endpoint.

    The GDC API supports remote BAM slicing at /slicing/view/{uuid}.
    No X-Auth-Token is required for open-access BAMs.
    Returns a BAM-formatted byte stream containing header + overlapping alignment records.
    A request with no region returns only the BAM header (small, useful for reference inspection).
    """

    BASE = "https://api.gdc.cancer.gov/slicing/view"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._http = client or httpx.AsyncClient(
            base_url=self.BASE,
            timeout=httpx.Timeout(120.0, connect=10.0),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=4),
            headers={"User-Agent": "CancerJev/0.2 (research use only)"},
        )

    async def slice_by_region(
        self, file_uuid: str, regions: list[str], max_bytes: int = 50 * 1024 * 1024
    ) -> bytes:
        """Slice an open-access BAM by chromosomal regions.

        regions: ['chr1', 'chr2:10000', 'chr3:10000-20000', 'unmapped']
        Returns BAM bytes (header + overlapping records).
        """
        return await self._slice(file_uuid, params={"region": regions}, max_bytes=max_bytes)

    async def slice_by_gene(
        self, file_uuid: str, genes: list[str], max_bytes: int = 50 * 1024 * 1024
    ) -> bytes:
        """Slice an open-access BAM by HGNC/GENCODE v36 gene symbols.

        genes: ['BRCA1', 'EGFR', 'TP53']
        Returns BAM bytes (header + overlapping records).
        """
        return await self._slice(file_uuid, params={"gencode": genes}, max_bytes=max_bytes)

    async def header_only(self, file_uuid: str) -> bytes:
        """Retrieve only the BAM header (no region/gene specified)."""
        return await self._get(f"/{file_uuid}", max_bytes=5 * 1024 * 1024)

    async def _slice(self, file_uuid: str, params: dict, max_bytes: int) -> bytes:
        if not file_uuid or len(file_uuid) != 36:
            raise ValueError(f"invalid file UUID: {file_uuid}")
        query = "&".join(f"{k}={v}" for k, values in params.items() for v in values)
        return await self._get(f"/{file_uuid}?{query}", max_bytes)

    async def _get(self, path: str, max_bytes: int) -> bytes:
        response = await self._http.get(path)
        if response.is_error:
            raise BAMSlicingError(
                f"BAM slicing failed: HTTP {response.status_code}",
                status=response.status_code,
            )
        body = response.content
        if len(body) > max_bytes:
            raise BAMSlicingError(f"BAM slice exceeds {max_bytes} bytes")
        return body

    async def aclose(self) -> None:
        await self._http.aclose()