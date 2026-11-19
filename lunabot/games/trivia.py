"""Multiplayer trivia where the first correct answer wins each round."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board, format_winner_line
from .difficulty import level_label, normalize_difficulty


CHOICE_EMOJIS = {"🇦": "A", "🇧": "B", "🇨": "C", "🇩": "D"}
LETTER_EMOJIS = {letter: emoji for emoji, letter in CHOICE_EMOJIS.items()}


class TriviaGame(BaseGame):
    name = "trivia"
    description = "Fast multiplayer trivia"
    max_players = 5

    async def start(self, session: GameSession, ctx) -> None:
        questions = session.state.get("questions", [])[:5]
        if not questions:
            session.state["finished"] = True
            await ctx.reply("🌙 Trivia setup was incomplete.", mention_author=False)
            return
        session.state.update(
            questions=questions,
            question_index=0,
            answer_lock=asyncio.Lock(),
            question_message_id=None,
        )
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        session.state["difficulty"] = difficulty
        await ctx.reply(
            f"🧠 **Trivia started** with {len(session.player_ids)} player(s)! "
            f"Level: **{level_label(difficulty)}**.\n"
            "**How to play:** React with 🇦, 🇧, 🇨, or 🇩—or type A-D. "
            "Each player's first answer is locked; the first correct player wins the round.\n"
            "**Example:** Capital of France? 🇦 Rome  🇧 Paris → react with 🇧.\n"
            "The correct answer and factual explanation follow every round.",
            mention_author=False,
        )
        await self._ask_question(session, ctx.channel)

    async def _ask_question(self, session: GameSession, channel) -> None:
        index = session.state["question_index"]
        questions = session.state["questions"]
        if index >= len(questions):
            await self._show_results(session, channel)
            return

        question = questions[index]
        session.state["current_question_data"] = question
        session.state["round_resolved"] = False
        session.state["question_message_id"] = None
        session.reset_answered()
        quoted_question = str(question["question"]).replace("\n", "\n> ")
        options = "\n".join(
            f"{LETTER_EMOJIS[letter]} **{letter})** {text}"
            for letter, text in zip("ABCD", question["options"])
        )
        question_message = await channel.send(
            f"**Trivia {index + 1}/{len(questions)}** — "
            f"Level: **{level_label(question.get('difficulty', session.state['difficulty']))}**\n"
            f"> **{quoted_question}**\n\n{options}\n\n"
            "React below with 🇦, 🇧, 🇨, or 🇩. Your first answer is final."
        )
        session.state["question_message_id"] = question_message.id
        for emoji in CHOICE_EMOJIS:
            try:
                await question_message.add_reaction(emoji)
            except (discord.HTTPException, discord.Forbidden):
                # Typed A-D answers remain available without reaction permissions.
                break

    async def _submit_choice(
        self,
        session: GameSession,
        user_id: int,
        choice: str,
        channel,
        respond: Callable[[str], Awaitable[None]],
    ) -> None:
        if session.state.get("round_resolved") or session.is_answered_by(user_id):
            return

        session.mark_answered(user_id)
        question = session.state["current_question_data"]
        correct_letter = str(question["correct_answer"]).upper()
        if choice == correct_letter:
            # Resolve before Discord I/O so simultaneous answers cannot win twice.
            session.state["round_resolved"] = True
            session.increment_score(user_id)
            answer = question["options"][ord(correct_letter) - 65]
            explanation = question.get("explanation", "That fact is worth remembering!")
            await respond(
                f"✅ You won this round! **Correct answer:** {answer}\n"
                f"💡 **Explanation:** {explanation}"
            )
            session.state["question_index"] += 1
            await self._ask_question(session, channel)
            return

        last_answer = len(session.answered_users) >= len(session.player_ids)
        if last_answer:
            # Claim the no-winner resolution before the first await.
            session.state["round_resolved"] = True
        await respond("❌ Incorrect.")
        if last_answer:
            answer = question["options"][ord(correct_letter) - 65]
            explanation = question.get("explanation", "That fact is worth remembering!")
            await channel.send(
                f"Nobody got it. **Correct answer:** {answer}\n"
                f"💡 **Explanation:** {explanation}"
            )
            session.state["question_index"] += 1
            await self._ask_question(session, channel)

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        choice = message.content.strip().upper()
        if choice not in "ABCD" or len(choice) != 1:
            return
        expected_index = session.state["question_index"]
        async with session.state["answer_lock"]:
            if expected_index != session.state["question_index"]:
                return

            async def respond(text: str) -> None:
                await message.reply(text, mention_author=False)

            await self._submit_choice(
                session, message.author.id, choice, message.channel, respond
            )

    async def handle_reaction(self, session: GameSession, payload, bot) -> None:
        if payload.message_id != session.state.get("question_message_id"):
            return
        choice = CHOICE_EMOJIS.get(str(payload.emoji))
        if choice is None:
            return
        channel = bot.get_channel(payload.channel_id)
        if channel is None:
            return

        expected_index = session.state["question_index"]
        async with session.state["answer_lock"]:
            if expected_index != session.state["question_index"]:
                return

            async def respond(text: str) -> None:
                await channel.send(f"<@{payload.user_id}> {text}")

            await self._submit_choice(
                session, payload.user_id, choice, channel, respond
            )

    async def _show_results(self, session: GameSession, channel) -> None:
        if session.state.get("finished"):
            return
        session.state["finished"] = True
        await channel.send(
            f"🏆 **Trivia complete!**\n"
            f"{format_winner_line(session.score)}\n"
            f"{format_score_board(session.score)}"
        )

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
