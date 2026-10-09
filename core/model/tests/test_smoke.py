import importlib

import pytest

PACKAGES = [
    "core",
    "core.model",
    "core.gen",
    "core.routing",
    "core.sim",
    "core.metrics",
    "core.explain",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports(name):
    importlib.import_module(name)
