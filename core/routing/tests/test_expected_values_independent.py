"""Cross-check of the hand-worked expected values by a second, independent route.

The three expected-value files (expected_diamond.json, expected_cases.json and
core/explain/tests/expected_records.json) were worked by hand. This test recomputes every value
from the PLAN.md definitions with code that shares nothing with core/routing or core/explain:

- paths by brute-force enumeration of every simple path, ordered by (cost, hops, node ids),
  instead of Dijkstra;
- max flow by a plain Edmonds-Karp, and checked against an exhaustive min cut over all node
  subsets, instead of networkx;
- S0 and S0-QoS with exact fractions, and the greedy of PLAN.md section 5 written from its
  pseudocode.

It reads only the JSON files. If one of them is wrong, or the production code and the files agree
on a wrong value, this fails. It is written by the same author as the files, so it does not replace
A checking the numbers; it removes the risk that the code and the files were tuned to each other.
"""

import itertools
import json
import math
from collections import deque
from fractions import Fraction
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
FILES = {
    "diamond": HERE / "expected_diamond.json",
    "cases": HERE / "expected_cases.json",
    "records": HERE.parents[1] / "explain" / "tests" / "expected_records.json",
}

DIAMOND = [("L_AB", "A", "B", 10, 1), ("L_BD", "B", "D", 10, 1), ("L_AC", "A", "C", 10, 2), ("L_CD", "C", "D", 10, 2)]
FLOWS = [
    {"id": "F1", "src": "A", "dst": "D", "rate": 15, "cls": 0},
    {"id": "F2", "src": "A", "dst": "D", "rate": 10, "cls": 2},
]


def load_all() -> dict[str, dict]:
    return {name: json.loads(path.read_text(encoding="utf-8")) for name, path in FILES.items()}


# --- a small model, written from PLAN.md sections 4 and 5 ---------------------------------


def make_arcs(links, down=()):
    """{(u, v): arc} for both directions of every link."""
    arcs = {}
    for link_id, u, v, cap, lat in links:
        for a, b in ((u, v), (v, u)):
            arcs[(a, b)] = {"id": f"{link_id}:{a}>{b}", "cap": cap, "lat": lat, "up": link_id not in down}
    return arcs


def best_path(arcs, src, dst, usable):
    """The path with the smallest (cost, hops, node ids) over every simple path, or None."""
    found = []

    def walk(node, nodes, cost):
        if node == dst:
            found.append((cost, len(nodes) - 1, tuple(nodes)))
            return
        for (a, b), arc in arcs.items():
            if a == node and b not in nodes and usable((a, b), arc):
                walk(b, [*nodes, b], cost + arc["lat"])

    walk(src, [src], 0)
    return min(found)[2] if found else None


def hops(path):
    return list(zip(path, path[1:], strict=False))


def max_flow(capacity, src, dst):
    """Edmonds-Karp on {(u, v): capacity}."""
    residual = dict(capacity)
    for u, v in capacity:
        residual.setdefault((v, u), 0)
    total = 0
    while True:
        parent = {src: None}
        queue = deque([src])
        while queue and dst not in parent:
            u = queue.popleft()
            for (a, b), cap in residual.items():
                if a == u and cap > 0 and b not in parent:
                    parent[b] = a
                    queue.append(b)
        if dst not in parent:
            return total
        edges, node = [], dst
        while parent[node] is not None:
            edges.append((parent[node], node))
            node = parent[node]
        push = min(residual[e] for e in edges)
        for a, b in edges:
            residual[(a, b)] -= push
            residual[(b, a)] += push
        total += push


def min_cut_by_subsets(capacity, src, dst):
    """The smallest capacity leaving any node set that holds src and not dst."""
    nodes = sorted({n for edge in capacity for n in edge} - {src, dst})
    best = None
    for size in range(len(nodes) + 1):
        for subset in itertools.combinations(nodes, size):
            inside = {src, *subset}
            value = sum(c for (a, b), c in capacity.items() if a in inside and b not in inside)
            best = value if best is None else min(best, value)
    return best


