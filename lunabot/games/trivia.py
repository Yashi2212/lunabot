"""Multiplayer trivia where the first correct answer wins each round."""

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board
from .difficulty import level_label, normalize_difficulty


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
        session.state.update(questions=questions, question_index=0)
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        session.state["difficulty"] = difficulty
        await ctx.reply(
            f"🧠 **Trivia started** with {len(session.player_ids)} player(s)! "
            f"Level: **{level_label(difficulty)}**.\n"
            "**How to play:** Reply A-D. The first correct player wins the round; each player gets one attempt.\n"
            "**Example:** Capital of France? A) Rome B) Paris → reply `B`.\n"
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
        session.reset_answered()
        options = "\n".join(f"{letter}) {text}" for letter, text in zip("ABCD", question["options"]))
        await channel.send(
            f"**Trivia {index + 1}/{len(questions)}** — "
            f"Level: **{level_label(question.get('difficulty', session.state['difficulty']))}**\n"
            f"{question['question']}\n\n{options}\n\n"
            "Reply with A, B, C, or D."
        )

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        if session.state.get("round_resolved") or session.is_answered_by(message.author.id):
            return
        choice = message.content.strip().upper()
        if choice not in "ABCD" or len(choice) != 1:
            return
        session.mark_answered(message.author.id)
        question = session.state["current_question_data"]
        if choice == str(question["correct_answer"]).upper():
            # Set this before awaiting to prevent simultaneous winners.
            session.state["round_resolved"] = True
            session.increment_score(message.author.id)
            answer = question["options"][ord(str(question["correct_answer"]).upper()) - 65]
            explanation = question.get("explanation", "That fact is worth remembering!")
            await message.reply(
                f"✅ You won this round! **Correct answer:** {answer}\n"
                f"💡 **Explanation:** {explanation}",
                mention_author=False,
            )
            session.state["question_index"] += 1
            await self._ask_question(session, message.channel)
        else:
            await message.reply("❌ Incorrect.", mention_author=False)
            if len(session.answered_users) >= len(session.player_ids):
                session.state["round_resolved"] = True
                answer = question["options"][ord(str(question["correct_answer"]).upper()) - 65]
                explanation = question.get("explanation", "That fact is worth remembering!")
                await message.channel.send(
                    f"Nobody got it. **Correct answer:** {answer}\n"
                    f"💡 **Explanation:** {explanation}"
                )
                session.state["question_index"] += 1
                await self._ask_question(session, message.channel)

    async def _show_results(self, session: GameSession, channel) -> None:
        session.state["finished"] = True
        await channel.send(f"🏆 **Trivia complete!**\n{format_score_board(session.score)}")

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
