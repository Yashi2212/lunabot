"""Turn-based collaborative storytelling."""

import re

import discord

from ..content_rotation import content_rotation
from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from .difficulty import level_label, normalize_difficulty


class StorytellerGame(BaseGame):
    name = "storyteller"
    description = "Build a ten-sentence story together"
    max_players = 5
    max_turns = 10

    OPENINGS = {
        "easy": [
            "A tiny lantern appeared outside the school, glowing even in daylight.",
            "The library cat dropped a silver key beside the newest student.",
            "Every flower in the garden suddenly began whispering the same name.",
        ],
        "medium": [
            "At midnight, the town's shadows detached themselves and queued at the railway station.",
            "The apprentice mapmaker discovered an island that moved whenever somebody told a lie.",
            "A forgotten radio began broadcasting tomorrow's weather—and one impossible warning.",
        ],
        "hard": [
            "Memory had become currency, and by sunrise the richest woman alive could no longer remember her own face.",
            "The city outlawed silence, yet beneath its loudest square an ancient quiet was beginning to wake.",
            "Each time the historian corrected the archive, reality politely rewrote itself around the footnote.",
        ],
    }

    async def start(self, session: GameSession, ctx) -> None:
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        opening = session.state.get("opening_prompt")
        if not isinstance(opening, str) or not opening.strip():
            opening = content_rotation.take(
                f"story:{difficulty}", self.OPENINGS[difficulty]
            )[0]
        session.state.update(
            story=[opening.strip()],
            opening_prompt=opening.strip(),
            turn_index=0,
            players=session.player_ids.copy(),
        )
        session.state["difficulty"] = difficulty
        challenge = {
            "easy": "Write one clear sentence.",
            "medium": "Use one vivid adjective or adverb.",
            "hard": "Use figurative language or a complex sentence.",
        }[difficulty]
        session.state["challenge"] = challenge
        await ctx.reply(
            f"📖 **Storyteller** begins with {len(session.player_ids)} player(s). "
            f"Level: **{level_label(difficulty)}**. Each turn adds one sentence "
            f"(300 characters maximum).\n\n**Opening:** {opening}\n\n"
            "**How to play:** Wait for your mention, then add exactly one sentence.\n"
            "**Example:** `Mira lifted the lantern, and the shadows stepped back.`\n"
            f"💡 **Writing skill:** {challenge}",
            mention_author=False,
        )
        await self._prompt_turn(session, ctx.channel)

    async def _prompt_turn(self, session: GameSession, channel) -> None:
        turn = session.state["turn_index"]
        if turn >= self.max_turns:
            session.state["finished"] = True
            await channel.send(
                f"📖 **The Story** 📖\n\n{' '.join(session.state['story'])}\n\n"
                f"💡 **Learning recap:** You practised sequencing ideas, sentence structure, "
                f"and collaborative writing at {session.state['difficulty']} level."
            )
            return
        players = session.state["players"]
        current_player = players[turn % len(players)]
        await channel.send(
            f"**Turn {turn + 1}/{self.max_turns}** — "
            f"Level: **{level_label(session.state['difficulty'])}**\n"
            f"<@{current_player}>, add one sentence. {session.state['challenge']}"
        )

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        turn = session.state["turn_index"]
        players = session.state["players"]
        if message.author.id != players[turn % len(players)]:
            return
        sentence = " ".join(message.content.strip().split())
        if not sentence:
            return
        if len(sentence) > 300:
            await message.reply("Keep your sentence to **300 characters or fewer**.", mention_author=False)
            return
        # Multiple terminal punctuation groups usually mean multiple sentences.
        if len(re.findall(r"[.!?]+(?:\s|$)", sentence)) > 1:
            await message.reply("One sentence per turn, please.", mention_author=False)
            return
        if sentence[-1] not in ".!?":
            sentence += "."
        session.state["story"].append(sentence)
        session.state["turn_index"] += 1
        await message.reply("✅ Added to the story!", mention_author=False)
        await self._prompt_turn(session, message.channel)

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
