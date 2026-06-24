"""CherryWords Arena multiplayer word battle."""

import random

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board
from .difficulty import level_label, normalize_difficulty


WORDS_BY_SEQUENCE = {
    "est": {"best", "chest", "forest", "greatest", "honest", "interest", "nest", "rest", "test", "yesterday"},
    "ion": {"action", "motion", "nation", "station", "vision", "education"},
    "ing": {"building", "king", "learning", "morning", "ring", "sing", "singing", "spring", "thing"},
    "pre": {"prepare", "present", "press", "pretty", "prevent", "preview", "supreme"},
    "con": {"concert", "concept", "concrete", "connect", "consider", "control", "icon"},
}
VALID_WORDS = set().union(*WORDS_BY_SEQUENCE.values())

WORD_DEFINITIONS = {
    "best": "of the highest quality", "chest": "the front part of the body below the neck",
    "forest": "a large area covered with trees", "honest": "truthful and sincere",
    "nest": "a structure where birds lay eggs", "rest": "to relax or recover strength",
    "test": "a way to measure knowledge or ability", "interest": "curiosity or attention",
    "greatest": "largest or best", "yesterday": "the day before today",
    "action": "the process of doing something", "motion": "movement",
    "nation": "a country and its people", "station": "a regular stopping place",
    "vision": "the ability to see or imagine", "education": "the process of learning",
    "building": "a structure with walls and a roof", "king": "a male monarch",
    "learning": "gaining knowledge or skill", "morning": "the early part of the day",
    "ring": "a circular band", "sing": "to make musical sounds with the voice",
    "singing": "making musical sounds with the voice", "spring": "the season after winter",
    "thing": "an object or idea",
    "prepare": "to make ready", "present": "to show, give, or be here now",
    "press": "to push firmly", "pretty": "attractive or fairly",
    "prevent": "to stop something from happening", "preview": "an advance view",
    "supreme": "highest in rank or quality",
    "concert": "a live musical performance", "concept": "an abstract idea",
    "concrete": "specific and real; also a building material", "connect": "to join together",
    "consider": "to think carefully about", "control": "the power to direct something",
    "icon": "a symbol or widely admired person",
}


class CherryWordsArenaGame(BaseGame):
    name = "cherrywords"
    description = "Competitive word-building arena"
    max_players = 5
    max_rounds = 5

    async def start(self, session: GameSession, ctx) -> None:
        sequences = list(WORDS_BY_SEQUENCE)
        random.shuffle(sequences)
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        session.state.update(
            round_number=0,
            used_words=set(),
            remaining_sequences=sequences,
            difficulty=difficulty,
        )
        await ctx.reply(
            f"🌸 **CherryWords Arena** started with {len(session.player_ids)} player(s)! "
            f"Level: **{level_label(difficulty)}**. Only real words from Luna's round "
            "dictionary count, and words cannot be reused.\n"
            "**How to play:** Submit a word containing the displayed letter sequence; "
            "the mode rewards the first or longest valid word.\n"
            "**Example:** Letters `est` → `forest`. Every accepted word is defined immediately.",
            mention_author=False,
        )
        await self._start_round(session, ctx.channel)

    async def _start_round(self, session: GameSession, channel) -> None:
        if session.state["round_number"] >= self.max_rounds:
            session.state["finished"] = True
            await channel.send(f"🏆 **CherryWords complete!**\n{format_score_board(session.score)}")
            return
        session.state["round_number"] += 1
        session.state["mode"] = random.choice(["speed", "quick", "longest"])
        session.state["letters"] = session.state["remaining_sequences"].pop()
        session.state["submissions"] = {}
        session.state["round_resolved"] = False
        session.reset_answered()
        mode_help = {
            "speed": "First valid word wins.",
            "quick": "First valid word wins.",
            "longest": "Everyone submits once; the longest valid word wins.",
        }[session.state["mode"]]
        await channel.send(
            f"**CherryWords {session.state['round_number']}/{self.max_rounds}**\n"
            f"Level: **{level_label(session.state['difficulty'])}** | "
            f"Mode: **{session.state['mode'].title()}**\n"
            f"Your word must contain **{session.state['letters']}**. {mode_help}"
        )

    @staticmethod
    def validate_word(word: str, letters: str, difficulty: str = "easy") -> bool:
        minimum = {"easy": 3, "medium": 5, "hard": 6}[normalize_difficulty(difficulty)]
        return word.isalpha() and len(word) >= minimum and letters in word and word in VALID_WORDS

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        if session.state.get("round_resolved"):
            return
        user_id = message.author.id
        word = message.content.strip().casefold()
        letters = session.state["letters"]
        if not self.validate_word(word, letters, session.state["difficulty"]):
            await message.reply(
                f"That is not a valid arena word containing **{letters}**.",
                mention_author=False,
            )
            return
        if word in session.state["used_words"]:
            await message.reply("That word was already used in this game.", mention_author=False)
            return

        mode = session.state["mode"]
        if mode in {"speed", "quick"}:
            session.state["round_resolved"] = True
            session.state["used_words"].add(word)
            session.increment_score(user_id)
            await message.reply(
                f"✅ **{word}** wins the round! +1 point.\n"
                f"💡 **Explanation:** {WORD_DEFINITIONS[word]}",
                mention_author=False,
            )
            await self._start_round(session, message.channel)
            return

        if session.is_answered_by(user_id):
            await message.reply("Your longest-word submission is already locked in.", mention_author=False)
            return
        session.mark_answered(user_id)
        session.state["submissions"][user_id] = word
        session.state["used_words"].add(word)
        await message.reply(
            f"✅ **{word}** locked in.\n💡 **Explanation:** {WORD_DEFINITIONS[word]}",
            mention_author=False,
        )
        if len(session.answered_users) >= len(session.player_ids):
            session.state["round_resolved"] = True
            submissions = session.state["submissions"]
            longest = max(len(item) for item in submissions.values())
            winners = [uid for uid, item in submissions.items() if len(item) == longest]
            for winner in winners:
                session.increment_score(winner)
            mentions = ", ".join(f"<@{uid}>" for uid in winners)
            await message.channel.send(f"Longest word winner(s): {mentions} with **{longest} letters**!")
            await self._start_round(session, message.channel)

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True


# Backwards-compatible name used by earlier bot revisions.
CherryWordsArena = CherryWordsArenaGame
