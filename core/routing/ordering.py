"""Order in which the allocator places flows (PLAN.md section 5)."""

from collections.abc import Sequence

from core.model.types import Flow

ORDERS = ("arrival", "class_size_desc", "class_size_asc")


def order_flows(flows: Sequence[Flow], order: str) -> list[Flow]:
    """`arrival` keeps the input order and ignores class. The others sort by class (P0 first),
    then rate, then flow id, so equal flows never depend on input order."""
    if order == "arrival":
        return list(flows)
    if order == "class_size_desc":
        return sorted(flows, key=lambda f: (f.cls, -f.rate, f.id))
    if order == "class_size_asc":
        return sorted(flows, key=lambda f: (f.cls, f.rate, f.id))
    raise ValueError(f"unknown order {order!r}; expected one of {ORDERS}")
