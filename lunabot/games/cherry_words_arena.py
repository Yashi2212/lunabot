"""CherryWords Arena multiplayer word battle."""

from __future__ import annotations

import asyncio
import contextlib
import random
from typing import Any

import aiohttp
import discord

from ..core.base_game import BaseGame
from ..definitions import DictionaryUnavailable, DefinitionNotFound, fetch_meaning
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board, format_winner_line
from .difficulty import level_label, normalize_difficulty


# Emergency-only prompts. CherryWords requires fresh AI prompts by default;
# this bank is used only when explicitly enabled with an environment flag.
CHERRYWORDS_FALLBACK_SEQUENCES = (
    "act", "ain", "all", "and", "art", "ate", "ble", "cas", "cha", "che",
    "com", "day", "ear", "ent", "est", "for", "ing", "ion", "key", "map",
    "mor", "mot", "nat", "out", "pre", "pro", "rea", "sta", "str", "sun",
    "tal", "ter", "ver", "wor", "you", "air", "arc", "ast", "ate", "ave",
    "cal", "car", "cou", "cre", "cur", "des", "dev", "ent", "gen", "hea",
)

LIVES_BY_DIFFICULTY = {
    "easy": 3,
    "medium": 2,
    "hard": 1,
}

ROUND_SECONDS_BY_DIFFICULTY = {
    "easy": 10,
    "medium": 8,
    "hard": 5,
}

COUNTDOWN_EMOJIS = ("3️⃣", "2️⃣", "1️⃣")
CROSS_REACTION = "❌"
CORRECT_REACTION = "🔥"
RANDOMIZER = random.SystemRandom()
MEANING_PREVIEW_LIMIT = 180
OPENING_PAUSE_SECONDS = 5
FIRST_INPUT_GRACE_SECONDS = 5
DICTIONARY_LOOKUP_TIMEOUT_SECONDS = 1.2

