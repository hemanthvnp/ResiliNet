"""Result type of topology resolution, shared by the registry and the generators."""

from __future__ import annotations

from dataclasses import dataclass

from core.model.types import Topology


@dataclass(frozen=True)
class ResolvedTopology:
    topology: Topology
    primary_uplink: str | None  # link id failed by the path check and scenario 2
    seed: int | None  # seed actually used; differs from the spec's after a generator retry
