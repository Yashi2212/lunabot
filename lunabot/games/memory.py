"""Timed emoji-memory game answered by reacting to each position in order."""

from __future__ import annotations

import asyncio
import contextlib
import random
from typing import Any

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board, format_winner_line
from .difficulty import level_label
from .round_plan import MIXED_LEVEL_LABEL, ROUND_SIZE, build_round_plan


DISPLAY_SECONDS_BY_DIFFICULTY = {"easy": 6, "medium": 5, "hard": 3}
SEQUENCE_LENGTH = 5
ROUNDS_PER_GAME = ROUND_SIZE
ANSWER_SECONDS = 45
MEMORY_EMOJIS = (
    # Faces and expressions.
    "😀", "😃", "😄", "😁", "😆", "😅", "😂", "🤣", "🙂", "🙃", "😉", "😊",
    "😇", "🥰", "😍", "🤩", "😘", "😗", "😚", "😋", "😛", "😜", "🤪", "🤨",
    "🧐", "🤓", "😎", "😏", "😒", "🙄", "😬", "🤔", "🤭", "🤫", "🤥", "😶",
    "😐", "😑", "😌", "😔", "😪", "🤤", "😴", "😷", "🤒", "🤕", "🤢", "🤮",
    "🤧", "🥵", "🥶", "🥴", "😵", "🤯", "🤠", "🥳", "😱", "😨", "😰", "😥",
    "😓", "🤗", "😮", "😲", "🥺", "😳", "😡", "😤", "😭", "😢", "😞", "😟",
    "😕", "🙁", "☹️", "😣", "😖", "😫", "😩", "🥱", "😠", "🤬", "😈",
    # Food and drinks.
    "🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🫐", "🍈", "🍒", "🍑",
    "🥭", "🍍", "🥥", "🥝", "🍅", "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🫑",
    "🥒", "🥬", "🥦", "🧄", "🧅", "🍞", "🥐", "🥖", "🥨", "🧀", "🥚", "🍳",
    "🧈", "🥞", "🧇", "🥓", "🥩", "🍗", "🍔", "🍟", "🍕", "🌭", "🌮", "🌯",
    "🥗", "🍿", "🍪", "🍩", "🍰", "🧁", "🍫", "🍭", "🍬", "🍯", "☕", "🍵",
    "🥤", "🧋", "🍺", "🍷", "🍹", "🍸",
    # Hands and actions.
    "👍", "👎", "👌", "✌️", "🤞", "🤟", "🤘", "🤙", "👈", "👉", "👆", "👇",
    "☝️", "✋", "🤚", "🖐️", "🖖", "👋", "🤏", "💪", "🙏", "👏", "🙌", "👐",
    "🤲", "💅", "🤝", "🙋", "💁", "🙆", "🙅", "🤷", "🤦", "🚶", "🏃", "🧘",
    # Animals and nature.
    "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮",
    "🐷", "🐸", "🐵", "🙈", "🙉", "🙊", "🐔", "🐧", "🐦", "🐤", "🦄", "🐝",
    "🦋", "🐌", "🐞", "🐢", "🐍", "🦎", "🐙", "🦀", "🐠", "🐟", "🐬", "🐳",
    "🌱", "🌲", "🌳", "🌴", "🌵", "🌷", "🌹", "🌺", "🌻", "🌼", "🌸", "🍀",
    "🍁", "🍂", "🍃", "🌙", "☀️", "🌤️", "🌧️", "⛈️", "🌈", "❄️", "⭐", "🌟",
    "✨", "🔥", "💧", "🌊", "🌪️", "☁️",
    # Travel, games, objects, and symbols.
    "🚗", "🚕", "🚌", "🚲", "✈️", "🚀", "🚁", "⛵", "🚢", "⚽", "🏀", "🏈",
    "⚾", "🎾", "🏐", "🏆", "🎯", "🎲", "🎸", "🎹", "🎺", "🎧", "📚", "✏️",
    "🔑", "🔒", "💡", "📌", "📎", "🎁", "⏰", "📱", "💻", "📷", "🔍", "🧭",
    "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💖", "💯", "✅",
    "❌", "❗", "❓", "⚡", "🔔", "🎉", "🎈", "🎵", "🎶", "☮️", "♻️", "☯️",
    # World flags.
    "🇮🇳", "🇺🇸", "🇬🇧", "🇨🇦", "🇦🇺", "🇯🇵", "🇰🇷", "🇨🇳", "🇫🇷", "🇩🇪", "🇮🇹",
    "🇪🇸", "🇧🇷", "🇲🇽", "🇿🇦", "🇸🇬", "🇦🇪", "🇳🇵", "🇳🇿", "🇵🇭", "🇵🇰", "🇧🇩",
    "🇱🇰", "🇹🇭", "🇹🇷", "🇪🇬", "🇬🇷", "🇳🇴", "🇸🇪", "🇨🇭", "🇦🇷", "🇵🇹",
)
POSITION_LABELS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣")


