"""Shared fixed-round difficulty plans for Luna's short competition games."""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Iterable


ROUND_SIZE = 10
DIFFICULTY_COUNTS = {
    "hard": 2,
    "medium": 3,
    "easy": 5,
}
MIXED_LEVEL_LABEL = "🌺 2 Difficult · 🌼 3 Moderate · 🌱 5 Easy"


def build_round_plan(*, shuffle: bool = True) -> list[str]:
    """Return exactly ten levels with the fixed 2/3/5 distribution."""
    plan = [
        difficulty
        for difficulty, count in DIFFICULTY_COUNTS.items()
        for _ in range(count)
    ]
    if shuffle:
        random.shuffle(plan)
    return plan


def has_round_distribution(values: Iterable[str]) -> bool:
    """Return whether ``values`` is one complete fixed-round difficulty plan."""
    values = list(values)
    return len(values) == ROUND_SIZE and Counter(values) == Counter(
        {difficulty: count for difficulty, count in DIFFICULTY_COUNTS.items()}
    )
