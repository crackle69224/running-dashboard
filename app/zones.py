MAX_HR = 196

ZONE_BOUNDS = [
    (0, round(MAX_HR * 0.60)),        # Zone 1: < 60%
    (round(MAX_HR * 0.60), round(MAX_HR * 0.70)),   # Zone 2: 60-70%
    (round(MAX_HR * 0.70), round(MAX_HR * 0.80)),   # Zone 3: 70-80%
    (round(MAX_HR * 0.80), round(MAX_HR * 0.90)),   # Zone 4: 80-90%
    (round(MAX_HR * 0.90), 999),      # Zone 5: > 90%
]

ZONE_COLORS = ["#3a4a63", "#5b8cf7", "#46c98e", "#f5b942", "#f25c54"]


def hr_to_zone(hr: int) -> int:
    if hr is None:
        return None
    for i, (lo, hi) in enumerate(ZONE_BOUNDS):
        if lo <= hr < hi:
            return i + 1
    return 5


def zone_breakdown(hr_values: list[int]) -> dict:
    """Return % of samples spent in each zone (1-5)."""
    counts = [0, 0, 0, 0, 0]
    total = 0
    for hr in hr_values:
        if hr is None:
            continue
        zone = hr_to_zone(hr)
        counts[zone - 1] += 1
        total += 1
    if total == 0:
        return {f"zone{i+1}_pct": 0.0 for i in range(5)}
    return {f"zone{i+1}_pct": round(counts[i] / total * 100, 1) for i in range(5)}
