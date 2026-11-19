"""Multiplayer word-jumble race with per-player attempts."""

from __future__ import annotations

import asyncio
import contextlib
import random
import re
from typing import Any

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board, format_winner_line
from .difficulty import level_label, normalize_difficulty
from .round_plan import MIXED_LEVEL_LABEL, ROUND_SIZE, has_round_distribution


TURNS_BY_DIFFICULTY = {"easy": 3, "medium": 2, "hard": 1}
# Every jumbled challenge gets a full 30-second answer window. The difficulty
# still controls the number of attempts, not whether players have enough time
# to read and solve the prompt.
ROUND_SECONDS_BY_DIFFICULTY = {"easy": 30, "medium": 30, "hard": 30}
LIFE_EMOJIS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣"}
COUNTDOWN_EMOJIS = ("3️⃣", "2️⃣", "1️⃣")


def _normal(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalpha())


def _fingerprint(item: dict[str, Any]) -> str:
    return _normal(str(item.get("word", "")))


def _scramble(word: str) -> str:
    """Return a shuffled spelling, guaranteeing it differs from the answer."""
    letters = list(word.casefold())
    if len(letters) < 2:
        return word.casefold()
    original = "".join(letters)
    for _ in range(12):
        random.shuffle(letters)
        scrambled = "".join(letters)
        if scrambled != original:
            return scrambled
    # Repeated letters can make random shuffles land on the original. A
    # rotation is deterministic and still looks like a genuine jumble.
    return original[1:] + original[:1]


def _answer_candidates(session: GameSession) -> set[str]:
    answer = _normal(str(session.state["answer"]))
    candidates = {answer}
    for value in session.state.get("accepted_answers", []) or []:
        normalized = _normal(str(value))
        if normalized:
            candidates.add(normalized)
    return candidates


def _all_players_done(session: GameSession) -> bool:
    turns = session.state.setdefault("turns_left", {})
    solved = session.state.setdefault("solved_players", set())
    return bool(session.player_ids) and all(
        user_id in solved or turns.get(user_id, 0) <= 0
        for user_id in session.player_ids
    )


async def _react(target: Any, *emojis: str) -> None:
    add_reaction = getattr(target, "add_reaction", None)
    if add_reaction is None:
        return
    for emoji in emojis:
        try:
            await add_reaction(emoji)
        except (discord.HTTPException, discord.Forbidden):
            return


