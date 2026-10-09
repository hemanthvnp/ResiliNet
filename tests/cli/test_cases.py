"""Per-seed benchmark cases (change add-cli-benchmark, task 3.1)."""

import pytest

from cli.cases import CASES, build_cases
from core.gen.campus import CAMPUS_PRIMARY_UPLINK
from core.gen.registry import resolve_topology

SEEDS = [0, 1, 7]


@pytest.fixture(scope="module", params=SEEDS)
def cases(request):
    return {s.id.split("-", 1)[1]: s for s in build_cases(request.param)}


def test_the_same_seed_gives_the_same_cases():
    first, second = build_cases(3), build_cases(3)
    assert [s.model_dump_json() for s in first] == [s.model_dump_json() for s in second]


def test_four_cases_in_order(cases):
    assert list(cases) == list(CASES)


def test_every_case_has_identical_topology_and_flows(cases):
    healthy = cases["healthy"]
    for case in cases.values():
        assert case.topology == healthy.topology
        assert case.traffic == healthy.traffic
        assert sum(f.rate for f in case.traffic) == sum(f.rate for f in healthy.traffic)


def test_events_per_case(cases):
    assert cases["healthy"].events == []
    [uplink] = cases["uplink"].events
    assert (uplink.step, uplink.kind, uplink.links) == (1, "fail", [CAMPUS_PRIMARY_UPLINK])
    [multi] = cases["multi"].events
    assert (multi.step, multi.kind) == (1, "fail")
    fail, recover = cases["recovered"].events
    assert (fail.step, fail.kind, recover.step, recover.kind) == (1, "fail", 2, "recover")
    assert recover.links == fail.links


def test_random_failures_are_three_distinct_links_of_the_network(cases):
    link_ids = {l.id for l in resolve_topology(cases["healthy"].topology).topology.links}
    for links in (cases["multi"].events[0].links, cases["recovered"].events[0].links):
        assert len(set(links)) == 3
        assert set(links) <= link_ids
        assert links == sorted(links)


def test_failure_sets_vary_across_seeds():
    draws = {tuple(build_cases(seed)[2].events[0].links) for seed in range(5)}
    assert len(draws) > 1
