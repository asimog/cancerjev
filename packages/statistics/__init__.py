"""Deterministic statistical leaf primitives.

The engine registry is deliberately NOT re-exported here: importing a leaf
module must not initialize the scientific engines (or the reverse), so the
registry is imported explicitly where dispatch happens
(packages.resources.execution, workers).
"""

from packages.statistics.core import benjamini_hochberg
from packages.statistics.crossmodal import cnv_expression, mutation_expression

__all__ = [
    "benjamini_hochberg",
    "cnv_expression",
    "mutation_expression",
]
