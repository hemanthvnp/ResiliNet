"""Every ext test runs with the ECMP policies and example templates registered, and the
cycle-1 registries are restored afterwards, so no other module's tests see them."""

import pytest

import ext
from core.gen.registry import TEMPLATES
from core.routing.registry import POLICIES


@pytest.fixture(autouse=True)
def registered():
    saved = dict(POLICIES), dict(TEMPLATES)
    ext.register()
    yield
    for registry, before in zip((POLICIES, TEMPLATES), saved):
        registry.clear()
        registry.update(before)
