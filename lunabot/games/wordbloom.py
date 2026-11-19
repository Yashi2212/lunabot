"""WordBloom: guess a word from its definition in three attempts."""

import re

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from .difficulty import level_label, normalize_difficulty


def _normalize_guess(value: str) -> str:
    return re.sub(r"[^a-z'-]", "", value.strip().casefold())


class WordBloomGame(BaseGame):
    name = "wordbloom"
    description = "Guess the word from its definition in three tries"
    max_players = 1

    async def start(self, session: GameSession, ctx) -> None:
        word = session.state.get("word")
        definition = session.state.get("definition")
        if not word or not definition:
            session.state["finished"] = True
            await ctx.reply("🌙 WordBloom setup was incomplete.", mention_author=False)
            return

        session.state["attempts_left"] = 3
        session.state["guesses"] = set()
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        session.state["difficulty"] = difficulty
        await ctx.reply(
            "**WordBloom** has started! 🌸\n"
            f"Level: **{level_label(difficulty)}**\n"
            "**How to play:** Read the definition and type the hidden word. You have three unique guesses.\n"
            "**Example:** ‘A baby cat’ → `kitten`.\n\n"
            "Guess the word from this definition:\n"
            f"> {definition}\n\n"
            "You have **3 attempts**.",
            mention_author=False,
        )

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        word = str(session.state.get("word", ""))
        guess = _normalize_guess(message.content)
        if not guess:
            return

        if guess in session.state["guesses"]:
            await message.reply("You already tried that guess—pick a new one.", mention_author=False)
            return
        session.state["guesses"].add(guess)

        if guess == _normalize_guess(word):
            session.increment_score(message.author.id)
            session.state["finished"] = True
            await message.reply(
                f"🏆 <@{message.author.id}> solved it!\n"
                f"✅ **Correct answer:** {word}\n"
                f"💡 **Explanation:** {session.state['definition']}",
                mention_author=False,
            )
            return

        session.state["attempts_left"] -= 1
        remaining = session.state["attempts_left"]
        if remaining <= 0:
            session.state["finished"] = True
            await message.reply(
                f"Game over. **Correct answer:** {word}\n"
                f"💡 **Explanation:** {session.state['definition']}",
                mention_author=False,
            )
            return

        revealed = word[0].upper() + ("_" * max(0, len(word) - 1))
        await message.reply(
            f"Not quite. You have **{remaining}** tries left.\n"
            f"Hint: **{len(word)} letters** — `{revealed}`",
            mention_author=False,
        )

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