def greedy(arcs, flows, max_paths=3, util_cap=Fraction(1)):
    """PLAN.md section 5: flows in class-then-size order, repeated shortest pushes on the residuals."""
    effective = {e: math.floor(util_cap * a["cap"]) for e, a in arcs.items() if a["up"]}
    load = dict.fromkeys(effective, 0)
    by_class: dict[tuple[str, str], dict[int, int]] = {e: {} for e in effective}
    results = {}
    for f in sorted(flows, key=lambda f: (f["cls"], -f["rate"], f["id"])):
        src, dst, remaining = f["src"], f["dst"], f["rate"]
        paths: list[tuple[tuple[str, ...], int]] = []

        def open_arc(e, arc):
            return arc["up"] and effective[e] - load[e] > 0

        if best_path(arcs, src, dst, lambda e, arc: arc["up"]) is None:
            results[f["id"]] = {"paths": [], "delivered": 0, "unserved": remaining, "cause": "DISCONNECTED"}
            continue
        while remaining > 0 and len(paths) < max_paths:
            path = best_path(arcs, src, dst, open_arc)
            if path is None:
                break
            push = min(remaining, *(effective[e] - load[e] for e in hops(path)))
            for e in hops(path):
                load[e] += push
                by_class[e][f["cls"]] = by_class[e].get(f["cls"], 0) + push
            paths.append((path, push))
            remaining -= push
        cause = "NONE"
        if remaining > 0:
            reachable = best_path(arcs, src, dst, open_arc)
            cause = "PATH_LIMIT" if reachable else "INSUFFICIENT_CAPACITY"
        results[f["id"]] = {
            "paths": paths,
            "delivered": f["rate"] - remaining,
            "unserved": remaining,
            "cause": cause,
            "post": {e: effective[e] - load[e] for e in effective},
            "by_class": {e: dict(c) for e, c in by_class.items()},
        }
    return results, load


def bound_gap_cut(arcs, flow, result):
    """Bound from the residuals before this flow was placed, gap, and the residual cut after it."""
    own: dict[tuple[str, str], int] = {}
    for path, push in result["paths"]:
        for e in hops(path):
            own[e] = own.get(e, 0) + push
    before = {e: r + own.get(e, 0) for e, r in result["post"].items()}
    bound = min(flow["rate"], max_flow(before, flow["src"], flow["dst"]))
    reach = {flow["src"]}
    queue = deque([flow["src"]])
    while queue:
        u = queue.popleft()
        for (a, b), r in result["post"].items():
            if a == u and r > 0 and b not in reach:
                reach.add(b)
                queue.append(b)
    cut = []
    if result["cause"] == "INSUFFICIENT_CAPACITY":
        for e, arc in arcs.items():
            if e[0] in reach and e[1] not in reach:
                load = result["by_class"].get(e, {}) if arc["up"] else {}
                cut.append(
                    {
                        "arc": arc["id"],
                        "state": "saturated" if arc["up"] else "down",
                        "load_by_class": {str(k): v for k, v in sorted(load.items())},
                    }
                )
    return bound, float(bound - result["delivered"]), sorted(cut, key=lambda c: c["arc"])


def baselines(arcs, flows, qos):
    """S0 or S0-QoS: shortest routes, offered load, and the single-pass scale of each flow."""
    routes = {f["id"]: best_path(arcs, f["src"], f["dst"], lambda e, arc: arc["up"]) for f in flows}
    load: dict[tuple[str, str], int] = {}
    class_load: dict[tuple[tuple[str, str], int], int] = {}
    for f in flows:
        for e in hops(routes[f["id"]] or ()):
            load[e] = load.get(e, 0) + f["rate"]
            class_load[(e, f["cls"])] = class_load.get((e, f["cls"]), 0) + f["rate"]
    delivered = {}
    for f in flows:
        route = routes[f["id"]]
        scale = Fraction(1)
        for e in hops(route or ()):
            cap = arcs[e]["cap"]
            if qos:
                higher = sum(v for (edge, cls), v in class_load.items() if edge == e and cls < f["cls"])
                scale = min(scale, Fraction(max(0, cap - higher), class_load[(e, f["cls"])]), Fraction(1))
            else:
                scale = min(scale, Fraction(cap, load[e]), Fraction(1))
        delivered[f["id"]] = (route, Fraction(0) if route is None else f["rate"] * scale)
    return delivered, load


# --- the comparison -----------------------------------------------------------------------


