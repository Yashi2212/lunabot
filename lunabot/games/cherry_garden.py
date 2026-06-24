"""CherryGarden: a ten-round mixed-format English grammar game."""

from __future__ import annotations

import random
import re
from copy import deepcopy
from typing import Any

import discord

from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from ..utils.text_utils import format_score_board
from .difficulty import level_label


QUESTION_BANK: dict[str, list[dict[str, Any]]] = {
    "easy": [
        {
            "topic": "Prepositions",
            "question_type": "multiple_choice",
            "prompt": "The lamp hangs ___ the table without touching it.",
            "options": ["on", "above", "inside", "between"],
            "answers": ["above"],
            "model_answer": "above",
            "explanation": "Use **above** because the lamp is higher than the table and does not touch it. **On** would mean it rests on and touches the table.",
        },
        {
            "topic": "Subject–verb agreement",
            "question_type": "fill_blank",
            "prompt": "She ___ a book every night. (read/reads)",
            "answers": ["reads"],
            "model_answer": "reads",
            "explanation": "A third-person singular subject such as **she** takes **reads** in the simple present.",
        },
        {
            "topic": "Parts of speech",
            "question_type": "true_false",
            "prompt": "True or False: An adjective describes a noun.",
            "answers": ["true"],
            "model_answer": "True",
            "explanation": "Adjectives describe or modify nouns, as **bright** describes **sun** in ‘bright sun’. ",
        },
        {
            "topic": "Sentence creation",
            "question_type": "sentence_creation",
            "prompt": "Create a sentence using **because** to give a reason.",
            "required_words": ["because"],
            "min_words": 5,
            "answers": [],
            "model_answer": "I carried an umbrella because it was raining.",
            "explanation": "**Because** introduces the reason for an action or situation.",
        },
        {
            "topic": "Verb agreement",
            "question_type": "correction",
            "prompt": "Correct this sentence: They is happy today.",
            "answers": ["they are happy today"],
            "model_answer": "They are happy today.",
            "explanation": "The plural subject **they** uses **are**, not **is**.",
        },
        {
            "topic": "Articles",
            "question_type": "multiple_choice",
            "prompt": "Choose the correct phrase.",
            "options": ["a umbrella", "an umbrella", "the umbrella are", "umbrella an"],
            "answers": ["an umbrella"],
            "model_answer": "an umbrella",
            "explanation": "Use **an** before a vowel sound, so we say **an umbrella**.",
        },
        {
            "topic": "Pronouns",
            "question_type": "fill_blank",
            "prompt": "Maya and I are classmates. ___ study together.",
            "answers": ["we"],
            "model_answer": "We",
            "explanation": "**We** replaces a group that includes the speaker: Maya and I.",
        },
        {
            "topic": "Past tense",
            "question_type": "true_false",
            "prompt": "True or False: **Went** is the past-tense form of **go**.",
            "answers": ["true"],
            "model_answer": "True",
            "explanation": "**Go** is irregular; its simple past form is **went**.",
        },
        {
            "topic": "Joining ideas",
            "question_type": "sentence_creation",
            "prompt": "Create one sentence using **and** to join two related ideas.",
            "required_words": ["and"],
            "min_words": 6,
            "answers": [],
            "model_answer": "Luna opened the book and read the first page.",
            "explanation": "The conjunction **and** joins words, phrases, or related clauses.",
        },
        {
            "topic": "Punctuation",
            "question_type": "correction",
            "prompt": "Correct and punctuate: where are you",
            "answers": ["where are you"],
            "model_answer": "Where are you?",
            "explanation": "A direct question begins with a capital letter and ends with a question mark.",
        },
    ],
    "medium": [
        {
            "topic": "Prepositions",
            "question_type": "multiple_choice",
            "prompt": "The café is ___ the bank and the library.",
            "options": ["among", "between", "through", "onto"],
            "answers": ["between"],
            "model_answer": "between",
            "explanation": "Use **between** for a position separating two clearly identified places. **Among** normally refers to a group of three or more.",
        },
        {
            "topic": "Present perfect",
            "question_type": "fill_blank",
            "prompt": "Rina ___ already ___ her homework. (has/finish)",
            "answers": ["has finished"],
            "model_answer": "has finished",
            "explanation": "The present perfect uses **has/have + past participle**: has finished.",
        },
        {
            "topic": "Quantifiers",
            "question_type": "true_false",
            "prompt": "True or False: **Fewer** is normally used with countable nouns.",
            "answers": ["true"],
            "model_answer": "True",
            "explanation": "Use **fewer** with countable nouns such as books; use **less** with uncountable nouns such as water.",
        },
        {
            "topic": "Contrast clauses",
            "question_type": "sentence_creation",
            "prompt": "Create a sentence using **although** to show contrast.",
            "required_words": ["although"],
            "min_words": 7,
            "answers": [],
            "model_answer": "Although the puzzle was difficult, we kept trying.",
            "explanation": "**Although** introduces a contrast between two clauses.",
        },
        {
            "topic": "Subject–verb agreement",
            "question_type": "correction",
            "prompt": "Correct: Neither of the answers are correct.",
            "answers": ["neither of the answers is correct"],
            "model_answer": "Neither of the answers is correct.",
            "explanation": "In formal standard English, **neither** is singular here, so it takes **is**.",
        },
        {
            "topic": "Relative pronouns",
            "question_type": "multiple_choice",
            "prompt": "The teacher ___ helped me was very patient.",
            "options": ["which", "who", "where", "whose"],
            "answers": ["who"],
            "model_answer": "who",
            "explanation": "Use **who** as the subject of a relative clause referring to a person.",
        },
        {
            "topic": "Active and passive voice",
            "question_type": "multiple_choice",
            "prompt": "Which sentence is passive?",
            "options": ["Mina baked the cake.", "The cake was baked by Mina.", "Mina is baking.", "Bake the cake."],
            "answers": ["the cake was baked by mina"],
            "model_answer": "The cake was baked by Mina.",
            "explanation": "In passive voice, the receiver of the action becomes the subject: the cake **was baked**.",
        },
        {
            "topic": "Possessives",
            "question_type": "true_false",
            "prompt": "True or False: **It's** is the possessive form of **it**.",
            "answers": ["false"],
            "model_answer": "False",
            "explanation": "**It's** means **it is** or **it has**. The possessive form is **its**, without an apostrophe.",
        },
        {
            "topic": "Conditional sentences",
            "question_type": "sentence_creation",
            "prompt": "Create a sentence using **unless**.",
            "required_words": ["unless"],
            "min_words": 7,
            "answers": [],
            "model_answer": "We will miss the bus unless we leave now.",
            "explanation": "**Unless** means **if not** and introduces a condition.",
        },
        {
            "topic": "Past-time expressions",
            "question_type": "correction",
            "prompt": "Correct: I have seen him yesterday.",
            "answers": ["i saw him yesterday"],
            "model_answer": "I saw him yesterday.",
            "explanation": "Use the simple past with a finished time such as **yesterday**: saw, not have seen.",
        },
    ],
    "hard": [
        {
            "topic": "Subjunctive mood",
            "question_type": "fill_blank",
            "prompt": "I wish I ___ taller. (was/were)",
            "answers": ["were"],
            "model_answer": "were",
            "explanation": "Formal hypothetical wishes use the subjunctive **were** for every subject: I wish I were.",
        },
        {
            "topic": "Modifier placement",
            "question_type": "multiple_choice",
            "prompt": "Choose the sentence without a dangling modifier.",
            "options": ["Walking home, the rain soaked Priya.", "Walking home, Priya was soaked by the rain.", "Walking home, the street was wet.", "Walking home, there was rain."],
            "answers": ["walking home priya was soaked by the rain"],
            "model_answer": "Walking home, Priya was soaked by the rain.",
            "explanation": "The noun after the opening modifier must be the person walking; that noun is **Priya**.",
        },
        {
            "topic": "Semicolons",
            "question_type": "true_false",
            "prompt": "True or False: A semicolon can join two closely related independent clauses.",
            "answers": ["true"],
            "model_answer": "True",
            "explanation": "A semicolon can connect two complete, closely related clauses without a coordinating conjunction.",
        },
        {
            "topic": "Comparing viewpoints",
            "question_type": "sentence_creation",
            "prompt": "Create a complex sentence using **whereas**.",
            "required_words": ["whereas"],
            "min_words": 9,
            "answers": [],
            "model_answer": "Cherry prefers quiet mornings, whereas Luna enjoys lively evenings.",
            "explanation": "**Whereas** places two contrasting facts or viewpoints in one sentence.",
        },
        {
            "topic": "Correlative structures",
            "question_type": "correction",
            "prompt": "Correct: No sooner did he arrive when the meeting began.",
            "answers": ["no sooner did he arrive than the meeting began"],
            "model_answer": "No sooner did he arrive than the meeting began.",
            "explanation": "The fixed structure is **no sooner … than**, not no sooner … when.",
        },
        {
            "topic": "Conditional inversion",
            "question_type": "fill_blank",
            "prompt": "___ I known about the delay, I would have waited. (Had/Have)",
            "answers": ["had"],
            "model_answer": "Had",
            "explanation": "**Had I known** is an inverted third conditional meaning **If I had known**.",
        },
        {
            "topic": "Pronoun case",
            "question_type": "true_false",
            "prompt": "True or False: **Whom** is normally used as the subject of a clause.",
            "answers": ["false"],
            "model_answer": "False",
            "explanation": "**Who** is normally the subject; **whom** is an object in formal usage.",
        },
        {
            "topic": "Concession",
            "question_type": "sentence_creation",
            "prompt": "Create a sentence using **despite** followed by a noun or -ing phrase.",
            "required_words": ["despite"],
            "min_words": 8,
            "answers": [],
            "model_answer": "Despite feeling nervous, Aria delivered a confident speech.",
            "explanation": "**Despite** is followed by a noun, pronoun, or -ing form—not a full that-clause.",
        },
        {
            "topic": "Agreement with distributives",
            "question_type": "correction",
            "prompt": "Correct: Each of the participants have a badge.",
            "answers": ["each of the participants has a badge"],
            "model_answer": "Each of the participants has a badge.",
            "explanation": "The head word **each** is singular, so the verb is **has**.",
        },
        {
            "topic": "Commonly confused words",
            "question_type": "multiple_choice",
            "prompt": "The new rule will ___ how we work.",
            "options": ["effect", "affect", "except", "accept"],
            "answers": ["affect"],
            "model_answer": "affect",
            "explanation": "**Affect** is usually a verb meaning influence. **Effect** is usually a noun meaning result.",
        },
    ],
}


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
    return normalized in {_normalize(answer) for answer in question.get("answers", [])}


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
        if mode not in QUESTION_BANK:
            mode = "easy"
        supplied = session.state.get("questions")
        questions = [deepcopy(q) for q in supplied or [] if valid_garden_question(q)]
        local = [deepcopy(q) for q in QUESTION_BANK[mode]]
        random.shuffle(local)
        used_prompts = {_normalize(q["prompt"]) for q in questions}
        questions.extend(q for q in local if _normalize(q["prompt"]) not in used_prompts)
        questions = questions[:10]
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
        winners = [user_id for user_id, score in session.score.items() if score == highest]
        winner_text = " and ".join(f"<@{user_id}>" for user_id in winners)
        perfect = " A PERFECT GARDEN—absolutely legendary!" if highest == 10 else ""
        await channel.send(
            "🌸🏆 **CHERRYGARDEN COMPLETE!** 🏆🌸\n\n"
            f"{format_score_board(session.score)}\n\n"
            f"🎉 Huge congratulations to {winner_text} with **{highest}/10**!{perfect}\n"
            "You grew ten rounds of grammar into something brilliant. Give yourselves a very dramatic round of applause!"
        )

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
