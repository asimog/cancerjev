"""Immutable engine registry: the deterministic dispatch authority.

Engines are registered at import time only. There is no runtime
self-registration, so worker processes and the API resolve the same fixed
scientific capabilities and versions.
"""

from collections.abc import Callable
from dataclasses import dataclass

from scientific.crossmodal.analysis import EngineContext, analyze_cnv_rna


@dataclass(frozen=True)
class EngineSpec:
    engine: str
    engine_version: str
    method_version: str
    #: Engine callable parameter names, in the engine's call order.
    inputs: tuple[str, ...]
    #: Canonical modality feeding each engine input, same order as `inputs`.
    modalities: tuple[str, ...]
    run: Callable[..., list]


#: engine name -> spec; resolved by (engine, engine_version) pairs.
ENGINES: dict[str, EngineSpec] = {
    "cnv_rna": EngineSpec(
        engine="cnv_rna",
        engine_version="1",
        method_version="cnv-rna-v1",
        inputs=("cnv_rows", "rna_rows"),
        modalities=("cnv", "expression"),
        run=analyze_cnv_rna,
    ),
}


def resolve_engine(engine: str, engine_version: str) -> EngineSpec:
    spec = ENGINES.get(engine)
    if spec is None or spec.engine_version != engine_version:
        raise ValueError(f"unsupported engine or version: {engine}/{engine_version}")
    return spec


__all__ = ["ENGINES", "EngineSpec", "EngineContext", "resolve_engine"]