class JumbledWordGame(BaseGame):
    name = "messed"
    description = "Ten-round multiplayer jumbled-word competition"
    max_players = 10

    async def start(self, session: GameSession, ctx) -> None:
        values = [
            {
                **item,
                "difficulty": normalize_difficulty(item.get("difficulty")),
            }
            for item in session.state.get("words", []) or []
            if isinstance(item, dict) and _normal(str(item.get("word", "")))
        ]
        if len(values) != ROUND_SIZE or not has_round_distribution(
            item["difficulty"] for item in values
        ):
            session.state["finished"] = True
            await ctx.reply(
                f"🌙 Jumbled Words setup needs exactly {ROUND_SIZE} challenges with the "
                "fixed 2 Difficult, 3 Moderate, 5 Easy mix.",
                mention_author=False,
            )
            return

        random.shuffle(values)
        difficulty = values[0]["difficulty"]
        turn_limit = TURNS_BY_DIFFICULTY[difficulty]
        timeout_budget = sum(
            ROUND_SECONDS_BY_DIFFICULTY[item["difficulty"]] + 3 for item in values
        )
        session.state.update(
            words=values,
            difficulty=difficulty,
            round_seconds=ROUND_SECONDS_BY_DIFFICULTY[difficulty],
            timeout_seconds=max(
                120,
                timeout_budget + 60,
            ),
            round_timer_task=None,
            round_token=0,
            round_index=0,
            rounds_total=len(values),
            answer="",
            jumble="",
            turns_left={user_id: turn_limit for user_id in session.player_ids},
            guesses_by_player={user_id: set() for user_id in session.player_ids},
            solved_players=set(),
            round_resolved=False,
            answer_lock=asyncio.Lock(),
            finished=False,
            results_sent=False,
        )
        await ctx.reply(
            f"🔤 **Luna Jumbled Words** · {len(session.player_ids)} player(s) · "
            f"{MIXED_LEVEL_LABEL}\n"
            f"**{ROUND_SIZE} challenges in this round:** 2 difficult, 3 moderate, and 5 easy.\n"
            "Unscramble the letters and send the answer. The first correct answer "
            "earns +1 point. Each jumble has a difficulty-based timer.",
            mention_author=False,
        )
        await self._ask_word(session, ctx.channel)

    async def _ask_word(
        self,
        session: GameSession,
        channel,
        resolution: str | None = None,
    ) -> None:
        index = session.state["round_index"]
        words = session.state["words"]
        if index >= len(words):
            await self._finish(session, channel, resolution)
            return

        item = words[index]
        answer = _normal(str(item["word"]))
        difficulty = normalize_difficulty(item.get("difficulty"))
        turn_limit = TURNS_BY_DIFFICULTY[difficulty]
        round_seconds = ROUND_SECONDS_BY_DIFFICULTY[difficulty]
        session.state.update(
            answer=answer,
            accepted_answers=item.get("accepted_answers", []) or [],
            definition=item.get("definition", "A useful word to add to your vocabulary."),
            jumble=_scramble(answer),
            difficulty=difficulty,
            turn_limit=turn_limit,
            round_seconds=round_seconds,
            round_resolved=False,
            turns_left={
                user_id: turn_limit
                for user_id in session.player_ids
            },
            guesses_by_player={user_id: set() for user_id in session.player_ids},
            solved_players=set(),
        )
        session.reset_answered()
        prompt = (
            f"🔤 **Jumbled {index + 1}/{len(words)}** · "
            f"{level_label(difficulty)}\n"
            f"Unscramble: **{session.state['jumble'].upper()}**\n"
            f"Reply with the word you think it is. 💗 **{LIFE_EMOJIS[turn_limit]}** each · "
            f"⏱️ **{round_seconds}s**"
        )
        round_message = await channel.send(f"{resolution}\n\n{prompt}" if resolution else prompt)
        self._schedule_round_timer(session, round_message)

    async def _cancel_round_timer(self, session: GameSession) -> None:
        task = session.state.get("round_timer_task")
        current_task = asyncio.current_task()
        if task and task is not current_task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if task is not current_task:
            session.state["round_timer_task"] = None

    def _schedule_round_timer(self, session: GameSession, round_message: discord.Message) -> None:
        session.state["round_token"] = session.state.get("round_token", 0) + 1
        token = session.state["round_token"]
        session.state["round_timer_task"] = asyncio.create_task(
            self._run_round_timer(
                session,
                round_message,
                token,
                session.state["round_seconds"],
            )
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
    ) -> None:
        try:
            await asyncio.sleep(max(0, seconds - len(COUNTDOWN_EMOJIS)))
            for emoji in COUNTDOWN_EMOJIS:
                if not self._is_current_round(session, token):
                    return
                try:
                    await round_message.add_reaction(emoji)
                except (discord.HTTPException, discord.Forbidden, discord.NotFound, AttributeError):
                    pass
                await asyncio.sleep(1)
            lock = session.state.setdefault("answer_lock", asyncio.Lock())
            async with lock:
                if self._is_current_round(session, token):
                    session.state["round_resolved"] = True
                    await self._advance(
                        session,
                        round_message.channel,
                        f"⏰ Time's up! Nobody solved it · Answer: **{session.state['answer']}**\n"
                        f"💡 {session.state.get('definition', 'That is the unscrambled word.')}",
                    )
        except asyncio.CancelledError:
            raise
        finally:
            if session.state.get("round_timer_task") is asyncio.current_task():
                session.state["round_timer_task"] = None

    async def _advance(
        self,
        session: GameSession,
        channel,
        resolution: str | None = None,
    ) -> None:
        await self._cancel_round_timer(session)
        if session.state["round_index"] + 1 >= session.state["rounds_total"]:
            session.state["finished"] = True
            await self._finish(session, channel, resolution)
            return
        session.state["round_index"] += 1
        await self._ask_word(session, channel, resolution)

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        raw_guess = message.content.strip()
        if not raw_guess:
            return
        expected_round = session.state.get("round_index", 0)
        lock = session.state.setdefault("answer_lock", asyncio.Lock())
        async with lock:
            if (
                session.state.get("finished")
                or session.state.get("round_resolved")
                or expected_round != session.state.get("round_index", 0)
            ):
                return

            user_id = message.author.id
            turns = session.state.setdefault("turns_left", {})
            solved = session.state.setdefault("solved_players", set())
            if user_id in solved:
                return
            if turns.get(user_id, 0) <= 0:
                await _react(message, "🚫")
                return

            guess = _normal(raw_guess)
            guesses = session.state.setdefault("guesses_by_player", {}).setdefault(user_id, set())
            if not guess:
                return
            if guess in guesses:
                await _react(message, "🔁")
                return

            guesses.add(guess)
            turns[user_id] -= 1
            if guess in _answer_candidates(session):
                session.state["round_resolved"] = True
                solved.add(user_id)
                session.increment_score(user_id)
                resolution = (
                    f"✅ <@{user_id}> **+1 point** · Answer: **{session.state['answer']}**\n"
                    f"💡 {session.state.get('definition', 'That is the unscrambled word.') }"
                )
                await _react(message, "✅")
                await self._advance(session, message.channel, resolution)
                return

            remaining = turns[user_id]
            await _react(message, "❌", LIFE_EMOJIS.get(remaining, "💀"))
            if _all_players_done(session):
                session.state["round_resolved"] = True
                await self._advance(
                    session,
                    message.channel,
                    f"🌙 Nobody solved it · Answer: **{session.state['answer']}**\n"
                    f"💡 {session.state.get('definition', 'That is the unscrambled word.')}",
                )

    async def _finish(
        self,
        session: GameSession,
        channel,
        resolution: str | None = None,
    ) -> None:
        if session.state.get("results_sent"):
            return
        session.state["finished"] = True
        session.state["results_sent"] = True
        winner_line = format_winner_line(
            session.score,
            winner_ids=[session.player_ids[0]] if len(session.player_ids) == 1 else None,
        )
        final_message = (
            "🏆 **Jumbled Words complete!**\n"
            f"{winner_line}\n"
            f"**Final scores**\n{format_score_board(session.score)}"
        )
        await channel.send(f"{resolution}\n\n{final_message}" if resolution else final_message)

    async def end(self, session: GameSession) -> None:
        await self._cancel_round_timer(session)
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        await self._cancel_round_timer(session)
        session.state["finished"] = True
