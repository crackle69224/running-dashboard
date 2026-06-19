"""
Simple heuristic lookup for "how many weeks is this goal likely to take" — a
starting estimate, not a trained model. See onboarding Screen 4 spec.
"""

BASE_WEEKS = {
    "5K": 8,
    "10K": 10,
    "Half Marathon": 12,
    "Marathon": 16,
    "Custom": 12,
}

# Multiplier relative to a 5-day/week baseline (1.0). Fewer days stretches the
# timeline; more days shortens it, with diminishing returns at the high end.
FREQUENCY_MULTIPLIER = {
    2: 2.2,
    3: 1.5,
    4: 1.2,
    5: 1.0,
    6: 0.95,
    7: 0.9,
}

# Below this many days/week, the combination gets flagged as unusual for the distance.
MIN_RECOMMENDED_DAYS = {
    "5K": 3,
    "10K": 3,
    "Half Marathon": 4,
    "Marathon": 4,
    "Custom": 3,
}


def estimate_goal(distance: str, days_per_week: int) -> dict:
    base_weeks = BASE_WEEKS.get(distance, BASE_WEEKS["Custom"])
    multiplier = FREQUENCY_MULTIPLIER.get(days_per_week, FREQUENCY_MULTIPLIER[5])
    estimated_weeks = round(base_weeks * multiplier)

    min_days = MIN_RECOMMENDED_DAYS.get(distance, MIN_RECOMMENDED_DAYS["Custom"])
    is_unusual = days_per_week < min_days

    return {
        "estimated_weeks": estimated_weeks,
        "is_unusual": is_unusual,
        "min_recommended_days": min_days,
    }