def mismatches(data: dict[str, dict]) -> tuple[int, list[tuple]]:
    """Recompute every value in the three files; return the number of checks and the differences."""
    found: list[tuple] = []
    count = 0

    def check(name, got, want):
        nonlocal count
        count += 1
        if got != want:
            found.append((name, got, want))

    diamond, cases, records = data["diamond"], data["cases"], data["records"]

    for case, down in (("healthy", ()), ("bd_failed", ("L_BD",))):
        arcs = make_arcs(DIAMOND, down)
        for policy, qos in (("S0", False), ("S0-QoS", True)):
            want = diamond["cases"][case][policy]
            delivered, load = baselines(arcs, FLOWS, qos)
            for fid, value in want["delivered"].items():
                check(f"{case}/{policy}/{fid} delivered", float(delivered[fid][1]), float(value))
                check(f"{case}/{policy}/{fid} path", list(delivered[fid][0]), want["paths"][fid][0])
            if "arc_load" in want:
                check(f"{case}/{policy} arc_load", {arcs[e]["id"]: v for e, v in load.items()}, want["arc_load"])
            check(f"{case}/{policy} dr_total", float(sum(d for _, d in delivered.values()) / 25), want["dr_total"])
            p0 = delivered["F1"][1] / 15
            if "dr_p0" in want:
                check(f"{case}/{policy} dr_p0", float(p0), want["dr_p0"])
            if "dr_p0_fraction" in want:
                check(f"{case}/{policy} dr_p0", p0, Fraction(want["dr_p0_fraction"]))
            over = [load[e] - arcs[e]["cap"] for e in load if load[e] > arcs[e]["cap"]]
            if want.get("overloaded_arcs") is not None:
                check(f"{case}/{policy} overloaded arcs", len(over), want["overloaded_arcs"])
            if "excess" in want:
                check(f"{case}/{policy} excess", sum(over), want["excess"])
            for fid, cause in want.get("cause", {}).items():
                rate = next(f["rate"] for f in FLOWS if f["id"] == fid)
                check(f"{case}/{policy}/{fid} cause", "OVERLOAD_LOSS" if delivered[fid][1] < rate else "NONE", cause)
        want = diamond["cases"][case]["S2"]
        results, load = greedy(arcs, FLOWS)
        for fid in ("F1", "F2"):
            check(f"{case}/S2/{fid} paths", [list(p) for p, _ in results[fid]["paths"]], want["paths"][fid])
            check(f"{case}/S2/{fid} rates", [x for _, x in results[fid]["paths"]], want["rates"][fid])
            for key in ("delivered", "unserved", "cause"):
                check(f"{case}/S2/{fid} {key}", results[fid][key], want[key][fid])
        p0 = Fraction(results["F1"]["delivered"], 15)
        total = Fraction(results["F1"]["delivered"] + results["F2"]["delivered"], 25)
        if "dr_p0" in want:
            check(f"{case}/S2 dr_p0", float(p0), want["dr_p0"])
        if "dr_p0_fraction" in want:
            check(f"{case}/S2 dr_p0", p0, Fraction(want["dr_p0_fraction"]))
        if "dr_p2" in want:
            check(f"{case}/S2 dr_p2", float(Fraction(results["F2"]["delivered"], 10)), want["dr_p2"])
        check(f"{case}/S2 dr_total", float(total), want["dr_total"])
        check(f"{case}/S2 overloaded arcs", sum(load[e] > arcs[e]["cap"] for e in load), want["overloaded_arcs"])
    fractional = diamond["non_integer_case"]
    check("non-integer delivered", float(7 * Fraction(2, 5)), fractional["delivered"])
    check("non-integer unserved", float(7 - 7 * Fraction(2, 5)), fractional["unserved"])

    blocking = cases["blocking"]
    links = [tuple(x) for x in blocking["links"]]
    arcs = make_arcs(links)
    results, _ = greedy(arcs, [dict(blocking["flow"])])
    got = results["X"]
    check("blocking paths", [list(p) for p, _ in got["paths"]], blocking["paths"])
    check("blocking rates", [x for _, x in got["paths"]], blocking["rates"])
    for key in ("delivered", "unserved", "cause"):
        check(f"blocking {key}", got[key], blocking[key])
    capacity = {e: a["cap"] for e, a in arcs.items()}
    check("blocking max flow (Edmonds-Karp)", max_flow(capacity, "S", "T"), blocking["maxflow"])
    check("blocking max flow (all-subsets min cut)", min_cut_by_subsets(capacity, "S", "T"), blocking["maxflow"])
    check("blocking greedy is below max flow", got["delivered"] < blocking["maxflow"], True)

    limit = cases["path_limit"]
    got = greedy(make_arcs(DIAMOND), [FLOWS[0]], max_paths=limit["max_paths"])[0]["F1"]
    check("path_limit paths", [list(p) for p, _ in got["paths"]], limit["paths"])
    check("path_limit rates", [x for _, x in got["paths"]], limit["rates"])
    for key in ("delivered", "unserved", "cause"):
        check(f"path_limit {key}", got[key], limit[key])

    cap_case = cases["util_cap"]
    arcs = make_arcs([("L1", "A", "B", cap_case["capacity"], 1)])
    flow = {"id": "X", "src": "A", "dst": "B", "rate": cap_case["rate"], "cls": 0}
    results, load = greedy(arcs, [flow], util_cap=Fraction(str(cap_case["util_cap"])))
    for key in ("delivered", "unserved", "cause"):
        check(f"util_cap {key}", results["X"][key], cap_case[key])
    check("util_cap arc_load", {arcs[e]["id"]: v for e, v in load.items() if v}, cap_case["arc_load"])

    def record(key, arcs, flows, fid, **kwargs):
        results, _ = greedy(arcs, flows, **kwargs)
        flow = next(f for f in flows if f["id"] == fid)
        bound, gap, cut = bound_gap_cut(arcs, flow, results[fid])
        want = records[key]
        check(f"{key} bound", bound, want["maxflow_bound"])
        check(f"{key} gap", gap, want["greedy_gap"])
        check(f"{key} cut", cut, want["cut"])

    record("bd_failed_F1", make_arcs(DIAMOND, ("L_BD",)), [FLOWS[0]], "F1")
    record("path_limit_F1", make_arcs(DIAMOND), [FLOWS[0]], "F1", max_paths=1)
    record("healthy_F2", make_arcs(DIAMOND), FLOWS, "F2")
    record("blocking", make_arcs(links), [dict(blocking["flow"])], "X")
    return count, found


