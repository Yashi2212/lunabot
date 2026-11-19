"""Wordle-style six-row word guessing game."""

from __future__ import annotations

import asyncio
import random
import secrets
from collections import Counter, deque
from typing import Any

import aiohttp
import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession


WORDLE_API_BASE_URL = "https://wordle-list.malted.dev"
WORDLE_FALLBACK_API_BASE_URL = "https://a04-wordle-api.vercel.app"
WORDLE_DATAMUSE_API_URL = "https://api.datamuse.com/words"
WORDLE_DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
WORDLE_FREE_DICTIONARY_API_URL = "https://freedictionaryapi.com/api/v1/entries/en/"
WORDLE_API_TIMEOUT_SECONDS = 4
WORDLE_FALLBACK_TIMEOUT_SECONDS = 4
WORDLE_TARGET_TIMEOUT_SECONDS = 2
WORDLE_TARGET_ATTEMPTS = 2
WORD_LENGTH = 5
MAX_GUESSES = 6
EMPTY_TILE = "⬜"
ABSENT_TILE = "⬛"
PRESENT_TILE = "🟨"
CORRECT_TILE = "🟩"

# Used only when the public target services are unavailable or keep returning
# the same cached answer. Keeping this pool local prevents a broken cache from
# making every new game identical.
EMERGENCY_TARGET_POOL = (
    "abate", "adore", "admit", "adopt", "aisle", "alert", "alien", "align",
    "alike", "alive", "allow", "alone", "alter", "amber", "angel", "anger",
    "angle", "angry", "ankle", "apart", "apple", "arise", "aroma", "aside",
    "asset", "audio", "avoid", "awake", "award", "aware", "bacon", "badge",
    "basic", "beach", "begin", "belly", "bench", "berry", "birth", "black",
    "blame", "blank", "blast", "blend", "blind", "block", "blood", "board",
    "brain", "brave", "bread", "break", "brick", "brief", "bring", "broad",
    "brown", "build", "cabin", "cable", "candy", "carry", "catch", "cause",
    "chain", "chair", "charm", "chase", "check", "chest", "chief", "child",
    "claim", "class", "clean", "clear", "climb", "clock", "close", "cloud",
    "coach", "coast", "color", "coral", "couch", "count", "court", "cover",
    "craft", "crane", "crash", "crazy", "cream", "crime", "cross", "crowd",
    "crown", "crush", "dance", "dealt", "death", "delay", "depth", "diary",
    "digit", "dirty", "doubt", "draft", "drain", "drama", "dream", "dress",
    "drink", "drive", "eager", "early", "earth", "eight", "elite", "empty",
    "enjoy", "enter", "equal", "error", "event", "every", "exact", "exist",
    "extra", "faith", "fancy", "fault", "feast", "fence", "field", "fight",
    "final", "first", "flame", "flash", "fleet", "floor", "focus", "force",
    "found", "frame", "fresh", "front", "fruit", "giant", "given", "glass",
    "globe", "glory", "grace", "grade", "grain", "grand", "grape", "graph",
    "grass", "great", "green", "greet", "grief", "grill", "group", "guard",
    "guess", "guest", "guide", "habit", "happy", "harsh", "heart", "heavy",
    "hello", "honey", "horse", "hotel", "house", "human", "humor", "ideal",
    "image", "imply", "index", "inner", "input", "issue", "jelly", "joint",
    "judge", "juice", "juicy", "known", "label", "large", "laser", "later",
    "laugh", "layer", "learn", "least", "leave", "legal", "lemon", "level",
    "light", "limit", "liver", "local", "logic", "loose", "lover", "lucky",
    "lunar", "magic", "major", "maker", "match", "maybe", "mayor", "media",
    "medal", "merit", "metal", "might", "minor", "minus", "model", "money",
    "month", "moral", "motor", "mount", "mouse", "movie", "music", "naive",
    "nerve", "never", "night", "noble", "noise", "north", "novel", "nurse",
    "ocean", "offer", "often", "olive", "orbit", "order", "other", "outer",
    "paint", "panel", "paper", "party", "pasta", "patch", "pause", "peace",
    "peach", "phase", "phone", "piano", "piece", "pilot", "place", "plain",
    "plane", "plant", "plate", "point", "power", "press", "price", "pride",
    "prime", "print", "prize", "proof", "proud", "queen", "quick", "quiet",
    "radio", "raise", "range", "rapid", "reach", "react", "ready", "realm",
    "rider", "right", "rival", "river", "robot", "rough", "round", "royal",
    "rural", "scale", "scene", "scope", "score", "sense", "serve", "seven",
    "shade", "shake", "shame", "shape", "share", "sharp", "sheep", "shift",
    "shine", "shirt", "shock", "short", "sight", "skill", "skirt", "sleep",
    "slice", "slide", "small", "smart", "smile", "smoke", "solid", "sound",
    "south", "space", "spare", "speak", "speed", "spend", "spent", "spice",
    "split", "sport", "staff", "stage", "stand", "start", "state", "steam",
    "steel", "stick", "still", "stock", "stone", "stood", "store", "storm",
    "story", "strip", "study", "style", "sugar", "suite", "super", "sweet",
    "table", "taste", "teach", "teeth", "thank", "their", "theme", "there",
    "thick", "thing", "think", "third", "those", "throw", "tight", "timer",
    "title", "today", "topic", "total", "touch", "tower", "track", "trade",
    "train", "treat", "trend", "trial", "trust", "truth", "uncle", "under",
    "union", "until", "upper", "upset", "urban", "usual", "valid", "value",
    "video", "visit", "voice", "waste", "watch", "water", "weary", "weird",
    "wheel", "where", "which", "while", "white", "whole", "woman", "world",
    "worry", "worth", "would", "write", "wrong", "young", "youth", "zebra",
)


