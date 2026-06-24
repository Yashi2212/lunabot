"""Single-player riddle game with limited guesses."""

import re

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from .difficulty import level_label, normalize_difficulty


def _normal(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", value.casefold()).strip()


def _without_article(value: str) -> str:
    for article in ("a ", "an ", "the "):
        if value.startswith(article):
            return value[len(article):]
    return value


class RiddleGame(BaseGame):
    name = "riddle"
    description = "Solve a riddle in three guesses"
    max_players = 1

    async def start(self, session: GameSession, ctx) -> None:
        if not session.state.get("riddle") or not session.state.get("answer"):
            session.state["finished"] = True
            await ctx.reply("🌙 Riddle setup was incomplete.", mention_author=False)
            return
        session.state["attempts_left"] = 3
        session.state["guesses"] = set()
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        session.state["difficulty"] = difficulty
        await ctx.reply(
            f"🧩 **A Riddle For You** 🧩\n"
            f"Level: **{level_label(difficulty)}**\n\n{session.state['riddle']}\n\n"
            "**How to play:** Type the answer in your own words. You have three unique guesses.\n"
            "**Example:** ‘What has hands but cannot clap?’ → `clock`.\n\n"
            "What is your answer?",
            mention_author=False,
        )

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        guess = _normal(message.content)
        answer = _normal(str(session.state["answer"]))
        accepted = {_normal(item) for item in session.state.get("accepted_answers", [])}
        accepted.add(answer)
        if not guess:
            return
        if guess in session.state["guesses"]:
            await message.reply("You already tried that answer.", mention_author=False)
            return
        session.state["guesses"].add(guess)

        if guess in accepted or _without_article(guess) in accepted:
            session.increment_score(message.author.id)
            session.state["finished"] = True
            await message.reply(
                f"✅ **Correct answer:** {session.state['answer']}\n"
                f"💡 **Explanation:** {session.state.get('explanation', 'The clues point to the answer through wordplay.')}",
                mention_author=False,
            )
            return

        session.state["attempts_left"] -= 1
        remaining = session.state["attempts_left"]
        if remaining <= 0:
            session.state["finished"] = True
            await message.reply(
                f"Out of guesses. **Correct answer:** {session.state['answer']}\n"
                f"💡 **Explanation:** {session.state.get('explanation', 'The clues point to the answer through wordplay.')}",
                mention_author=False,
            )
        else:
            await message.reply(
                f"Not quite—you have **{remaining}** guess{'es' if remaining != 1 else ''} left.",
                mention_author=False,
            )

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
