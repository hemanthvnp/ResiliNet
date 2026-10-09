"""One-line explanation from a fixed template over record fields (PLAN.md section 10)."""

from collections.abc import Sequence

from core.model.arcs import parse_arc_id
from core.model.types import CutArc, DecisionRecord


def rate_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.2f}"


def arc_nodes(arc_id: str) -> tuple[str, str]:
    _, u, v = parse_arc_id(arc_id)
    return u, v


def path_text(arcs: Sequence[str]) -> str:
    nodes = [arc_nodes(arcs[0])[0]] + [arc_nodes(a)[1] for a in arcs]
    return "-".join(nodes)


def link_of(arc_id: str) -> str:
    return parse_arc_id(arc_id)[0]


def _reference_segment(record: DecisionRecord) -> str:
    if not record.reference_path:
        return ""
    path = path_text(record.reference_path)
    status = record.reference_status
    if status == "USED":
        return f"path {path} used."
    if status.startswith("INVALID: "):
        link = status[len("INVALID: "):].removesuffix(" down")
        return f"path {path} invalid ({link} down)."
    if status.startswith("PARTIAL: "):
        arc = status[len("PARTIAL: "):].removesuffix(" saturated")
        return f"path {path} limited by {link_of(arc)} (saturated)."
    return ""


def _attempt_segments(record: DecisionRecord) -> list[str]:
    verb = "Moved" if record.previous else "Placed"
    return [
        f"{verb} {rate_text(a.pushed)} Mbps to {path_text(a.arcs)} (latency {rate_text(a.latency)} ms)."
        for a in record.attempts
        if a.pushed > 0
    ]


def _cut_text(cut: Sequence[CutArc]) -> str:
    saturated = [c for c in cut if c.state == "saturated"]
    if not saturated:
        return "cut " + ", ".join(link_of(c.arc) for c in cut) + " down"
    parts = []
    for c in saturated:
        by = ", ".join(f"P{cls} ({rate_text(rate)} Mbps)" for cls, rate in sorted(c.load_by_class.items()))
        parts.append(f"{link_of(c.arc)} saturated" + (f" by {by}" if by else ""))
    return "cut " + "; ".join(parts)


def _unserved_segment(record: DecisionRecord) -> str:
    if record.unserved <= 0:
        return ""
    unserved = rate_text(record.unserved)
    if record.cause == "DISCONNECTED":
        return f"{unserved} Mbps unserved: destination unreachable."
    if record.cause == "OVERLOAD_LOSS":
        return f"{unserved} Mbps lost to overload."
    if record.greedy_gap is not None and record.greedy_gap > 0:
        return (
            f"{unserved} Mbps unserved, of which {rate_text(record.greedy_gap)} Mbps "
            "could have been routed (heuristic or path limit)."
        )
    if record.greedy_gap == 0 and record.cut:
        return f"{unserved} Mbps unserved: {_cut_text(record.cut)}."
    return f"{unserved} Mbps unserved."


def explain(record: DecisionRecord) -> str:
    header = f"{record.flow_id} (P{record.cls}, {rate_text(record.demand)} Mbps):"
    segments = [_reference_segment(record), *_attempt_segments(record), _unserved_segment(record)]
    return " ".join([header, *[s for s in segments if s]])
