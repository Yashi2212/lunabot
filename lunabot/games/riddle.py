"""Multiplayer riddle race with per-player turns and shared hints."""

from __future__ import annotations

import asyncio
import random
import re
from difflib import SequenceMatcher
from typing import Any

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board, format_winner_line
from .difficulty import level_label, normalize_difficulty
from .round_plan import MIXED_LEVEL_LABEL, ROUND_SIZE, has_round_distribution


HINT_LIMIT = 2
TURNS_BY_DIFFICULTY = {"easy": 3, "medium": 2, "hard": 1}
LIFE_EMOJIS = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣"}


def _normal(value: str) -> str:
    """Normalize guesses while keeping words separate for multi-word answers."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _without_article(value: str) -> str:
    for article in ("a ", "an ", "the "):
        if value.startswith(article):
            return value[len(article):]
    return value


def _riddle_fingerprint(item: dict[str, Any]) -> str:
    return " ".join(str(item.get("riddle", "")).casefold().split())


def _answer_candidates(session: GameSession) -> set[str]:
    answer = _normal(str(session.state["answer"]))
    raw_answers = [answer, *(session.state.get("accepted_answers") or [])]
    candidates: set[str] = set()
    for raw_answer in raw_answers:
        candidate = _normal(str(raw_answer))
        if not candidate:
            continue
        candidates.add(candidate)
        candidates.add(_without_article(candidate))

    # Keep this common wordplay variant valid even when an AI-generated riddle
    # does not explicitly include accepted_answers.
    if answer == "footsteps":
        candidates.add("steps")
    return candidates


def _is_close_guess(guess: str, candidates: set[str]) -> bool:
    """Return whether a non-correct guess is plausibly near the answer."""
    compact_guess = guess.replace(" ", "")
    if len(compact_guess) < 4:
        return False

    for candidate in candidates:
        compact_candidate = candidate.replace(" ", "")
        if len(compact_candidate) < 4:
            continue
        if compact_guess in compact_candidate or compact_candidate in compact_guess:
            return True
        if SequenceMatcher(None, compact_guess, compact_candidate).ratio() >= 0.68:
            return True

    return False


def _hint_pattern(answer: str) -> tuple[str, int]:
    """Make a hint that exposes only each word's first letter and its length."""
    words = re.findall(r"[a-z0-9]+", answer.casefold())
    if not words:
        return "_", 0
    pattern = "   ".join(
        " ".join([word[0].upper(), *(["_"] * (len(word) - 1))])
        for word in words
    )
    return pattern, sum(len(word) for word in words)


def _turns_left(session: GameSession) -> dict[int, int]:
    turns = session.state.setdefault("turns_left", {})
    for user_id in session.player_ids:
        turns.setdefault(user_id, 0)
    return turns


def _all_players_done(session: GameSession) -> bool:
    turns = _turns_left(session)
    solved = session.state.setdefault("solved_players", set())
    return bool(session.player_ids) and all(
        user_id in solved or turns.get(user_id, 0) <= 0
        for user_id in session.player_ids
    )


async def _respond(target: Any, text: str) -> None:
    responder = getattr(target, "reply", None)
    if responder is not None:
        await responder(text, mention_author=False)
        return
    await target.send(text)


async def _react(target: Any, *emojis: str) -> None:
    """Add compact visual feedback without filling the channel with replies."""
    add_reaction = getattr(target, "add_reaction", None)
    if add_reaction is None:
        message = getattr(target, "message", None)
        add_reaction = getattr(message, "add_reaction", None)
    if add_reaction is None:
        return
    for emoji in emojis:
        try:
            await add_reaction(emoji)
        except (discord.HTTPException, discord.Forbidden):
            # Reactions are a convenience; a missing Discord permission should
            # not crash or stop the riddle session.
            return


