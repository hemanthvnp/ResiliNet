"""Plain record types mirroring Attempt, CutArc and DecisionRecord of PLAN.md section 7.

Stand-ins until core/model/types.py exists: `to_dict` gives the JSON shape of the section 10
fixture, so the pydantic model can be built from it with `DecisionRecord(**record.to_dict())`.
"""

from dataclasses import dataclass

from core.routing.inputs import PathRate


@dataclass(frozen=True)
class Attempt:
    iter: int
    arcs: tuple[str, ...]
    cost: int
    latency: int
    bottleneck: int
    pushed: int


@dataclass(frozen=True)
class CutArc:
    arc: str
    state: str  # saturated | down
    load_by_class: dict[int, int]


@dataclass
class DecisionRecordData:
    flow_id: str
    cls: int
    demand: int
    step: int
    failed_links: tuple[str, ...]
    previous: tuple[PathRate, ...]
    reference_path: tuple[str, ...]
    reference_status: str
    attempts: tuple[Attempt, ...]
    delivered: float
    unserved: float
    cause: str
    cut: tuple[CutArc, ...]
    maxflow_bound: int | None
    greedy_gap: float | None
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "cls": self.cls,
            "demand": self.demand,
            "step": self.step,
            "failed_links": list(self.failed_links),
            "previous": [{"arcs": list(p.arcs), "rate": p.rate} for p in self.previous],
            "reference_path": list(self.reference_path),
            "reference_status": self.reference_status,
            "attempts": [
                {"iter": a.iter, "arcs": list(a.arcs), "cost": a.cost, "latency": a.latency,
                 "bottleneck": a.bottleneck, "pushed": a.pushed}
                for a in self.attempts
            ],
            "delivered": self.delivered,
            "unserved": self.unserved,
            "cause": self.cause,
            "cut": [
                {"arc": c.arc, "state": c.state, "load_by_class": {str(k): v for k, v in c.load_by_class.items()}}
                for c in self.cut
            ],
            "maxflow_bound": self.maxflow_bound,
            "greedy_gap": self.greedy_gap,
            "explanation": self.explanation,
        }
