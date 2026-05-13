from __future__ import annotations

import re


def sold_count_to_score(value: str) -> float:
    if not value:
        return 0.0

    normalized = value.lower().replace(",", "").strip()
    multiplier = 1
    if "k" in normalized:
        multiplier = 1_000
    elif "m" in normalized:
        multiplier = 1_000_000

    match = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if not match:
        return 0.0
    return float(match.group(1)) * multiplier
