"""Stand-in for the Ledger that B owns (core/model/ledger.py, add-core-model-contract).

It has the method names PLAN.md section 7 lists, so the allocator can be written and tested
before B's code exists. Delete this module once B's Ledger is merged and point the allocator at
it. Two assumptions to confirm with B: `reserve` and `release` take the flow's class (the
section 7 signature has none, but `class_breakdown` needs it), and the constructor takes the
arcs and `util_cap`.
"""

from collections.abc import Iterable, Sequence
from fractions import Fraction
from math import floor

from core.routing.inputs import ArcSpec


class SimpleLedger:
    def __init__(self, arcs: Iterable[ArcSpec], util_cap: float = 1.0):
        rho = Fraction(repr(util_cap))  # exact, so floor(0.29 * 100) is 29 and not 28
        self._capacity = {a.id: floor(rho * a.capacity) for a in arcs if a.up}
        self._by_class: dict[str, dict[int, int]] = {arc_id: {} for arc_id in self._capacity}

    def _load(self, arc_id: str) -> int:
        return sum(self._by_class[arc_id].values())

    def residual(self, arc_id: str) -> int:
        return self._capacity[arc_id] - self._load(arc_id)

    def bottleneck(self, path: Sequence[str]) -> int:
        return min(self.residual(a) for a in path)

    def reserve(self, path: Sequence[str], rate: int, cls: int) -> None:
        if rate < 0 or any(self.residual(a) < rate for a in path):
            raise ValueError(f"cannot reserve {rate} on {list(path)}")
        for a in path:
            self._by_class[a][cls] = self._by_class[a].get(cls, 0) + rate

    def release(self, path: Sequence[str], rate: int, cls: int) -> None:
        if rate < 0 or any(self._by_class[a].get(cls, 0) < rate for a in path):
            raise ValueError(f"cannot release {rate} from {list(path)}")
        for a in path:
            self._by_class[a][cls] -= rate

    def class_breakdown(self, arcs: Iterable[str]) -> dict[int, int]:
        total: dict[int, int] = {}
        for a in arcs:
            for cls, rate in self._by_class[a].items():
                if rate:
                    total[cls] = total.get(cls, 0) + rate
        return dict(sorted(total.items()))
