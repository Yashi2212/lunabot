"""Multiplayer Would You Rather voting game."""

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from .difficulty import level_label, normalize_difficulty


class WouldYouRatherGame(BaseGame):
    name = "would_you_rather"
    description = "Vote between two choices"
    max_players = 10

    async def start(self, session: GameSession, ctx) -> None:
        questions = session.state.get("questions", [])[:5]
        if not questions:
            session.state["finished"] = True
            await ctx.reply("🌙 Would You Rather setup was incomplete.", mention_author=False)
            return
        session.state.update(questions=questions, question_index=0)
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        session.state["difficulty"] = difficulty
        await ctx.reply(
            f"🤔 **Would You Rather?** {len(session.player_ids)} player(s)—"
            f"Level: **{level_label(difficulty)}**.\n"
            "**What this is:** An opinion-voting game—there is no correct or incorrect answer.\n"
            "**How to play:** Vote A or B once, then compare reasons after the result.\n"
            "**Example:** A) Fly B) Breathe underwater → reply `A` or `B`.",
            mention_author=False,
        )
        await self._ask_question(session, ctx.channel)

    async def _ask_question(self, session: GameSession, channel) -> None:
        index = session.state["question_index"]
        questions = session.state["questions"]
        if index >= len(questions):
            session.state["finished"] = True
            await channel.send("🌸 All votes are in. Thanks for playing!")
            return
        question = questions[index]
        session.state["current_question"] = question
        session.state["votes"] = {}
        session.state["advancing"] = False
        session.reset_answered()
        await channel.send(
            f"**Question {index + 1}/{len(questions)}** — "
            f"Level: **{level_label(question.get('difficulty', session.state['difficulty']))}**\n\n"
            f"**A)** {question['option_a']}\n\n**B)** {question['option_b']}"
        )

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        user_id = message.author.id
        if session.state.get("advancing") or session.is_answered_by(user_id):
            return
        choice = message.content.strip().upper()
        if choice not in {"A", "B"}:
            return
        session.state["votes"][user_id] = choice
        session.mark_answered(user_id)
        await message.reply(f"✅ Vote **{choice}** locked in!", mention_author=False)
        if len(session.answered_users) >= len(session.player_ids):
            session.state["advancing"] = True
            await self._show_results(session, message.channel)

    async def _show_results(self, session: GameSession, channel) -> None:
        votes = session.state["votes"].values()
        a_count = sum(vote == "A" for vote in votes)
        b_count = sum(vote == "B" for vote in votes)
        question = session.state["current_question"]
        majority = "A" if a_count > b_count else "B" if b_count > a_count else "Tie"
        await channel.send(
            f"📊 **Results**\nA) {question['option_a']}: **{a_count}**\n"
            f"B) {question['option_b']}: **{b_count}**\nMajority: **{majority}**\n"
            "**Correct answer:** None—this is an opinion question.\n"
            f"💡 **Explanation:** {question.get('learning_focus', 'Explain your choice clearly and listen to another viewpoint.')}"
        )
        session.state["question_index"] += 1
        await self._ask_question(session, channel)

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
