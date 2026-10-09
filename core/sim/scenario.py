"""Scenario loading (PLAN.md section 7 and 9).

A scenario fixture under fixtures/scenarios/ is {"scenario": Scenario, "expect": {...}}:
the scenario and the claims made about it sit in one file, so a reviewer sees both.
The expect block is free-form data read by the fixture test.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue

from core.model.types import Scenario


class ScenarioFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: Scenario
    expect: dict[str, JsonValue]


def load_scenario(source: Scenario | dict | str | Path) -> Scenario:
    """A Scenario from a model, a dict, or a JSON file holding a Scenario or a fixture."""
    if isinstance(source, Scenario):
        return source
    if isinstance(source, dict):
        return Scenario.model_validate(source)
    text = Path(source).read_text(encoding="utf-8")
    try:
        return ScenarioFixture.model_validate_json(text).scenario
    except ValueError:
        return Scenario.model_validate_json(text)


def load_fixture(path: str | Path) -> ScenarioFixture:
    return ScenarioFixture.model_validate_json(Path(path).read_text(encoding="utf-8"))
