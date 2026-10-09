"""Cycle 2 additions on top of core/ (PLAN-CYCLE2.md section 7). Owner: D.

Imports core/ and cli/; imported by neither. No web or frontend imports.

Importing `ext` changes nothing. `register()` adds the ECMP policies and the example
topologies to the cycle-1 registries in memory; `python -m ext` calls it. Registration at
import time would leak into every other test in the same pytest process.
"""

from pathlib import Path

EXAMPLE_TOPOLOGIES = Path(__file__).resolve().parents[1] / "examples" / "topologies"


def register() -> None:
    """Idempotent. The registries have no register function, so this adds to their dicts
    (the PLAN-CYCLE2.md section 7 fallback). fixtures/ is frozen, so the small hand-worked
    topologies live in examples/topologies/; an absolute path survives the registry's join
    onto fixtures/topologies/."""
    from core.gen.registry import TEMPLATES
    from core.routing.registry import POLICIES
    from ext.ecmp import Ecmp, EcmpQoS

    POLICIES.setdefault("ECMP", Ecmp())
    POLICIES.setdefault("ECMP-QoS", EcmpQoS())
    for name in ("square", "shared-prefix", "eight-paths"):
        TEMPLATES.setdefault(name, (str(EXAMPLE_TOPOLOGIES / f"{name}.json"), None))
