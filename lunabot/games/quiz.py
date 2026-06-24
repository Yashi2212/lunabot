"""Multiplayer quiz with one answer per player per question."""

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board
from .difficulty import level_label, normalize_difficulty


class QuizGame(BaseGame):
    name = "quiz"
    description = "Multiplayer quiz with independent scoring"
    max_players = 5

    async def start(self, session: GameSession, ctx) -> None:
        questions = session.state.get("questions", [])[:10]
        if not questions:
            session.state["finished"] = True
            await ctx.reply("🌙 Quiz setup was incomplete.", mention_author=False)
            return
        session.state.update(questions=questions, question_index=0)
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        session.state["difficulty"] = difficulty
        await ctx.reply(
            f"📝 **Quiz Battle started** with {len(session.player_ids)} player(s). "
            f"Level: **{level_label(difficulty)}**.\n"
            "**How to play:** Everyone replies A-D once; correct answers earn individual points.\n"
            "**Example:** 15% of 200? A) 20 B) 30 → reply `B`.\n"
            "After everyone answers, Luna reveals and explains the correct answer.",
            mention_author=False,
        )
        await self._ask_question(session, ctx.channel)

    async def _ask_question(self, session: GameSession, channel) -> None:
        index = session.state["question_index"]
        questions = session.state["questions"]
        if index >= len(questions):
            session.state["finished"] = True
            await channel.send(f"🏆 **Quiz complete!**\n{format_score_board(session.score)}")
            return
        question = questions[index]
        session.state["current_question_data"] = question
        session.state["advancing"] = False
        session.reset_answered()
        options = "\n".join(f"{letter}) {text}" for letter, text in zip("ABCD", question["options"]))
        await channel.send(
            f"**Question {index + 1}/{len(questions)}** — "
            f"Level: **{level_label(question.get('difficulty', session.state['difficulty']))}**\n"
            f"{question['question']}\n\n{options}"
        )

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        user_id = message.author.id
        if session.state.get("advancing") or session.is_answered_by(user_id):
            return
        choice = message.content.strip().upper()
        if choice not in "ABCD" or len(choice) != 1:
            return
        question = session.state["current_question_data"]
        session.mark_answered(user_id)
        if choice == str(question["correct_answer"]).upper():
            session.increment_score(user_id)
        await message.reply("🔒 Answer locked in. Results appear after everyone answers.", mention_author=False)

        if len(session.answered_users) >= len(session.player_ids):
            session.state["advancing"] = True
            answer = question["options"][ord(str(question["correct_answer"]).upper()) - 65]
            explanation = question.get("explanation", "Use this explanation to remember the answer.")
            await message.channel.send(
                f"✅ **Correct answer:** {answer}\n💡 **Explanation:** {explanation}"
            )
            session.state["question_index"] += 1
            await self._ask_question(session, message.channel)

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
