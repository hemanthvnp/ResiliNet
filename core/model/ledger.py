"""Residual-capacity accounting for the S1/S2 allocator (PLAN.md sections 4, 5 and 7).

Built from the available arcs of a topology with effective capacity
floor(util_cap * capacity) and zero load. `reserve` raises, and changes nothing,
if any arc would exceed its effective capacity, so an allocator bug surfaces at
the point of reservation instead of being clamped away. Reservations are recorded
per priority class so a cut can be attributed to the classes holding it.
"""

from __future__ import annotations

import math
from decimal import Decimal

from core.model.arcs import available_arcs
from core.model.types import Topology


class CapacityExceeded(ValueError):
    """A reservation would push an arc's load above its effective capacity."""


def effective_capacity(capacity: int, util_cap: float) -> int:
    """floor(util_cap * capacity), computed exactly from util_cap's decimal form
    so that, for example, 0.29 * 100 gives 29 and not 28."""
    return math.floor(Decimal(repr(util_cap)) * capacity)


class Ledger:
    def __init__(self, topo: Topology, util_cap: float = 1.0) -> None:
        if not 0 < util_cap <= 1:
            raise ValueError(f"util_cap must be in (0, 1], got {util_cap}")
        arcs = available_arcs(topo)  # sorted by arc id
        self._capacity: dict[str, int] = {a.id: a.capacity for a in arcs}
        self._effective: dict[str, int] = {a.id: effective_capacity(a.capacity, util_cap) for a in arcs}
        self._load: dict[str, int] = {a.id: 0 for a in arcs}
        self._class_load: dict[str, dict[int, int]] = {a.id: {} for a in arcs}

    # --- Queries --------------------------------------------------------------

    @property
    def arcs(self) -> list[str]:
        """Arc ids in the ledger (available arcs only), sorted."""
        return list(self._effective)

    def __contains__(self, arc: str) -> bool:
        return arc in self._effective

    def effective(self, arc: str) -> int:
        return self._effective[arc]

    def load(self, arc: str) -> int:
        return self._load[arc]

    def residual(self, arc: str) -> int:
        return self._effective[arc] - self._load[arc]

    def util(self, arc: str) -> float:
        """Load over raw capacity, u_a = L_a / c_a (section 4). 0.0 for a capacity-0 arc."""
        cap = self._capacity[arc]
        return self._load[arc] / cap if cap else 0.0

    def bottleneck(self, path: list[str]) -> int:
        """Minimum residual over the arcs of the path."""
        self._check_path(path)
        return min(self.residual(a) for a in path)

    def class_breakdown(self, arcs: list[str]) -> dict[int, int]:
        """Load held by each class over the given arcs, classes in ascending order.
        Classes holding nothing are omitted."""
        totals: dict[int, int] = {}
        for arc in sorted(set(arcs)):
            for cls, amount in self._class_load[arc].items():
                totals[cls] = totals.get(cls, 0) + amount
        return {cls: totals[cls] for cls in sorted(totals) if totals[cls]}

    # --- Updates --------------------------------------------------------------

    def reserve(self, path: list[str], rate: int, cls: int) -> None:
        """Add `rate` to every arc of the path for class `cls`.
        Raises CapacityExceeded, changing nothing, if any arc's residual is below `rate`."""
        self._check_path(path)
        self._check_rate(rate)
        short = [a for a in path if self.residual(a) < rate]
        if short:
            raise CapacityExceeded(
                f"reserving {rate} exceeds residual on "
                + ", ".join(f"{a} ({self.residual(a)})" for a in short)
            )
        for a in path:
            self._load[a] += rate
            self._class_load[a][cls] = self._class_load[a].get(cls, 0) + rate

    def release(self, path: list[str], rate: int, cls: int) -> None:
        """Subtract `rate` from every arc of the path for class `cls`.
        Raises ValueError, changing nothing, if class `cls` holds less than `rate` on any arc."""
        self._check_path(path)
        self._check_rate(rate)
        short = [a for a in path if self._class_load[a].get(cls, 0) < rate]
        if short:
            raise ValueError(f"releasing {rate} for class {cls} exceeds its load on {', '.join(short)}")
        for a in path:
            self._load[a] -= rate
            self._class_load[a][cls] -= rate
            if not self._class_load[a][cls]:
                del self._class_load[a][cls]

    # --- Validation -----------------------------------------------------------

    def _check_path(self, path: list[str]) -> None:
        if not path:
            raise ValueError("path is empty")
        if len(set(path)) != len(path):
            raise ValueError(f"path repeats an arc: {path}")
        missing = [a for a in path if a not in self._effective]
        if missing:
            raise KeyError(f"arcs not in ledger (unknown or down): {', '.join(missing)}")

    @staticmethod
    def _check_rate(rate: int) -> None:
        if rate < 0:
            raise ValueError(f"rate must be non-negative, got {rate}")