def test_hand_worked_values_agree_with_an_independent_recomputation():
    count, found = mismatches(load_all())
    assert count >= 80  # the check really ran
    assert not found, found


# Corrupting one value in each area must be noticed, otherwise the test above proves nothing.
CORRUPTIONS = {
    "diamond S2 delivered": lambda d: d["diamond"]["cases"]["healthy"]["S2"]["delivered"].__setitem__("F2", 6),
    "diamond S0 excess": lambda d: d["diamond"]["cases"]["healthy"]["S0"].__setitem__("excess", 20),
    "diamond QoS delivered": lambda d: d["diamond"]["cases"]["healthy"]["S0-QoS"]["delivered"].__setitem__("F1", 9),
    "diamond S2 cause": lambda d: d["diamond"]["cases"]["bd_failed"]["S2"]["cause"].__setitem__("F2", "DISCONNECTED"),
    "blocking max flow": lambda d: d["cases"]["blocking"].__setitem__("maxflow", 2),
    "blocking path": lambda d: d["cases"]["blocking"]["paths"].__setitem__(1, ["S", "A", "T"]),
    "path_limit unserved": lambda d: d["cases"]["path_limit"].__setitem__("unserved", 4),
    "util_cap delivered": lambda d: d["cases"]["util_cap"].__setitem__("delivered", 10),
    "record bound": lambda d: d["records"]["bd_failed_F1"].__setitem__("maxflow_bound", 15),
    "record cut load": lambda d: d["records"]["healthy_F2"]["cut"][1]["load_by_class"].__setitem__("2", 4),
    "record gap": lambda d: d["records"]["blocking"].__setitem__("greedy_gap", 0.0),
    "record cut arc": lambda d: d["records"]["blocking"]["cut"][2].__setitem__("arc", "L3:T>A"),
}


@pytest.mark.parametrize("name", CORRUPTIONS)
def test_a_corrupted_value_is_noticed(name):
    data = load_all()
    CORRUPTIONS[name](data)
    assert mismatches(data)[1], name
