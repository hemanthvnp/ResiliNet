"""Input checks shared by the policies."""

from collections.abc import Sequence

from core.model.types import Flow, PolicyConfig


def validate_inputs(flows: Sequence[Flow], cfg: PolicyConfig) -> None:
    """Flow ids must be unique (one record per flow), rates must not be negative, and the
    knobs must be usable. PolicyConfig itself only checks types."""
    seen: set[str] = set()
    for f in flows:
        if f.id in seen:
            raise ValueError(f"duplicate flow id {f.id!r}")
        seen.add(f.id)
        if f.rate < 0:
            raise ValueError(f"flow {f.id!r} has a negative rate")
    if cfg.max_paths < 1:
        raise ValueError("max_paths must be at least 1")
    if cfg.congestion_lambda < 0:
        raise ValueError("congestion_lambda must not be negative")
    if not 0 < cfg.util_cap <= 1:
        raise ValueError("util_cap must be in (0, 1]")
