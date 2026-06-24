"""Non-repeating, in-memory content rotation for Luna games."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T")


def content_fingerprint(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("question", "riddle", "word", "title", "option_a"):
            if value.get(key):
                return f"{key}:{str(value[key]).strip().casefold()}"
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).casefold()


class ContentRotation:
    """Shuffle-bag selection: no repeats until every item has been used."""

    def __init__(self) -> None:
        self._remaining: dict[str, list[str]] = defaultdict(list)
        self._last: dict[str, str] = {}
        self._seen_generated: dict[str, set[str]] = defaultdict(set)

    def take(
        self,
        key: str,
        items: Iterable[T],
        count: int = 1,
        fingerprint: Callable[[T], str] = content_fingerprint,
    ) -> list[T]:
        values = list(items)
        if not values or count <= 0:
            return []
        by_id = {fingerprint(item): item for item in values}
        available_ids = set(by_id)
        bag = [item_id for item_id in self._remaining[key] if item_id in available_ids]

        result: list[T] = []
        selected_ids: set[str] = set()
        target = min(count, len(by_id))
        while len(result) < target:
            if not bag:
                bag = [item_id for item_id in available_ids if item_id not in selected_ids]
                random.shuffle(bag)
                last = self._last.get(key)
                if len(bag) > 1 and bag[-1] == last:
                    bag[0], bag[-1] = bag[-1], bag[0]
            item_id = bag.pop()
            if item_id in selected_ids:
                continue
            result.append(by_id[item_id])
            selected_ids.add(item_id)
            self._last[key] = item_id

        self._remaining[key] = bag
        return result

    def remember_generated(self, key: str, item: Any) -> bool:
        """Return False for an AI value already used during this bot process."""
        item_id = content_fingerprint(item)
        if item_id in self._seen_generated[key]:
            return False
        self._seen_generated[key].add(item_id)
        return True


content_rotation = ContentRotation()