class CherryWordsArenaGame(BaseGame):
    name = "cherrywords"
    description = "Competitive multiplayer word-building arena"
    max_players = 5

    def __init__(self) -> None:
        super().__init__()
        self._definition_cache: dict[str, str | None] = {}
        self._last_opening_sequence: dict[str, str] = {}
        self._dictionary_session: aiohttp.ClientSession | None = None

    @staticmethod
    def _current_player_id(session: GameSession) -> int | None:
        current = session.state.get("current_player_id")
        if current in CherryWordsArenaGame._active_player_ids(session):
            return current
        return None

    @staticmethod
    def _active_mentions(session: GameSession) -> str:
        current = CherryWordsArenaGame._current_player_id(session)
        if current is not None:
            return f"<@{current}>"
        return " ".join(f"<@{user_id}>" for user_id in CherryWordsArenaGame._active_player_ids(session))

    def _build_round_prompt(self, session: GameSession, notice: str = "") -> str:
        letters = session.state["letters"].upper()
        current = self._current_player_id(session)
        lines = [
            f"**Turn:** {self._active_mentions(session)}",
            f"Type a word containing: **{letters}**",
        ]
        if not session.state.get("timeless"):
            current_life = session.state.get("lives", {}).get(current, 0)
            seconds = session.state["round_seconds"]
            if session.state.get("first_input_pending"):
                lines.append(
                    f"⏳ First word window: {FIRST_INPUT_GRACE_SECONDS}s  ·  "
                    f"then ⏱️ {seconds}s  ·  ❤️ HP: **{current_life}**"
                )
            else:
                lines.append(f"⏱️ {seconds}s  ·  ❤️ HP: **{current_life}**")
        if notice:
            lines.insert(0, notice)
        return "\n".join(lines)

    async def start(self, session: GameSession, ctx) -> None:
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        timeless = bool(session.state.get("timeless", False))
        round_seconds = session.state.get("round_seconds") or ROUND_SECONDS_BY_DIFFICULTY[difficulty]
        session.state.update(
            round_number=0,
            used_words=set(),
            used_sequences=set(),
            extra_sequences=self._clean_extra_sequences(session.state.get("extra_sequences")),
            remaining_sequences=[],
            difficulty=difficulty,
            show_meanings=bool(session.state.get("show_meanings", False)),
            timeless=timeless,
            lives=(
                {}
                if timeless
                else {user_id: LIVES_BY_DIFFICULTY[difficulty] for user_id in session.player_ids}
            ),
            turn_index=-1,
            current_player_id=None,
            round_seconds=None if timeless else round_seconds,
            validation_lock=asyncio.Lock(),
            round_timer_task=None,
            round_message=None,
            first_input_pending=True,
            round_token=0,
        )
        if not session.state["extra_sequences"]:
            session.state["finished"] = True
            await ctx.reply(
                "🌙 CherryWords could not prepare a sequence bank and could not start.",
                mention_author=False,
            )
            return
        session.state["remaining_sequences"] = self._build_sequence_bag(session)
        meanings = " · meanings on" if session.state["show_meanings"] else ""
        timing = (
            "practice · no timer · no HP"
            if timeless
            else f"❤️ {LIVES_BY_DIFFICULTY[difficulty]} · ⏱️ {round_seconds}s"
        )
        if timeless:
            instructions = (
                "Practice mode: no timer or HP. It is open-ended, so there is no final winner."
            )
        elif len(session.player_ids) == 1:
            instructions = "Solo score run: answer until your HP runs out."
        else:
            instructions = "One player answers per turn. The last player standing wins."
        await ctx.reply(
            f"🌸 **CherryWords** · {level_label(difficulty)} · "
            f"{timing}{meanings}\n"
            f"{instructions}\n"
            "Use the letters inside a longer real word. Wrong entries are rejected; accepted words score +1.\n"
            f"First turn in {OPENING_PAUSE_SECONDS} seconds.",
            mention_author=False,
        )
        await asyncio.sleep(OPENING_PAUSE_SECONDS)
        await self._start_round(session, ctx.channel)

    async def _start_round(self, session: GameSession, channel, notice: str = "") -> None:
        await self._cancel_round_timer(session)
        if not self._active_player_ids(session):
            await self._show_results(session, channel, notice)
            return

        current_player = self._next_active_player_id(session)
        if current_player is None:
            await self._show_results(session, channel, notice)
            return

        session.state["round_number"] += 1
        session.state["letters"] = self._next_sequence(session)
        session.state["attempts"] = {user_id: 0 for user_id in session.player_ids}
        session.state["round_resolved"] = False
        session.state["first_input_pending"] = True
        session.reset_answered()
        round_message = await channel.send(self._build_round_prompt(session, notice))
        session.state["round_message"] = round_message
        if not session.state.get("timeless"):
            # Give the player a short protected window to submit the first
            # word. The actual countdown begins only after that window, and a
            # live dictionary check never consumes the answer timer.
            self._schedule_round_timer(
                session,
                round_message,
                initial_wait=FIRST_INPUT_GRACE_SECONDS,
            )

    @staticmethod
    def _active_player_ids(session: GameSession) -> list[int]:
        if session.state.get("timeless"):
            return list(session.player_ids)
        lives = session.state.get("lives", {})
        return [user_id for user_id in session.player_ids if lives.get(user_id, 0) > 0]

    @staticmethod
    def _format_lives(session: GameSession) -> str:
        lives = session.state.get("lives", {})
        return " | ".join(
            f"<@{user_id}>: **{lives.get(user_id, 0)}**"
            for user_id in session.player_ids
        )

    @staticmethod
    def _next_active_player_id(session: GameSession) -> int | None:
        if not CherryWordsArenaGame._active_player_ids(session):
            return None
        total_players = len(session.player_ids)
        turn_index = session.state.get("turn_index", -1)
        for _ in range(total_players):
            turn_index = (turn_index + 1) % total_players
            user_id = session.player_ids[turn_index]
            if session.state.get("timeless") or session.state["lives"].get(user_id, 0) > 0:
                session.state["turn_index"] = turn_index
                session.state["current_player_id"] = user_id
                return user_id
        return None

    @staticmethod
    def _clean_extra_sequences(values: Any) -> tuple[str, ...]:
        if not isinstance(values, (list, tuple, set)):
            return ()
        cleaned: list[str] = []
        for value in values:
            letters = "".join(ch for ch in str(value).casefold() if ch.isalpha())
            if len(letters) == 3 and letters not in cleaned:
                cleaned.append(letters)
        return tuple(cleaned)

    def _build_sequence_bag(self, session: GameSession) -> list[str]:
        difficulty = normalize_difficulty(session.state["difficulty"])
        sequences = list(dict.fromkeys(session.state.get("extra_sequences", ())))
        RANDOMIZER.shuffle(sequences)
        last_opening = self._last_opening_sequence.get(difficulty)
        if len(sequences) > 1 and sequences[-1] == last_opening:
            sequences[0], sequences[-1] = sequences[-1], sequences[0]
        return sequences

    def _next_sequence(self, session: GameSession) -> str:
        difficulty = normalize_difficulty(session.state["difficulty"])
        remaining_sequences = session.state.setdefault("remaining_sequences", [])
        if not remaining_sequences:
            previous = session.state.get("letters")
            remaining_sequences.extend(self._build_sequence_bag(session))
            if len(remaining_sequences) > 1 and remaining_sequences[-1] == previous:
                remaining_sequences[0], remaining_sequences[-1] = (
                    remaining_sequences[-1],
                    remaining_sequences[0],
                )
            session.state["used_sequences"].clear()
        sequence = remaining_sequences.pop()
        session.state["used_sequences"].add(sequence)
        if session.state.get("round_number") == 1:
            self._last_opening_sequence[difficulty] = sequence
        return sequence

    async def _cancel_round_timer(self, session: GameSession) -> None:
        task = session.state.get("round_timer_task")
        current_task = asyncio.current_task()
        if task and task is not current_task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if task is not current_task:
            session.state["round_timer_task"] = None

    def _schedule_round_timer(
        self,
        session: GameSession,
        round_message: discord.Message,
        initial_wait: int = 0,
    ) -> None:
        session.state["round_token"] = session.state.get("round_token", 0) + 1
        token = session.state["round_token"]
        seconds = session.state["round_seconds"]
        if seconds is None:
            return
        session.state["round_timer_task"] = asyncio.create_task(
            self._run_round_timer(session, round_message, token, seconds, initial_wait)
        )

    @staticmethod
    def _is_current_round(session: GameSession, token: int) -> bool:
        return (
            not session.state.get("finished")
            and not session.state.get("round_resolved")
            and session.state.get("round_token") == token
        )

    async def _run_round_timer(
        self,
        session: GameSession,
        round_message: discord.Message,
        token: int,
        seconds: int,
        initial_wait: int = 0,
    ) -> None:
        try:
            if initial_wait:
                await asyncio.sleep(initial_wait)
                if not self._is_current_round(session, token):
                    return
            await asyncio.sleep(max(0, seconds - len(COUNTDOWN_EMOJIS)))
            for emoji in COUNTDOWN_EMOJIS:
                if not self._is_current_round(session, token):
                    return
                try:
                    await round_message.add_reaction(emoji)
                except (discord.HTTPException, discord.Forbidden):
                    pass
                await asyncio.sleep(1)
            async with session.state["validation_lock"]:
                if self._is_current_round(session, token):
                    await self._time_out_round(session, round_message.channel)
        except asyncio.CancelledError:
            raise
        finally:
            if session.state.get("round_timer_task") is asyncio.current_task():
                session.state["round_timer_task"] = None

    @staticmethod
    def validate_word(word: str, letters: str, difficulty: str = "easy") -> bool:
        """Check structure; dictionary validity is checked asynchronously afterward."""
        return (
            word.isalpha()
            and len(word) > len(letters)
            and letters in word
        )

    @staticmethod
    def _dictionary_candidates(word: str) -> list[str]:
        """Return conservative base forms for ordinary English inflections."""
        candidates = [word]
        if word.endswith("ies") and len(word) > 4:
            candidates.append(f"{word[:-3]}y")
        if word.endswith("es") and len(word) > 4:
            candidates.extend((word[:-1], word[:-2]))
        elif word.endswith("s") and len(word) > 3:
            candidates.append(word[:-1])
        if word.endswith("ing") and len(word) > 5:
            stem = word[:-3]
            candidates.extend((stem, f"{stem}e"))
            if len(stem) > 2 and stem[-1] == stem[-2]:
                candidates.append(stem[:-1])
        if word.endswith("ed") and len(word) > 4:
            stem = word[:-2]
            candidates.extend((stem, f"{stem}e"))
            if len(stem) > 2 and stem[-1] == stem[-2]:
                candidates.append(stem[:-1])

        return list(dict.fromkeys(item for item in candidates if item.isalpha()))

    @staticmethod
    def _extract_definition(result: dict[str, Any]) -> str | None:
        for meaning in result.get("meanings", []):
            part = meaning.get("partOfSpeech", "").strip()
            for item in meaning.get("definitions", []):
                definition = item.get("definition", "").strip()
                if definition:
                    return f"{part}: {definition}" if part else definition
        return None

    async def _lookup_definition(self, word: str) -> tuple[str | None, bool]:
        """Return (definition, service_available), accepting normal inflections.

        The dictionary providers are the source of truth. If neither provider
        can answer, return ``service_available=False`` so the game can stop
        cleanly instead of guessing whether a word is real.
        """
        if word in self._definition_cache:
            return self._definition_cache[word], True

        deadline = asyncio.get_running_loop().time() + DICTIONARY_LOOKUP_TIMEOUT_SECONDS
        if self._dictionary_session is None or self._dictionary_session.closed:
            self._dictionary_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=DICTIONARY_LOOKUP_TIMEOUT_SECONDS)
            )
        for candidate in self._dictionary_candidates(word):
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return None, False
            try:
                result = await fetch_meaning(
                    candidate,
                    self._dictionary_session,
                    timeout_seconds=remaining,
                )
            except DefinitionNotFound:
                continue
            except (DictionaryUnavailable, aiohttp.ClientError, TimeoutError):
                return None, False

            definition = self._extract_definition(result)
            if definition:
                if candidate != word:
                    definition = f"an inflected form of **{candidate}** — {definition}"
                self._definition_cache[word] = definition
                return definition, True

        self._definition_cache[word] = None
        return None, True

    async def _advance_after_round(self, session: GameSession, channel, notice: str = "") -> None:
        if not session.state.get("timeless") and len(session.player_ids) > 1:
            active = self._active_player_ids(session)
            if len(active) == 1:
                await self._show_results(session, channel, notice, survivor_id=active[0])
                return
        if self._active_player_ids(session):
            await self._start_round(session, channel, notice)
        else:
            await self._show_results(session, channel, notice)

    @staticmethod
    def _lose_life(session: GameSession, user_id: int) -> int:
        lives = session.state["lives"]
        lives[user_id] = max(0, lives.get(user_id, 0) - 1)
        return lives[user_id]

    def _penalize_unanswered(self, session: GameSession) -> list[int]:
        if session.state.get("timeless"):
            return []
        user_id = self._current_player_id(session)
        if user_id is None or session.is_answered_by(user_id):
            return []
        self._lose_life(session, user_id)
        return [user_id]

    @staticmethod
    def _life_loss_summary(session: GameSession, user_ids: list[int]) -> str:
        if not user_ids:
            return ""
        lives = session.state["lives"]
        return "\n".join(
            f"💥 <@{user_id}> -1 HP ({lives.get(user_id, 0)} left)"
            for user_id in user_ids
        )

    async def _time_out_round(self, session: GameSession, channel) -> None:
        session.state["round_resolved"] = True
        penalized = self._penalize_unanswered(session)
        lines = ["⏰ Time's up!"]
        summary = self._life_loss_summary(session, penalized)
        if summary:
            lines.append(summary)
        await self._advance_after_round(session, channel, "\n".join(lines))

    @staticmethod
    async def _add_reaction(message: discord.Message, emoji: str) -> None:
        try:
            await message.add_reaction(emoji)
        except (discord.HTTPException, discord.Forbidden):
            pass

    async def _reject_entry(self, message: discord.Message) -> None:
        await self._add_reaction(message, CROSS_REACTION)

    async def _reject_reused_word(self, message: discord.Message, word: str) -> None:
        await self._add_reaction(message, CROSS_REACTION)
        await message.reply(
            f"**{word}** was already used. Try another word.",
            mention_author=False,
        )

    async def _reject_prompt_copy(self, message: discord.Message, letters: str) -> None:
        await self._add_reaction(message, CROSS_REACTION)
        await message.reply(
            f"**{letters}** is the prompt itself. Brainstorm a bit more - "
            f"use **{letters.upper()}** inside a longer word.",
            mention_author=False,
        )

    async def _reject_unverified_word(
        self,
        message: discord.Message,
        word: str,
    ) -> None:
        await self._reject_entry(message)
        await message.reply(
            f"**{word}** was not found as a verified English word.",
            mention_author=False,
        )

    async def _stop_for_dictionary_outage(
        self,
        session: GameSession,
        message: discord.Message,
    ) -> None:
        """Stop safely when no provider can verify a submitted word."""
        session.state["finished"] = True
        session.state["round_resolved"] = True
        await self._cancel_round_timer(session)
        await self._add_reaction(message, CROSS_REACTION)
        await message.reply(
            "⚠️ Dictionary verification is currently unavailable from both "
            "providers, so I stopped CherryWords instead of guessing. No HP or "
            "attempt was used. Try `luna trivia` or another game instead. 🌸",
            mention_author=False,
        )
        await self._close_dictionary_session()

    def _restart_round_timer(self, session: GameSession) -> None:
        if session.state.get("timeless") or session.state.get("round_resolved"):
            return
        round_message = session.state.get("round_message")
        if round_message is not None:
            self._schedule_round_timer(session, round_message)

    @staticmethod
    def _meaning_preview(word: str, definition: str) -> str:
        compact = " ".join(definition.replace("\n", " ").split())
        if len(compact) > MEANING_PREVIEW_LIMIT:
            compact = compact[:MEANING_PREVIEW_LIMIT].rstrip(" ,;:-") + "…"
        return f"💡 **{word}**: {compact}"

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        expected_round = session.state["round_number"]
        async with session.state["validation_lock"]:
            # Ignore queued spam from the previous round after it has advanced.
            if expected_round != session.state["round_number"]:
                return
            if session.state.get("round_resolved"):
                return

            user_id = message.author.id
            if user_id != session.state.get("current_player_id"):
                return
            if not session.state.get("timeless") and session.state["lives"].get(user_id, 0) <= 0:
                await message.reply(
                    "You're out of lives for this CherryWords run.",
                    mention_author=False,
                )
                return
            if session.is_answered_by(user_id):
                await message.reply(
                    "Your valid word is already locked in for this round.",
                    mention_author=False,
                )
                return

            word = message.content.strip().casefold()
            if not word:
                return

            # The first word check may call the external dictionary and take
            # longer than Discord's visible countdown. Pause the timer before
            # validating; invalid attempts restart a full timer afterward.
            first_input_check = bool(session.state.get("first_input_pending"))
            session.state["first_input_pending"] = False
            if first_input_check and not session.state.get("timeless"):
                await self._cancel_round_timer(session)

            letters = session.state["letters"]
            if word == letters:
                await self._reject_prompt_copy(message, letters)
                if first_input_check:
                    self._restart_round_timer(session)
                return
            if not self.validate_word(word, letters, session.state["difficulty"]):
                await self._reject_entry(message)
                if first_input_check:
                    self._restart_round_timer(session)
                return
            if word in session.state["used_words"]:
                await self._reject_reused_word(message, word)
                if first_input_check:
                    self._restart_round_timer(session)
                return

            definition, service_available = await self._lookup_definition(word)
            if definition is None:
                if not service_available:
                    await self._stop_for_dictionary_outage(session, message)
                    return
                await self._reject_unverified_word(message, word)
                if first_input_check:
                    self._restart_round_timer(session)
                return

            attempts = session.state["attempts"]
            attempts[user_id] = attempts.get(user_id, 0) + 1
            session.state["round_resolved"] = True
            session.state["used_words"].add(word)
            session.mark_answered(user_id)
            session.increment_score(user_id)
            await self._add_reaction(message, CORRECT_REACTION)
            if session.state.get("show_meanings"):
                await message.reply(
                    self._meaning_preview(word, definition),
                    mention_author=False,
                )
            await self._start_round(session, message.channel)

    async def _show_results(
        self,
        session: GameSession,
        channel,
        notice: str = "",
        survivor_id: int | None = None,
    ) -> None:
        if session.state.get("finished"):
            return
        await self._cancel_round_timer(session)
        session.state["finished"] = True
        prefix = f"{notice}\n" if notice else ""
        winner_line = format_winner_line(
            session.score,
            winner_ids=[survivor_id] if survivor_id is not None else None,
            reason="last player standing" if survivor_id is not None else "",
        )
        await channel.send(
            f"{prefix}🏆 **CherryWords complete**\n"
            f"Rounds played: **{session.state.get('round_number', 0)}**\n"
            f"{winner_line}\n"
            f"{format_score_board(session.score)}"
        )

    async def end(self, session: GameSession) -> None:
        await self._cancel_round_timer(session)
        session.state["finished"] = True
        await self._close_dictionary_session()

    async def timeout(self, session: GameSession) -> None:
        await self._cancel_round_timer(session)
        session.state["finished"] = True
        await self._close_dictionary_session()

    async def _close_dictionary_session(self) -> None:
        if self._dictionary_session is not None and not self._dictionary_session.closed:
            await self._dictionary_session.close()


# Backwards-compatible name used by earlier bot revisions.
CherryWordsArena = CherryWordsArenaGame
