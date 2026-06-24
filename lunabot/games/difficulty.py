"""Shared difficulty helpers for Luna games."""

DIFFICULTIES = ("easy", "medium", "hard")

LEVEL_ICONS = {
    "easy": "🌱",
    "medium": "🌼",
    "hard": "🌺",
}

LEVEL_NAMES = {
    "easy": "Easy",
    "medium": "Moderate",
    "hard": "Difficult",
}

DIFFICULTY_ALIASES = {
    "easy": "easy",
    "green": "easy",
    "green flower": "easy",
    "🌱": "easy",
    "🟢": "easy",
    "medium": "medium",
    "moderate": "medium",
    "yellow": "medium",
    "yellow flower": "medium",
    "🌼": "medium",
    "🟡": "medium",
    "hard": "hard",
    "difficult": "hard",
    "red": "hard",
    "red flower": "hard",
    "🌺": "hard",
    "🌹": "hard",  # Accepted for backwards compatibility, but no longer displayed.
    "🔴": "hard",
}


def parse_difficulty(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().casefold().strip("'\"").split())
    return DIFFICULTY_ALIASES.get(cleaned)


def normalize_difficulty(value: str | None, default: str = "easy") -> str:
    return parse_difficulty(value) or default


def level_label(value: str | None) -> str:
    level = normalize_difficulty(value)
    return f"{LEVEL_ICONS[level]} {LEVEL_NAMES[level]}"
