"""The headline-check helper runs end to end (task 4.1). It asserts properties, not the
measured ratios: those are recorded in the pull request and hand-checked there."""

import pytest

from core.gen.tests.headline import run


@pytest.mark.parametrize("failed", [None, "L6"])
def test_s2_overloads_nothing(failed):
    assert run(failed)["S2"]["overloaded_arcs"] == 0


def test_every_policy_delivers_everything_while_healthy():  # scenario 1: load factor 0.5, no failure
    for name, row in run(None).items():
        assert row["DR"] == pytest.approx(1.0), name
