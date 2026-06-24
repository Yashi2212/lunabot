"""Single-player vocabulary multiple-choice quiz."""

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from .difficulty import level_label, normalize_difficulty


class WordQuizGame(BaseGame):
    name = "wordquiz"
    description = "Learn words with a short multiple-choice quiz"
    max_players = 1

    async def start(self, session: GameSession, ctx) -> None:
        questions = session.state.get("questions", [])[:5]
        if not questions:
            session.state["finished"] = True
            await ctx.reply("🌙 Word Quiz setup was incomplete.", mention_author=False)
            return
        session.state.update(questions=questions, question_index=0)
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        session.state["difficulty"] = difficulty
        await ctx.reply(
            f"📚 **Word Quiz started!** Level: **{level_label(difficulty)}**\n"
            "**How to play:** Reply A, B, C, or D to each vocabulary question.\n"
            "**Example:** ‘Which word means calm?’ A) Serene B) Rough → reply `A`.\n"
            "After every answer, Luna gives the correct answer and explains why.",
            mention_author=False,
        )
        await self._ask(session, ctx.channel)

    async def _ask(self, session: GameSession, channel) -> None:
        index = session.state["question_index"]
        questions = session.state["questions"]
        if index >= len(questions):
            session.state["finished"] = True
            score = session.score.get(session.player_ids[0], 0)
            await channel.send(f"🌸 Word Quiz complete! Score: **{score}/{len(questions)}**")
            return
        question = questions[index]
        session.state["current_question_data"] = question
        options = "\n".join(f"{letter}) {text}" for letter, text in zip("ABCD", question["options"]))
        await channel.send(
            f"**Word Quiz {index + 1}/{len(questions)}** — "
            f"Level: **{level_label(question.get('difficulty', session.state['difficulty']))}**\n"
            f"{question['question']}\n\n{options}"
        )

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        choice = message.content.strip().upper()
        if choice not in "ABCD" or len(choice) != 1:
            return
        question = session.state["current_question_data"]
        correct = str(question["correct_answer"]).upper()
        answer = question["options"][ord(correct) - 65]
        if choice == correct:
            session.increment_score(message.author.id)
            result = "✅ Your choice was correct."
        else:
            result = "❌ Your choice was incorrect."
        explanation = question.get("explanation", "Review the word and use it in your own sentence.")
        await message.reply(
            f"{result}\n**Correct answer:** {answer}\n💡 **Explanation:** {explanation}",
            mention_author=False,
        )
        session.state["question_index"] += 1
        await self._ask(session, message.channel)

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
