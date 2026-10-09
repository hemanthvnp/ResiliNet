"""Integer arc cost with the Fortz-Thorup congestion slopes (PLAN.md section 5)."""


def slope(load: int, capacity: int) -> int:
    """s(u) for u = load / capacity, compared with the thresholds in integer arithmetic."""
    if 3 * load < capacity:
        return 1
    if 3 * load < 2 * capacity:
        return 3
    if 10 * load < 9 * capacity:
        return 10
    return 70


def arc_cost(latency: int, load: int, capacity: int, congestion_lambda: int) -> int:
    """latency + lambda * (s(u) - 1). With lambda 0 this is the latency."""
    return latency + congestion_lambda * (slope(load, capacity) - 1)