class WordleServiceUnavailable(Exception):
    """The Wordle API could not provide or validate a word."""


class WordleGame(BaseGame):
    name = "wordle"
    description = "Single-player six-row Wordle game with green, yellow, and black feedback"
    max_players = 1

    def __init__(self) -> None:
        super().__init__()
        self._recent_targets: deque[str] = deque(maxlen=30)

    async def start(self, session: GameSession, ctx) -> None:
        try:
            target = await self._choose_target()
        except (WordleServiceUnavailable, aiohttp.ClientError, TimeoutError, ValueError):
            session.state["finished"] = True
            await ctx.reply(
                "⚠️ The Wordle word service is unavailable, so I could not start this game. "
                "No lobby score was recorded—please try `luna wordle` again later. 🌸",
                mention_author=False,
            )
            return

        session.state.update(
            target=target,
            guesses=[],
            guess_lock=asyncio.Lock(),
            finished=False,
        )
        await ctx.reply(
            "🟩 **Wordle** · **Solo** · **6 rows**\n"
            "Guess the hidden 5-letter word. Green = correct place, yellow = wrong place, "
            "black = not in the word.\n"
            "Every accepted guess uses one row; invalid words do not use a row.",
            mention_author=False,
        )
        await self._send_board(session, ctx.channel, "Type a 5-letter guess.")

    async def _choose_target(self) -> str:
        timeout = aiohttp.ClientTimeout(total=WORDLE_TARGET_TIMEOUT_SECONDS)
        cached_targets: list[str] = []
        async with aiohttp.ClientSession(timeout=timeout) as client:
            for endpoint in (
                f"{WORDLE_API_BASE_URL}/choice",
                f"{WORDLE_FALLBACK_API_BASE_URL}/api/random-word/",
            ):
                for _ in range(WORDLE_TARGET_ATTEMPTS):
                    try:
                        # Vercel/CDN caching can otherwise return the same
                        # one-word response for every new game.
                        async with client.get(
                            endpoint,
                            params={"_": secrets.token_hex(8)},
                        ) as response:
                            if response.status != 200:
                                continue
                            payload = await response.json(content_type=None)
                    except (aiohttp.ClientError, TimeoutError, ValueError):
                        continue
                    target = self._extract_target(payload)
                    if not target:
                        continue
                    if target not in self._recent_targets:
                        self._recent_targets.append(target)
                        return target
                    cached_targets.append(target)

        available = [
            target for target in EMERGENCY_TARGET_POOL
            if target not in self._recent_targets
        ]
        if available:
            target = random.choice(available)
            self._recent_targets.append(target)
            return target
        if cached_targets:
            target = cached_targets[0]
            self._recent_targets.append(target)
            return target
        raise WordleServiceUnavailable("All Wordle target providers are unavailable")

    @staticmethod
    def _extract_target(payload: Any) -> str | None:
        if isinstance(payload, dict):
            raw_target = payload.get("word") or payload.get("solution")
        elif isinstance(payload, str):
            raw_target = payload
        else:
            raw_target = ""
        target = str(raw_target).strip().casefold()
        if len(target) == WORD_LENGTH and target.isascii() and target.isalpha():
            return target
        return None

    async def _is_valid_guess(self, guess: str) -> bool:
        timeout = aiohttp.ClientTimeout(total=WORDLE_API_TIMEOUT_SECONDS)
        wordle_provider_responded = False
        async with aiohttp.ClientSession(timeout=timeout) as client:
            endpoints = (
                (f"{WORDLE_API_BASE_URL}/valid", {"word": guess}),
                (f"{WORDLE_FALLBACK_API_BASE_URL}/api/word-valid/{guess}", None),
            )
            for endpoint, params in endpoints:
                try:
                    async with client.get(endpoint, params=params) as response:
                        if response.status != 200:
                            continue
                        payload = await response.json(content_type=None)
                except (aiohttp.ClientError, TimeoutError, ValueError):
                    continue
                wordle_provider_responded = True
                if self._extract_validity(payload):
                    return True

        # Both public Wordle endpoints have had intermittent DNS/timeout
        # failures. Try independent word-list/dictionary fallbacks in parallel
        # so a slow definition response cannot make a normal word unplayable.
        fallback_valid = await self._fallback_validity(guess)
        if fallback_valid is not None:
            return fallback_valid

        if wordle_provider_responded:
            return False
        raise WordleServiceUnavailable("All Wordle validation providers are unavailable")

    @classmethod
    async def _fallback_validity(cls, guess: str) -> bool | None:
        timeout = aiohttp.ClientTimeout(total=WORDLE_FALLBACK_TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as client:
                results = await asyncio.gather(
                    cls._check_datamuse(client, guess),
                    cls._check_dictionary_provider(
                        client, f"{WORDLE_DICTIONARY_API_URL}{guess}"
                    ),
                    cls._check_dictionary_provider(
                        client, f"{WORDLE_FREE_DICTIONARY_API_URL}{guess}"
                    ),
                    return_exceptions=True,
                )
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None

        provider_responded = False
        for result in results:
            if isinstance(result, BaseException):
                continue
            if result is True:
                return True
            if result is False:
                provider_responded = True
        return False if provider_responded else None

    @staticmethod
    async def _check_datamuse(client: aiohttp.ClientSession, guess: str) -> bool | None:
        try:
            async with client.get(
                WORDLE_DATAMUSE_API_URL,
                params={"sp": guess, "max": 20},
                headers={"User-Agent": "LunaBot/1.0"},
            ) as response:
                if response.status != 200:
                    return None
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None

        if not isinstance(payload, list):
            return False
        return any(
            isinstance(item, dict)
            and str(item.get("word", "")).strip().casefold() == guess
            for item in payload
        )

    @staticmethod
    async def _check_dictionary_provider(
        client: aiohttp.ClientSession, endpoint: str
    ) -> bool | None:
        try:
            async with client.get(endpoint, headers={"User-Agent": "LunaBot/1.0"}) as response:
                if response.status == 404:
                    return False
                if response.status != 200:
                    return None
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None

        if isinstance(payload, list):
            return bool(payload)
        if isinstance(payload, dict):
            return bool(payload.get("entries")) or bool(payload.get("word"))
        return False

    @staticmethod
    def _extract_validity(payload: Any) -> bool:
        if isinstance(payload, bool):
            return payload
        if isinstance(payload, dict):
            value = payload.get("valid")
            if isinstance(value, bool):
                return value
            value = payload.get("is_valid")
            if isinstance(value, bool):
                return value
        if isinstance(payload, str):
            return payload.strip().casefold() in {"true", "valid", "1"}
        return False

    @staticmethod
    def _score_guess(target: str, guess: str) -> list[str]:
        """Score duplicate letters using Wordle's two-pass rules."""
        tiles = [ABSENT_TILE] * WORD_LENGTH
        remaining = Counter(target)
        for index, letter in enumerate(guess):
            if letter == target[index]:
                tiles[index] = CORRECT_TILE
                remaining[letter] -= 1
        for index, letter in enumerate(guess):
            if tiles[index] == CORRECT_TILE:
                continue
            if remaining[letter] > 0:
                tiles[index] = PRESENT_TILE
                remaining[letter] -= 1
        return tiles

    @classmethod
    def _format_board(cls, session: GameSession) -> str:
        rows = []
        guesses = session.state.get("guesses", [])
        for index in range(MAX_GUESSES):
            if index < len(guesses):
                row = guesses[index]
                rows.append(
                    f"{index + 1}. `{row['guess'].upper()}` {''.join(row['tiles'])}"
                )
            else:
                rows.append(f"{index + 1}. {EMPTY_TILE * WORD_LENGTH}")
        return "\n".join(rows)

    @classmethod
    def _board_message(cls, session: GameSession, prompt: str = "") -> str:
        lines = [
            f"**Wordle** · Row **{len(session.state.get('guesses', []))}/{MAX_GUESSES}**",
            "```text",
            cls._format_board(session),
            "```",
        ]
        if prompt:
            lines.append(prompt)
        return "\n".join(lines)

    async def _send_board(self, session: GameSession, channel, prompt: str = "") -> None:
        await channel.send(self._board_message(session, prompt))

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        guess = message.content.strip().casefold()
        if len(guess) != WORD_LENGTH or not guess.isascii() or not guess.isalpha():
            return

        async with session.state["guess_lock"]:
            if session.state.get("finished"):
                return
            if any(row["guess"] == guess for row in session.state["guesses"]):
                await message.reply("That guess is already on the board. Try another word.", mention_author=False)
                return

            try:
                # The target is known locally, so solving must still work if
                # every external validator is temporarily unavailable.
                valid = guess == session.state["target"] or await self._is_valid_guess(guess)
            except (WordleServiceUnavailable, aiohttp.ClientError, TimeoutError, ValueError):
                await message.reply(
                    "⚠️ The Wordle validation service is unavailable. No row was used; "
                    "please try that guess again shortly.",
                    mention_author=False,
                )
                return
            if not valid:
                await message.reply(
                    "That is not a valid Wordle word. No row was used.",
                    mention_author=False,
                )
                return

            target = session.state["target"]
            tiles = self._score_guess(target, guess)
            session.state["guesses"].append(
                {"guess": guess, "tiles": tiles, "user_id": message.author.id}
            )
            solved = guess == target
            if solved:
                session.increment_score(message.author.id)
                session.state["finished"] = True
                await message.channel.send(
                    self._board_message(
                        session,
                        f"🏆 <@{message.author.id}> solved it in **{len(session.state['guesses'])}/6**! "
                        f"Answer: **{target.upper()}**",
                    )
                )
                return

            if len(session.state["guesses"]) >= MAX_GUESSES:
                session.state["finished"] = True
                await message.channel.send(
                    self._board_message(
                        session,
                        f"Game over. The answer was **{target.upper()}**.",
                    )
                )
                return

            await self._send_board(session, message.channel, "Next guess.")

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
