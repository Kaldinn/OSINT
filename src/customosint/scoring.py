"""Evidence-based scoring with diminishing returns and conflict penalties."""

from __future__ import annotations

import math

from .models import Evidence

SIGNAL_WEIGHTS: dict[str, float] = {
    "exact_email": 0.95,
    "direct_profile_link": 0.9,
    "rare_username": 0.68,
    "common_username": 0.25,
    "same_avatar": 0.72,
    "same_full_name": 0.25,
    "same_city": 0.2,
    "same_organization": 0.38,
    "same_website": 0.82,
    "same_bio_url": 0.8,
    "derived": 0.42,
    "provider_match": 0.62,
}


def combine_evidence(evidence: list[Evidence], conflicts: float = 0.0) -> float:
    """Combine independent signals as 1-product(1-w), capped and penalized."""
    if not evidence:
        return 0.0
    by_provider: dict[str, float] = {}
    for item in evidence:
        weight = max(0.0, min(0.99, item.weight))
        by_provider[item.provider] = max(by_provider.get(item.provider, 0.0), weight)
    remaining = math.prod(1.0 - weight for weight in by_provider.values())
    score = (1.0 - remaining) * (1.0 - max(0.0, min(conflicts, 0.9)))
    return round(max(0.0, min(score, 1.0)), 4)


def confidence_label(score: float) -> str:
    if score < 0.3:
        return "LOW"
    if score < 0.6:
        return "POSSIBLE"
    if score < 0.8:
        return "PROBABLE"
    return "STRONG"

