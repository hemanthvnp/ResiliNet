"""Summary statistics for the benchmark: mean, median, a seeded bootstrap interval, paired differences
(PLAN.md section 9; add-cli-benchmark group 4).

Everything is deterministic. The bootstrap uses its own `random.Random(BOOTSTRAP_SEED)`, so the same
values always give the same interval, and no function reads a clock or a global random state.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

BOOTSTRAP_SEED = 20240131
RESAMPLES = 10_000
LEVEL = 0.95


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float
    median: float
    low: float  # lower end of the 95% bootstrap interval of the mean
    high: float

    def __str__(self) -> str:
        return f"{self.mean:.4f} (median {self.median:.4f}, 95% CI {self.low:.4f} to {self.high:.4f}, n={self.n})"


def bootstrap_interval(
    values: Sequence[float], *, resamples: int = RESAMPLES, level: float = LEVEL, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float]:
    """Percentile bootstrap interval of the mean: the (1 - level) / 2 and (1 + level) / 2 quantiles of
    `resamples` resampled means. Empty input has no interval."""
    if not values:
        raise ValueError("no values to bootstrap")
    rng = random.Random(seed)
    count = len(values)
    means = sorted(math.fsum(rng.choices(values, k=count)) / count for _ in range(resamples))
    low = means[int((1 - level) / 2 * resamples)]
    high = means[min(resamples - 1, int((1 + level) / 2 * resamples))]
    return low, high


def summarize(values: Sequence[float], **kwargs) -> Summary:
    values = [float(v) for v in values]
    low, high = bootstrap_interval(values, **kwargs)
    return Summary(len(values), math.fsum(values) / len(values), statistics.median(values), low, high)


def paired_differences(a: Mapping[int, float], b: Mapping[int, float]) -> list[float]:
    """a[seed] - b[seed] for every seed in both, in seed order. A seed missing from either side is an error:
    a paired comparison on different sets of seeds would not be paired."""
    if set(a) != set(b):
        raise ValueError(f"seeds differ: only in a {sorted(set(a) - set(b))}, only in b {sorted(set(b) - set(a))}")
    return [a[seed] - b[seed] for seed in sorted(a)]
