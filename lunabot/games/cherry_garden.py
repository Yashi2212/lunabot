"""CherryGarden: a ten-round mixed-format English grammar game."""

from __future__ import annotations

import random
import re
from copy import deepcopy
from typing import Any

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board, format_winner_line
from .difficulty import level_label


def _normalize(value: str) -> str:
    value = value.casefold().replace("’", "'")
    return " ".join(re.sub(r"[^a-z0-9']", " ", value).split())


def valid_garden_question(question: object) -> bool:
    if not isinstance(question, dict):
        return False
    required = ("topic", "question_type", "prompt", "explanation")
    if not all(isinstance(question.get(key), str) and question[key].strip() for key in required):
        return False
    if question["question_type"] not in {
        "multiple_choice", "fill_blank", "true_false", "sentence_creation", "correction"
    }:
        return False
    if question["question_type"] == "multiple_choice":
        options = question.get("options")
        if not isinstance(options, list) or len(options) != 4:
            return False
    if question["question_type"] == "sentence_creation":
        return bool(question.get("required_words")) and isinstance(question.get("model_answer"), str)
    return bool(question.get("answers"))


def _evaluate_answer(question: dict[str, Any], raw_answer: str) -> bool:
    normalized = _normalize(raw_answer)
    question_type = question["question_type"]
    if question_type == "multiple_choice" and len(normalized) == 1 and normalized in "abcd":
        normalized = _normalize(question["options"][ord(normalized) - 97])
    if question_type == "true_false":
        normalized = {"t": "true", "f": "false"}.get(normalized, normalized)
    if question_type == "sentence_creation":
        words = normalized.split()
        required = {_normalize(word) for word in question["required_words"]}
        return len(words) >= int(question.get("min_words", 5)) and required.issubset(set(words))
    accepted = {
        _normalize(answer)
        for answer in question.get("answers", [])
        if isinstance(answer, str) and answer.strip()
    }
    if question_type == "correction":
        model_answer = question.get("model_answer")
        if isinstance(model_answer, str) and model_answer.strip():
            accepted.add(_normalize(model_answer))
        if normalized in accepted:
            return True
        # The prompt explicitly allows either the missing correction or the
        # complete corrected sentence. Accept a valid correction phrase inside
        # the full sentence, e.g. "she doesn't like coffee" for "doesn't".
        padded_answer = f" {normalized} "
        return any(f" {candidate} " in padded_answer for candidate in accepted)
    return normalized in accepted


def _question_text(session: GameSession, question: dict[str, Any]) -> str:
    index = session.state["question_index"]
    question_type = question["question_type"].replace("_", " ").title()
    lines = [
        f"**CherryGarden Round {index + 1}/10**",
        f"Level: **{level_label(session.state['mode'])}** | Topic: **{question['topic']}** | Type: **{question_type}**",
        "",
        f"✍️ {question['prompt']}",
    ]
    if question["question_type"] == "multiple_choice":
        lines.append("")
        lines.extend(
            f"**{letter})** {option}" for letter, option in zip("ABCD", question["options"])
        )
        lines.append("Reply with A-D or the full answer.")
    elif question["question_type"] == "true_false":
        lines.append("Reply `true` or `false`.")
    elif question["question_type"] == "sentence_creation":
        lines.append("Write your own complete sentence—many answers can be correct.")
    else:
        lines.append("Reply with the missing or corrected text.")
    return "\n".join(lines)


class CherryGardenGame(BaseGame):
    name = "cherrygarden"
    description = "Ten-round mixed English grammar garden"
    max_players = 5

    async def start(self, session: GameSession, ctx) -> None:
        mode = session.state.get("mode", "easy")
        if mode not in {"easy", "medium", "hard"}:
            mode = "easy"
        supplied = session.state.get("questions")
        questions = [deepcopy(q) for q in supplied or [] if valid_garden_question(q)]
        questions = questions[:10]
        if len(questions) < 10:
            session.state["finished"] = True
            await ctx.reply(
                "🌙 CherryGarden needs a complete fresh AI question bank and could not start.",
                mention_author=False,
            )
            return
        random.shuffle(questions)
        session.state.update(
            mode=mode,
            questions=questions,
            question_index=0,
            max_rounds=10,
        )
        topics = ", ".join(sorted({q["topic"] for q in questions}))
        await ctx.reply(
            f"🌸 **CherryGarden: Grammar Mix** — {len(session.player_ids)} player(s)\n"
            f"Level: **{level_label(mode)}** | Rounds: **10**\n"
            f"**Today's topics:** {topics}\n\n"
            "**How to play:** The rounds randomly mix multiple choice, fill-in-the-blank, "
            "true/false, sentence creation, and correction. Everyone answers once.\n"
            "**Example — Prepositions:** ‘The lamp hangs ___ the table without touching it.’ "
            "The answer is **above**, not **on**, because **on** means touching the table.\n"
            "After every round Luna shows the correct/model answer, explains the rule, and "
            "gently explains each incorrect response.",
            mention_author=False,
        )
        await self._ask_question(session, ctx.channel)

    async def _ask_question(self, session: GameSession, channel) -> None:
        index = session.state["question_index"]
        if index >= len(session.state["questions"]):
            await self._show_results(session, channel)
            return
        question = session.state["questions"][index]
        session.state["current_question_data"] = question
        session.state["responses"] = {}
        session.state["advancing"] = False
        session.reset_answered()
        await channel.send(_question_text(session, question))

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        user_id = message.author.id
        if session.state.get("advancing") or session.is_answered_by(user_id):
            return
        raw_answer = " ".join(message.content.strip().split())
        if not raw_answer:
            return
        question = session.state["current_question_data"]
        correct = _evaluate_answer(question, raw_answer)
        session.mark_answered(user_id)
        session.state["responses"][user_id] = {"answer": raw_answer, "correct": correct}
        if correct:
            session.increment_score(user_id)
        await message.reply(
            "🔒 Answer locked in. Luna explains every response after everyone answers.",
            mention_author=False,
        )
        if len(session.answered_users) >= len(session.player_ids):
            session.state["advancing"] = True
            await self._explain_round(session, message.channel)

    async def _explain_round(self, session: GameSession, channel) -> None:
        question = session.state["current_question_data"]
        model_answer = question.get("model_answer") or question.get("answers", ["Open response"])[0]
        lines = [
            f"✅ **Correct/model answer:** {model_answer}",
            f"💡 **Explanation:** {question['explanation']}",
            "",
        ]
        for user_id, response in session.state["responses"].items():
            if response["correct"]:
                lines.append(f"✅ <@{user_id}> — correct! +1 point.")
            else:
                lines.append(
                    f"❌ <@{user_id}> answered **{response['answer']}**. "
                    f"Why it misses: {question['explanation']}"
                )
        await channel.send("\n".join(lines))
        session.state["question_index"] += 1
        await self._ask_question(session, channel)

    async def _show_results(self, session: GameSession, channel) -> None:
        session.state["finished"] = True
        highest = max(session.score.values(), default=0)
        perfect = " A PERFECT GARDEN—absolutely legendary!" if highest == 10 else ""
        await channel.send(
            "🌸🏆 **CHERRYGARDEN COMPLETE!** 🏆🌸\n\n"
            f"{format_score_board(session.score)}\n\n"
            f"{format_winner_line(session.score)}{perfect}"
        )

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
