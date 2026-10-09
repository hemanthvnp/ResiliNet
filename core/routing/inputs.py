"""Plain input and output types for the routing code.

Field names mirror the section 7 contract (Flow, PathAlloc, FlowResult, PolicyConfig) so that
an adapter over the pydantic models in core/model/types.py is a field-for-field copy. Nothing
here imports core/model.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArcSpec:
    id: str  # "L7:u>v"
    u: str
    v: str
    capacity: int
    latency: int
    up: bool = True

    @property
    def link_id(self) -> str:
        return self.id.split(":", 1)[0]


@dataclass(frozen=True)
class FlowSpec:
    id: str
    src: str
    dst: str
    rate: int
    cls: int  # 0 = P0


@dataclass(frozen=True)
class PathRate:
    arcs: tuple[str, ...]
    rate: int


@dataclass(frozen=True)
class AllocConfig:
    order: str = "class_size_desc"  # arrival | class_size_desc | class_size_asc
    max_paths: int = 3
    congestion_lambda: int = 0
    util_cap: float = 1.0

    def __post_init__(self):
        if self.order not in ("arrival", "class_size_desc", "class_size_asc"):
            raise ValueError(f"unknown order {self.order!r}")
        if self.max_paths < 1:
            raise ValueError("max_paths must be at least 1")
        if self.congestion_lambda < 0:
            raise ValueError("congestion_lambda must not be negative")
        if not 0 < self.util_cap <= 1:
            raise ValueError("util_cap must be in (0, 1]")


@dataclass
class FlowOutcome:
    flow_id: str
    paths: tuple[PathRate, ...]
    delivered: float
    unserved: float
    cause: str  # NONE | DISCONNECTED | INSUFFICIENT_CAPACITY | PATH_LIMIT | OVERLOAD_LOSS


@dataclass
class RouteResult:
    outcomes: dict[str, FlowOutcome]  # in placement order
    arc_load: dict[str, int]  # arcs with load above zero, sorted by arc id
    records: list = field(default_factory=list)  # DecisionRecordData, in placement order


def validate_flows(flows) -> None:
    """Flow ids must be unique (one record per flow) and rates must not be negative."""
    seen: set[str] = set()
    for f in flows:
        if f.id in seen:
            raise ValueError(f"duplicate flow id {f.id!r}")
        seen.add(f.id)
        if f.rate < 0:
            raise ValueError(f"flow {f.id!r} has a negative rate")


def available_tuples(arcs, value) -> list[tuple[str, str, str, int]]:
    """(arc_id, u, v, value(arc)) for every available arc, in the form pathfinder takes."""
    return [(a.id, a.u, a.v, value(a)) for a in sorted(arcs, key=lambda a: a.id) if a.up]