class RiddleGame(BaseGame):
    name = "riddle"
    description = "Ten-riddle multiplayer AI competition"
    max_players = 10

    async def start(self, session: GameSession, ctx) -> None:
        if not session.state.get("riddle") or not session.state.get("answer"):
            session.state["finished"] = True
            await ctx.reply("🌙 Riddle setup was incomplete.", mention_author=False)
            return
        initial_difficulty = normalize_difficulty(session.state.get("difficulty"))
        initial_riddle = {
            "riddle": session.state["riddle"],
            "answer": session.state["answer"],
            "accepted_answers": [
                answer for answer in session.state.get("accepted_answers", []) or []
                if isinstance(answer, str) and answer.strip()
            ],
            "explanation": session.state.get("explanation", "The clues point to the answer through wordplay."),
            "difficulty": initial_difficulty,
        }
        pool: list[dict[str, Any]] = [initial_riddle]
        seen_riddles = {_riddle_fingerprint(initial_riddle)}
        for item in session.state.get("riddle_pool", []) or []:
            if not isinstance(item, dict) or not item.get("riddle") or not item.get("answer"):
                continue
            candidate = {
                "riddle": item["riddle"],
                "answer": item["answer"],
                "accepted_answers": [
                    answer for answer in item.get("accepted_answers", []) or []
                    if isinstance(answer, str) and answer.strip()
                ],
                "explanation": item.get(
                    "explanation", "The clues point to the answer through wordplay."
                ),
                "difficulty": normalize_difficulty(item.get("difficulty")),
            }
            fingerprint = _riddle_fingerprint(candidate)
            if fingerprint and fingerprint not in seen_riddles:
                pool.append(candidate)
                seen_riddles.add(fingerprint)
        random.shuffle(pool)
        if len(pool) != ROUND_SIZE or not has_round_distribution(
            item["difficulty"] for item in pool
        ):
            session.state["finished"] = True
            await ctx.reply(
                f"🌙 Riddle setup needs exactly {ROUND_SIZE} riddles with the fixed "
                "2 Difficult, 3 Moderate, 5 Easy mix.",
                mention_author=False,
            )
            return
        first_riddle = pool[0]
        difficulty = first_riddle["difficulty"]
        turn_limit = TURNS_BY_DIFFICULTY[difficulty]
        rounds_total = len(pool)
        session.state.update(
            difficulty=first_riddle["difficulty"],
            difficulty_plan=[item["difficulty"] for item in pool],
            riddle_pool=pool,
            riddle=first_riddle["riddle"],
            answer=first_riddle["answer"],
            accepted_answers=first_riddle.get("accepted_answers", []),
            explanation=first_riddle.get(
                "explanation", "The clues point to the answer through wordplay."
            ),
            used_riddles={_riddle_fingerprint(first_riddle)},
            round_index=0,
            rounds_total=rounds_total,
            round_resolved=False,
            turn_limit=turn_limit,
            turns_left={user_id: turn_limit for user_id in session.player_ids},
            guesses_by_player={user_id: set() for user_id in session.player_ids},
            solved_players=set(),
            hints_used=0,
            answer_lock=asyncio.Lock(),
            refill_in_progress=False,
            results_sent=False,
            finished=False,
        )
        await ctx.reply(
            f"🧩 **Luna Riddle Race** · {len(session.player_ids)} player(s) · "
            f"{MIXED_LEVEL_LABEL}\n"
            f"**Riddle #1:** {session.state['riddle']}\n\n"
            f"📚 **{rounds_total} riddles in this round.** Difficulty is mixed: "
            "2 difficult, 3 moderate, and 5 easy.\n"
            f"💗 Lifelines: **{LIFE_EMOJIS[turn_limit]}** for this riddle · "
            "wrong = ❌ + remaining-life emoji · correct = ✅ +1\n"
            "💡 `hint` / `luna hint` uses one of 2 shared hints.",
            mention_author=False,
        )

    async def handle_hint(self, session: GameSession, target: Any) -> None:
        """Reveal one shared letter-count hint without consuming a turn."""
        lock = session.state.setdefault("answer_lock", asyncio.Lock())
        async with lock:
            if session.state.get("finished"):
                return
            used = int(session.state.get("hints_used", 0))
            if used >= HINT_LIMIT:
                await _react(target, "🚫")
                return

            pattern, letter_count = _hint_pattern(str(session.state["answer"]))
            used += 1
            session.state["hints_used"] = used
            await _react(target, "💡")
            await _respond(
                target,
                f"💡 **Hint {used}/{HINT_LIMIT}:** `{pattern}` — {letter_count} letter"
                f"{'s' if letter_count != 1 else ''}.",
            )

    def _has_next_riddle(self, session: GameSession) -> bool:
        used = session.state.setdefault("used_riddles", set())
        return any(
            _riddle_fingerprint(item) not in used
            for item in session.state.get("riddle_pool", []) or []
            if isinstance(item, dict)
        )

    def _select_next_riddle(self, session: GameSession) -> bool:
        used = session.state.setdefault("used_riddles", set())
        for item in session.state.get("riddle_pool", []) or []:
            if not isinstance(item, dict):
                continue
            fingerprint = _riddle_fingerprint(item)
            if not fingerprint or fingerprint in used:
                continue
            session.state.update(
                riddle=item["riddle"],
                answer=item["answer"],
                accepted_answers=[
                    answer for answer in item.get("accepted_answers", []) or []
                    if isinstance(answer, str) and answer.strip()
                ],
                explanation=item.get(
                    "explanation", "The clues point to the answer through wordplay."
                ),
                difficulty=normalize_difficulty(item.get("difficulty")),
            )
            used.add(fingerprint)
            return True
        return False

    async def _refill_riddles(self, session: GameSession) -> bool:
        """Ask the command's AI provider for another bank when the queue ends."""
        generator = session.state.get("riddle_generator")
        if not callable(generator) or session.state.get("refill_in_progress"):
            return False

        session.state["refill_in_progress"] = True
        try:
            values = await generator()
        except Exception as exc:
            print(f"Unable to refill the AI riddle bank: {exc}")
            values = []
        finally:
            session.state["refill_in_progress"] = False

        if not isinstance(values, list):
            return False
        used = session.state.setdefault("used_riddles", set())
        pool = session.state.setdefault("riddle_pool", [])
        existing = {
            _riddle_fingerprint(item)
            for item in pool
            if isinstance(item, dict)
        } | used
        added = 0
        for item in values:
            if not isinstance(item, dict) or not item.get("riddle") or not item.get("answer"):
                continue
            candidate = {
                "riddle": item["riddle"],
                "answer": item["answer"],
                "accepted_answers": [
                    answer for answer in item.get("accepted_answers", []) or []
                    if isinstance(answer, str) and answer.strip()
                ],
                "explanation": item.get(
                    "explanation", "The clues point to the answer through wordplay."
                ),
            }
            fingerprint = _riddle_fingerprint(candidate)
            if fingerprint and fingerprint not in existing:
                pool.append(candidate)
                existing.add(fingerprint)
                added += 1
        session.state["rounds_total"] += added
        return added > 0

    async def _ask_riddle(
        self,
        session: GameSession,
        channel,
        resolution: str | None = None,
    ) -> None:
        session.state["round_resolved"] = False
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        turn_limit = TURNS_BY_DIFFICULTY[difficulty]
        session.state["turn_limit"] = turn_limit
        session.state["turns_left"] = {
            user_id: turn_limit for user_id in session.player_ids
        }
        session.state["guesses_by_player"] = {
            user_id: set() for user_id in session.player_ids
        }
        session.state["solved_players"] = set()
        session.reset_answered()
        index = session.state["round_index"] + 1
        life_emoji = LIFE_EMOJIS[turn_limit]
        prompt = (
            f"🧩 **Riddle #{index}/{session.state['rounds_total']}** · "
            f"{level_label(difficulty)} · "
            f"💗 {life_emoji} each\n"
            f"{session.state['riddle']}\n"
            "💡 `hint` for a shared letter clue (2 total)."
        )
        await channel.send(f"{resolution}\n\n{prompt}" if resolution else prompt)

    async def _advance_round(
        self,
        session: GameSession,
        channel,
        resolution: str | None = None,
    ) -> None:
        session.state["round_index"] += 1
        if not self._select_next_riddle(session):
            session.state["finished"] = True
            await self._finish(session, channel, resolution)
            return
        await self._ask_riddle(session, channel, resolution)

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        raw_guess = " ".join(message.content.strip().split())
        if not raw_guess:
            return
        if raw_guess.casefold() in {"hint", "take hint", "take a hint"}:
            await self.handle_hint(session, message)
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
            turns = _turns_left(session)
            guesses_by_player = session.state.setdefault("guesses_by_player", {})
            guesses = guesses_by_player.setdefault(user_id, set())
            solved = session.state.setdefault("solved_players", set())

            if user_id in solved:
                return
            if turns.get(user_id, 0) <= 0:
                await _react(message, "🚫")
                return

            guess = _normal(raw_guess)
            if not guess:
                return
            if guess in guesses:
                await _react(message, "🔁")
                return

            guesses.add(guess)
            turns[user_id] -= 1
            candidates = _answer_candidates(session)
            correct = guess in candidates or _without_article(guess) in candidates

            if correct:
                # Resolve before Discord I/O so simultaneous answers cannot win
                # the same riddle twice or answer the old riddle after advancing.
                session.state["round_resolved"] = True
                session.increment_score(user_id)
                resolution = (
                    f"✅ <@{user_id}> **+1 point** · Answer: **{session.state['answer']}**\n"
                    f"💡 {session.state.get('explanation', 'The clues point to the answer through wordplay.')}"
                )
                await _react(message, "✅")
                await self._advance_round(session, message.channel, resolution)
                return

            remaining = turns[user_id]
            close = (
                normalize_difficulty(session.state.get("difficulty")) in {"medium", "hard"}
                and _is_close_guess(guess, candidates)
            )
            reactions = ["❌", LIFE_EMOJIS.get(remaining, "💀")]
            if close:
                reactions.insert(1, "🧭")
            if _all_players_done(session):
                session.state["round_resolved"] = True
                resolution = (
                    f"🌙 Nobody solved it · Answer: **{session.state['answer']}**\n"
                    f"💡 {session.state.get('explanation', 'The clues point to the answer through wordplay.')}"
                )
            else:
                resolution = None
            await _react(message, *reactions)
            if session.state.get("round_resolved"):
                # A missed riddle still counts toward the fixed ten-riddle
                # round; it should not decide the overall winner early.
                await self._advance_round(session, message.channel, resolution)

    async def _finish(
        self,
        session: GameSession,
        channel,
        resolution: str | None = None,
    ) -> None:
        if session.state.get("results_sent"):
            return
        session.state["results_sent"] = True
        rounds_played = min(
            session.state.get("round_index", 0) + 1,
            session.state.get("rounds_total", ROUND_SIZE),
        )
        winner_line = format_winner_line(
            session.score,
            winner_ids=[session.player_ids[0]] if len(session.player_ids) == 1 else None,
        )
        final_message = (
            "🌙 **Riddle race complete!**\n"
            f"Riddles played: **{rounds_played}**\n"
            f"{winner_line}\n"
            f"**Final scores**\n{format_score_board(session.score)}"
        )
        await channel.send(
            f"{resolution}\n\n{final_message}" if resolution else final_message
        )

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