def _format_sequence(sequence: list[str] | tuple[str, ...]) -> str:
    return "  |  ".join(sequence)


async def _safe_add_reaction(message: Any, emoji: str) -> None:
    add_reaction = getattr(message, "add_reaction", None)
    if add_reaction is None:
        return
    try:
        await add_reaction(emoji)
    except (discord.HTTPException, discord.Forbidden, discord.NotFound):
        pass


class MemoryGame(BaseGame):
    name = "memo"
    description = "Timed emoji-memory sequence challenge"
    max_players = 10

    async def start(self, session: GameSession, ctx) -> None:
        difficulty_plan = build_round_plan()
        difficulty = difficulty_plan[0]
        display_seconds = DISPLAY_SECONDS_BY_DIFFICULTY[difficulty]
        session.state.update(
            difficulty=difficulty,
            difficulty_plan=difficulty_plan,
            display_seconds=display_seconds,
            round_number=0,
            rounds_total=ROUNDS_PER_GAME,
            used_sequences=set(),
            phase="starting",
            round_resolved=False,
            finished=False,
            # Five answer windows can outlast the global 120-second default;
            # keep the session alive while the game's own answer timer runs.
            timeout_seconds=sum(
                ANSWER_SECONDS + DISPLAY_SECONDS_BY_DIFFICULTY[level]
                for level in difficulty_plan
            ) + 60,
            answer_lock=asyncio.Lock(),
            answer_timer_task=None,
            last_sequence=(),
        )
        await ctx.reply(
            f"🧠 **Luna Memo** · {MIXED_LEVEL_LABEL}\n"
            f"**{ROUNDS_PER_GAME} memory challenges in this round:** "
            "2 difficult, 3 moderate, and 5 easy.\n"
            f"Memorize a row of {SEQUENCE_LENGTH} emojis. It stays visible for "
            "a difficulty-based time, then disappears.\n"
            "After it vanishes, react to each position's emoji choice in order "
            "from 1 to 5. A complete correct row earns +1 point.",
            mention_author=False,
        )
        await self._start_round(session, ctx.channel)

    @staticmethod
    def _next_sequence(session: GameSession) -> list[str]:
        used = session.state.setdefault("used_sequences", set())
        previous = set(session.state.get("last_sequence", ()))
        for _ in range(100):
            sequence = random.sample(MEMORY_EMOJIS, SEQUENCE_LENGTH)
            fingerprint = "".join(sorted(sequence))
            overlap = len(previous.intersection(sequence))
            if fingerprint not in used and (not previous or overlap <= 1):
                used.add(fingerprint)
                session.state["last_sequence"] = tuple(sequence)
                return sequence
        # There are thousands of possible rows, so this is only a defensive
        # fallback for a test with an unusually large number of rounds.
        sequence = random.sample(MEMORY_EMOJIS, SEQUENCE_LENGTH)
        used.add("".join(sorted(sequence)))
        session.state["last_sequence"] = tuple(sequence)
        return sequence

    async def _cancel_answer_timer(self, session: GameSession) -> None:
        task = session.state.get("answer_timer_task")
        current_task = asyncio.current_task()
        if task and task is not current_task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if task is not current_task:
            session.state["answer_timer_task"] = None

    async def _start_round(self, session: GameSession, channel) -> None:
        await self._cancel_answer_timer(session)
        if session.state.get("finished"):
            return
        if session.state["round_number"] >= session.state["rounds_total"]:
            await self._finish(session, channel)
            return

        session.state["round_number"] += 1
        round_number = session.state["round_number"]
        difficulty = session.state["difficulty_plan"][round_number - 1]
        display_seconds = DISPLAY_SECONDS_BY_DIFFICULTY[difficulty]
        sequence = self._next_sequence(session)
        session.state.update(
            sequence=sequence,
            difficulty=difficulty,
            display_seconds=display_seconds,
            phase="showing",
            round_resolved=False,
            answers={user_id: [] for user_id in session.player_ids},
            completed_users=set(),
            position_message_ids={},
            position_options={},
        )
        reveal_message = await channel.send(
            f"👀 **Memory {round_number}/{session.state['rounds_total']}** · "
            f"{level_label(difficulty)}\n"
            f"{_format_sequence(sequence)}\n"
            f"You have {display_seconds} seconds — memorize the order!"
        )
        session.state["reveal_message_id"] = reveal_message.id
        await asyncio.sleep(session.state["display_seconds"])
        if session.state.get("finished") or session.state.get("round_number") != round_number:
            return

        hidden_content = (
            f"🙈 **Memory {round_number}/{session.state['rounds_total']}** · "
            f"{level_label(difficulty)} — sequence hidden!\n"
            "React to the five position prompts below, from position 1 through position 5."
        )
        try:
            await reveal_message.edit(content=hidden_content)
        except (discord.HTTPException, discord.Forbidden, discord.NotFound, AttributeError):
            await channel.send(hidden_content)

        session.state["phase"] = "answering"
        for position in range(SEQUENCE_LENGTH):
            options = list(sequence)
            random.shuffle(options)
            position_message = await channel.send(
                f"{POSITION_LABELS[position]} **Position {position + 1}/{SEQUENCE_LENGTH}** — "
                "react with the emoji you remember here."
            )
            session.state["position_message_ids"][position_message.id] = position
            session.state["position_options"][position] = options
            for emoji in options:
                await _safe_add_reaction(position_message, emoji)

        token = round_number
        session.state["answer_timer_task"] = asyncio.create_task(
            self._run_answer_timer(session, channel, token)
        )

    async def _run_answer_timer(self, session: GameSession, channel, token: int) -> None:
        try:
            await asyncio.sleep(ANSWER_SECONDS)
            lock = session.state.setdefault("answer_lock", asyncio.Lock())
            async with lock:
                if (
                    session.state.get("finished")
                    or session.state.get("phase") != "answering"
                    or session.state.get("round_number") != token
                ):
                    return
                session.state["round_resolved"] = True
                await self._advance_round(
                    session,
                    channel,
                    f"⏰ Time's up! The sequence was **{_format_sequence(session.state['sequence'])}**.",
                )
        except asyncio.CancelledError:
            raise
        finally:
            if session.state.get("answer_timer_task") is asyncio.current_task():
                session.state["answer_timer_task"] = None

    async def _advance_round(self, session: GameSession, channel, notice: str = "") -> None:
        session.state["phase"] = "between_rounds"
        if session.state["round_number"] >= session.state["rounds_total"]:
            await self._finish(session, channel, notice)
            return
        await channel.send(notice) if notice else None
        await self._start_round(session, channel)

    async def handle_reaction(self, session: GameSession, payload, bot) -> None:
        if session.state.get("phase") != "answering":
            return
        position = session.state.get("position_message_ids", {}).get(payload.message_id)
        if position is None:
            return
        choice = str(payload.emoji)
        options = session.state.get("position_options", {}).get(position, [])
        if choice not in options:
            return

        channel = bot.get_channel(payload.channel_id)
        if channel is None:
            return
        user_id = payload.user_id
        lock = session.state.setdefault("answer_lock", asyncio.Lock())
        async with lock:
            if session.state.get("phase") != "answering":
                return
            answers = session.state.setdefault("answers", {}).setdefault(user_id, [])
            if user_id in session.state.setdefault("completed_users", set()):
                return
            expected_position = len(answers)
            if position != expected_position:
                return

            answers.append(choice)
            if len(answers) < SEQUENCE_LENGTH:
                return

            session.state["completed_users"].add(user_id)
            correct = answers == session.state["sequence"]
            if correct:
                session.increment_score(user_id)
                result = "✅ Correct row — **+1 point**!"
            else:
                result = (
                    "❌ Not quite. The order was "
                    f"**{_format_sequence(session.state['sequence'])}**."
                )
            await channel.send(f"<@{user_id}> {result}")

            if len(session.state["completed_users"]) >= len(session.player_ids):
                session.state["round_resolved"] = True
                await self._advance_round(session, channel)

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        """Memory answers are reaction-based; text does not submit a guess."""
        return

    async def _finish(self, session: GameSession, channel, notice: str = "") -> None:
        if session.state.get("results_sent"):
            return
        await self._cancel_answer_timer(session)
        session.state.update(finished=True, phase="finished", results_sent=True)
        winner_line = format_winner_line(
            session.score,
            winner_ids=[session.player_ids[0]] if len(session.player_ids) == 1 else None,
        )
        final_message = (
            "🏆 **Memo complete!**\n"
            f"{winner_line}\n"
            f"**Final scores**\n{format_score_board(session.score)}"
        )
        await channel.send(f"{notice}\n\n{final_message}" if notice else final_message)

    async def end(self, session: GameSession) -> None:
        await self._cancel_answer_timer(session)
        session.state.update(finished=True, phase="finished")

    async def timeout(self, session: GameSession) -> None:
        await self._cancel_answer_timer(session)
        session.state.update(finished=True, phase="finished")
