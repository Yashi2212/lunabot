from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any

import aiohttp
import discord
from discord.ext import commands

from .core import GameManager, TimeoutManager
from .content_rotation import content_rotation
from .definitions import DefinitionNotFound, fetch_meaning
from .games import (
    CherryGardenGame,
    CherryWordsArenaGame,
    CodenamesGame,
    EscapeRoomGame,
    QuizGame,
    RiddleGame,
    StorytellerGame,
    TriviaGame,
    WordBloomGame,
    WordQuizGame,
    WouldYouRatherGame,
)
from .games.difficulty import parse_difficulty
from .games.cherry_garden import valid_garden_question
from .games.escape import valid_escape_puzzle
from .persona import (
    GAME_GENERATOR_PERSONA,
    LUNA_PERSONA,
    OFFLINE_JOKES,
    ensure_emoji,
    luna_about_text,
    offline_chat_reply,
    romantic_boundary_reply,
    special_chat_reply,
    style_casual_reply,
    style_joke_reply,
)

CHERRY_BLOSSOM = "🌸"
WHITE_HEART = "🤍"
DEFAULT_OSS_MODEL = "openai/gpt-oss-120b"
DEFAULT_LLAMA_MODEL = "llama-3.3-70b"
DATA_DIR = Path(__file__).resolve().parent / "data"

DEFAULT_WORDS = {
    "serendipity": "the chance occurrence of a happy or useful discovery",
    "glimmer": "a faint or unsteady light",
    "cozy": "giving a feeling of comfort, warmth, and relaxation",
    "moxie": "courage, determination, and confidence",
    "whimsical": "playfully unusual or fanciful",
    "sparkle": "to shine with small flashes of light",
    "wanderlust": "a strong desire to travel",
    "moonbeam": "a ray of light from the moon",
    "gentle": "kind, calm, and mild in manner",
    "sunbeam": "a ray of sunlight",
}

WORDS_BY_DIFFICULTY = {
    "easy": ["cozy", "gentle", "glimmer", "sparkle", "sunbeam"],
    "medium": ["moonbeam", "moxie", "whimsical"],
    "hard": ["serendipity", "wanderlust"],
}

GAME_DESCRIPTIONS = {
    "wordbloom": "Guess one hidden word from its definition; three attempts.",
    "wordquiz": "Choose A-D for vocabulary meanings, then learn why the answer is correct.",
    "riddle": "Solve a wordplay riddle in three guesses and see how its clues work.",
    "escape": "Search, collect, inspect, and solve a rotating interactive puzzle room.",
    "trivia": "Multiplayer race: the first correct A-D answer wins each round.",
    "quiz": "Multiplayer knowledge quiz: everyone answers once and earns individual points.",
    "storyteller": "Players take turns adding one sentence to a collaborative story.",
    "would_you_rather": "Would You Rather: vote A or B, compare opinions, and explain reasoning—no correct answer.",
    "cherrygarden": "Multiplayer English grammar and sentence-correction competition.",
    "cherrywords": "Build valid words containing given letters and learn each word's meaning.",
    # "codenames": "Connect clues to words on a pastel 5x4 board, solo or in two teams.",
}

GAME_HELP = {
    "wordbloom": {
        "command": "luna wordbloom <level>",
        "players": "1",
        "how": "Read a definition and type the hidden word. You have three unique guesses.",
        "example": "Definition: ‘a baby cat’ → answer `kitten`.",
        "learning": "Luna reveals the word and explains its meaning.",
    },
    "wordquiz": {
        "command": "luna wordquiz <level>",
        "players": "1",
        "how": "Read a vocabulary question and reply A, B, C, or D.",
        "example": "‘Which word means calm?’ A) Serene B) Rough → reply `A`.",
        "learning": "Every answer is followed immediately by a definition and explanation.",
    },
    "riddle": {
        "command": "luna riddle <level>",
        "players": "1",
        "how": "Type a free-text answer to the riddle; repeated guesses do not consume attempts.",
        "example": "‘What has hands but cannot clap?’ → `clock`.",
        "learning": "The answer reveal explains the riddle's wordplay.",
    },
    "escape": {
        "command": "luna escape <level>",
        "players": "1",
        "how": "Use `look`, `search`, `take <item>`, `inspect <item>`, `hint`, and `solve <answer>`.",
        "example": "`search` → `take star chart` → `inspect star chart` → `solve 4217`.",
        "learning": "Every solved room ends with the idea behind its puzzle.",
    },
    "trivia": {
        "command": "luna trivia <level>",
        "players": "1-5 (lobby)",
        "how": "The first player to submit the correct A-D choice wins that round.",
        "example": "Capital of France? A) Rome B) Paris → reply `B` quickly.",
        "learning": "The correct answer appears with a factual explanation on the next line.",
    },
    "quiz": {
        "command": "luna quiz <level>",
        "players": "1-5 (lobby)",
        "how": "Every player locks one A-D answer per question; correct choices earn a point.",
        "example": "15% of 200? A) 20 B) 30 → reply `B`.",
        "learning": "After everyone answers, Luna shows the answer and explains the method.",
    },
    "storyteller": {
        "command": "luna storyteller <level>",
        "players": "1-5 (lobby)",
        "how": "Follow the opening prompt and add exactly one sentence on your turn.",
        "example": "Opening: ‘A lantern appeared…’ → `Mira picked it up carefully.`",
        "learning": "Difficulty changes the writing skill: clarity, vivid description, or figurative language.",
    },
    "would_you_rather": {
        "command": "luna wyr <level>",
        "players": "1-5 (lobby)",
        "how": "Vote A or B on a dilemma. This is an opinion game—there is no correct answer.",
        "example": "A) Fly B) Breathe underwater → reply `A` or `B`, then explain why.",
        "learning": "Results introduce a reasoning, comparison, or discussion skill.",
    },
    "cherrygarden": {
        "command": "luna cherrygarden <level>",
        "players": "1-5 (lobby)",
        "how": "Correct a sentence or fill a blank; each player submits one answer.",
        "example": "‘She ___ a book each night.’ → `reads`.",
        "learning": "The accepted answer is followed by its grammar explanation.",
    },
    "cherrywords": {
        "command": "luna cherrywords <level>",
        "players": "1-5 (lobby)",
        "how": "Submit a real word containing the displayed letter sequence; modes reward speed or length.",
        "example": "Letters `est` → `forest` is valid.",
        "learning": "Every accepted word is immediately defined.",
    },
    "codenames": {
        "command": "luna codenames <solo|multi> <level>",
        "players": "1 solo; 4-10 multiplayer",
        "how": "Connect a clue to board words and select cards with A-T. Avoid neutral, opponent, and assassin cards.",
        "example": "Clue `OCEAN — 2` might point to `WHALE` and `CORAL`; reply with their card letters.",
        "learning": "Every revealed word receives a concise vocabulary definition.",
    },
}

GAME_HELP_ALIASES = {
    "tea": "wordbloom", "word": "wordbloom", "trio": "wordquiz",
    "wyr": "would_you_rather", "wouldyourather": "would_you_rather",
    "arena": "cherrywords", "codename": "codenames", "escaperoom": "escape",
}

AUTO_MODEL_KEYWORDS = {
    "meaning", "define", "word", "grammar", "translate", "sentence",
    "synonym", "spelling", "spell", "vocabulary",
}


def _load_json_list(filename: str, key: str) -> list[dict[str, Any]]:
    try:
        with (DATA_DIR / filename).open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, json.JSONDecodeError):
        return []
    values = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


def _items_for_difficulty(items: list[dict[str, Any]], difficulty: str) -> list[dict[str, Any]]:
    return [item for item in items if item.get("difficulty", "easy") == difficulty]


def _load_word_list() -> list[str]:
    try:
        with (DATA_DIR / "word_list.json").open("r", encoding="utf-8") as stream:
            values = json.load(stream)
    except (OSError, json.JSONDecodeError):
        return list(DEFAULT_WORDS)
    clean = [item.strip().casefold() for item in values if isinstance(item, str) and item.strip()]
    return clean or list(DEFAULT_WORDS)


WORD_LIST = _load_word_list()


def choose_llm_model(prompt: str) -> str:
    words = prompt.casefold()
    return DEFAULT_OSS_MODEL if any(keyword in words for keyword in AUTO_MODEL_KEYWORDS) else DEFAULT_LLAMA_MODEL


def build_llm_payload(
    prompt: str,
    model: str,
    system_prompt: str | None = None,
    max_tokens: int = 250,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }


def extract_definition_target(text: str) -> str | None:
    cleaned = text.strip().casefold().rstrip("?.!")
    for prefix in ("what is ", "what are ", "define ", "meaning of ", "meaning "):
        if cleaned.startswith(prefix):
            return cleaned[len(prefix):].strip() or None
    return None


def format_definition_response(term: str, result: dict[str, Any]) -> str:
    definition = result["meanings"][0]["definitions"][0]["definition"]
    example = result["meanings"][0]["definitions"][0].get("example")
    phonetic = result.get("phonetic") or ""
    reply = f"**{term}** {phonetic}\n{definition}"
    if example:
        reply += f"\n\n_Example:_ {example}"
    return limit_response_words(f"{reply}\n\n{CHERRY_BLOSSOM}", 300)


def parse_ai_json(text: str) -> Any | None:
    """Parse a JSON value even when a model wraps it in a Markdown fence."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for marker in ("{", "["):
            index = cleaned.find(marker)
            if index >= 0:
                try:
                    value, _ = decoder.raw_decode(cleaned[index:])
                    return value
                except json.JSONDecodeError:
                    continue
    return None


def limit_response_words(text: str, maximum: int, compact: bool = False) -> str:
    """Enforce a hard word cap without changing already-short replies."""
    words = text.split()
    if len(words) <= maximum:
        result = text.strip()
    else:
        result = " ".join(words[:maximum]).rstrip(" ,;:") + "…"
    return " ".join(result.split()) if compact else result


async def call_llm(
    url: str | None,
    key: str,
    prompt: str,
    model: str | None = None,
    system_prompt: str | None = None,
    max_tokens: int = 250,
) -> str:
    if not key:
        raise ValueError("LLM API key is required.")
    endpoint = url or os.environ.get("LUNA_API_URL") or "https://api.groq.com/openai/v1/chat/completions"
    chosen_model = model or os.environ.get("LUNA_MODEL") or choose_llm_model(prompt)
    models = list(dict.fromkeys([chosen_model, DEFAULT_OSS_MODEL, "gpt-oss-120b"]))
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    errors: list[str] = []

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for current_model in models:
            try:
                async with session.post(
                    endpoint,
                    json=build_llm_payload(prompt, current_model, system_prompt, max_tokens),
                    headers=headers,
                ) as response:
                    body = await response.text()
                    if response.status != 200:
                        errors.append(f"{current_model}: HTTP {response.status} {body[:160]}")
                        continue
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        errors.append(f"{current_model}: invalid JSON")
                        continue
            except (aiohttp.ClientError, TimeoutError) as exc:
                errors.append(f"{current_model}: {exc}")
                continue

            answer = None
            if isinstance(data, dict):
                choices = data.get("choices")
                if isinstance(choices, list) and choices:
                    choice = choices[0]
                    if isinstance(choice, dict):
                        message = choice.get("message")
                        answer = message.get("content") if isinstance(message, dict) else None
                        answer = answer or choice.get("text")
                answer = answer or data.get("text") or data.get("output") or data.get("response")
            if isinstance(answer, str) and answer.strip():
                return answer.strip()
            errors.append(f"{current_model}: response contained no text")

    raise RuntimeError("; ".join(errors) or "LLM request failed")


async def generate_luna_chat_reply(prompt: str) -> str:
    """Generate one charming chat reply, with a useful offline fallback."""
    boundary = romantic_boundary_reply(prompt)
    if boundary:
        return ensure_emoji(boundary)
    special = special_chat_reply(prompt)
    if special:
        return ensure_emoji(special)

    key = os.environ.get("LUNA_API_KEY", "")
    if not key:
        return style_casual_reply(offline_chat_reply(prompt))

    information_request = prompt.casefold().startswith(
        ("what is ", "what are ", "define ", "explain ", "how does ", "tell me about ")
    )
    word_limit = 300 if information_request else 80
    try:
        answer = await call_llm(
            os.environ.get("LUNA_API_URL"),
            key,
            prompt + f"\nReply in no more than {word_limit} words.",
            system_prompt=LUNA_PERSONA,
            max_tokens=min(600, max(160, int(word_limit * 1.8))),
        )
    except (RuntimeError, ValueError, aiohttp.ClientError, TimeoutError):
        return style_casual_reply(offline_chat_reply(prompt))
    answer = limit_response_words(answer, word_limit, compact=word_limit <= 100)
    return ensure_emoji(answer) if information_request else style_casual_reply(answer)


async def generate_luna_joke() -> str:
    """Create a fresh sharp joke, rejecting duplicates and exhausted clichés."""
    key = os.environ.get("LUNA_API_KEY", "")
    banned = (
        "outstanding in his field",
        "why did the chicken",
        "walks into a bar",
        "i would tell you a joke about",
        "grins and taps",
    )
    themes = (
        "cat logic and human servitude",
        "technology behaving suspiciously",
        "modern work and meetings",
        "the brain's ridiculous habits",
        "an intelligent everyday observation",
        "animals quietly judging humans",
    )
    if key:
        for attempt in range(2):
            theme = random.choice(themes)
            prompt = (
                f"Write one original, genuinely surprising joke about {theme}. Use clever "
                "observational humour, absurd logic, or a sharp reversal. Dry sarcasm is welcome. "
                "Keep it under 80 words. Do not use a question-answer dad-joke template, famous "
                "stock punchlines, scarecrows, chickens crossing roads, or bar jokes. If you add "
                "a gesture, wrap it in Markdown asterisks. Return only the finished joke. "
                f"Freshness attempt: {attempt + 1}."
            )
            try:
                joke = await call_llm(
                    os.environ.get("LUNA_API_URL"),
                    key,
                    prompt,
                    system_prompt=LUNA_PERSONA,
                    max_tokens=180,
                )
            except (RuntimeError, ValueError, aiohttp.ClientError, TimeoutError):
                break
            joke = limit_response_words(joke, 80, compact=True)
            lowered = joke.casefold()
            bare_gesture = lowered.startswith(("grins ", "smiles ", "laughs ", "taps "))
            if (
                len(joke.split()) >= 10
                and not any(phrase in lowered for phrase in banned)
                and not bare_gesture
                and content_rotation.remember_generated("ai:jokes", {"title": joke})
            ):
                return style_joke_reply(joke)
    return style_joke_reply(content_rotation.take("offline:jokes", OFFLINE_JOKES)[0])


class DiscordLuna(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        def get_prefix(_bot, message):
            raw_content = message.content
            content = raw_content.casefold()
            if content.startswith("luna "):
                # Return the exact casing used in the message because prefix
                # matching itself is case-sensitive in discord.py.
                return [raw_content[:5]]
            if content == "luna":
                return [raw_content[:4]]
            return ["!"]

        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.game_manager = GameManager()
        self.timeout_manager: TimeoutManager | None = None
        for game in (
            WordBloomGame(), WordQuizGame(), CherryGardenGame(), CherryWordsArenaGame(),
            TriviaGame(), QuizGame(), RiddleGame(), EscapeRoomGame(),
            StorytellerGame(), WouldYouRatherGame(), CodenamesGame(),
        ):
            self.game_manager.register_game(game.name, game)

    async def setup_hook(self) -> None:
        self.timeout_manager = TimeoutManager(self.game_manager, self)
        await self.timeout_manager.start()
        await self.add_cog(LunaCog(self))

    async def close(self) -> None:
        if self.timeout_manager:
            await self.timeout_manager.stop()
        await super().close()

    async def on_ready(self) -> None:
        print(f"Luna is awake as {self.user} {CHERRY_BLOSSOM}")

    async def _is_reply_to_luna(self, message: discord.Message) -> bool:
        reference = getattr(message, "reference", None)
        if reference is None or self.user is None:
            return False
        resolved = getattr(reference, "resolved", None)
        author = getattr(resolved, "author", None)
        if author is not None:
            return author.id == self.user.id
        message_id = getattr(reference, "message_id", None)
        fetch_message = getattr(message.channel, "fetch_message", None)
        if message_id is None or fetch_message is None:
            return False
        try:
            replied_to = await fetch_message(message_id)
        except (discord.HTTPException, discord.Forbidden, discord.NotFound):
            return False
        return replied_to.author.id == self.user.id

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        try:
            await message.add_reaction(CHERRY_BLOSSOM)
        except (discord.HTTPException, discord.Forbidden):
            pass
        content = message.content.casefold()
        is_command = content == "luna" or content.startswith("luna ") or content.startswith("!")
        if is_command:
            await self.process_commands(message)
            return
        handled = await self.game_manager.handle_message(message, self)
        if handled:
            return
        if await self._is_reply_to_luna(message):
            answer = await generate_luna_chat_reply(message.content.strip() or "hi")
            await message.reply(answer, mention_author=False)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            content = ctx.message.content.strip()
            is_luna_message = content.casefold() == "luna" or content.casefold().startswith("luna ")
            prompt = content[5:].strip() if content.casefold().startswith("luna ") else ""
            if is_luna_message:
                prompt = prompt or "hi"
                boundary = romantic_boundary_reply(prompt)
                if boundary:
                    await ctx.reply(ensure_emoji(boundary), mention_author=False)
                    return
                special = special_chat_reply(prompt)
                if special:
                    await ctx.reply(ensure_emoji(special), mention_author=False)
                    return
                target = extract_definition_target(prompt)
                if target:
                    try:
                        result = await fetch_meaning(target)
                        await ctx.reply(format_definition_response(target, result), mention_author=False)
                        return
                    except (DefinitionNotFound, aiohttp.ClientError, TimeoutError):
                        pass
                await ctx.reply(await generate_luna_chat_reply(prompt), mention_author=False)
                return
            await ctx.reply("I don't know that command. Try `luna help`.", mention_author=False)
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"Missing `{error.param.name}`. Try `luna help` for usage.", mention_author=False)
            return
        if isinstance(error, commands.BadArgument):
            await ctx.reply("I couldn't understand that value. Try `luna help` for usage.", mention_author=False)
            return
        raise error


class LunaCog(commands.Cog):
    def __init__(self, bot: DiscordLuna) -> None:
        self.bot = bot

    async def _difficulty(self, ctx: commands.Context, value: str) -> str | None:
        difficulty = parse_difficulty(value)
        if difficulty is None:
            await ctx.reply(
                "Choose a flower level: 🌱 Easy, 🌼 Moderate, or 🌺 Difficult.",
                mention_author=False,
            )
            return None
        return difficulty

    async def _send_chunks(self, ctx: commands.Context, lines: list[str]) -> None:
        chunks: list[str] = []
        current = ""
        for line in lines:
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) > 1850 and current:
                chunks.append(current)
                current = line
            else:
                current = candidate
        if current:
            chunks.append(current)
        for index, chunk in enumerate(chunks):
            if index == 0:
                await ctx.reply(chunk, mention_author=False)
            else:
                await ctx.send(chunk)

    async def _ai_json(self, ctx: commands.Context, prompt: str) -> Any | None:
        """Generate validated JSON when an LLM key exists; otherwise use fallbacks."""
        key = os.environ.get("LUNA_API_KEY", "")
        if not key:
            return None
        try:
            async with ctx.typing():
                text = await call_llm(
                    os.environ.get("LUNA_API_URL"),
                    key,
                    prompt,
                    model=os.environ.get("LUNA_MODEL") or DEFAULT_OSS_MODEL,
                    system_prompt=GAME_GENERATOR_PERSONA,
                    max_tokens=900,
                )
        except (RuntimeError, ValueError, aiohttp.ClientError, TimeoutError):
            return None
        return parse_ai_json(text)

    async def _mcq_content(
        self,
        ctx: commands.Context,
        game_type: str,
        difficulty: str,
        fallback: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        focus = {
            "wordquiz": "English vocabulary meanings and usage",
            "trivia": "interesting facts across science, culture, language, and geography",
            "quiz": "educational questions across grammar, maths, science, and reasoning",
        }[game_type]
        payload = await self._ai_json(
            ctx,
            f"Create 5 unique {difficulty}-level multiple-choice questions about {focus}. "
            "Return {{\"questions\":[{{\"question\":str,\"options\":[4 strings],"
            "\"correct_answer\":\"A|B|C|D\",\"explanation\":str}}]}}. "
            "Do not reuse famous stock questions; make every answer unambiguous.",
        )
        values = payload.get("questions", []) if isinstance(payload, dict) else []
        generated: list[dict[str, Any]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            options = value.get("options")
            correct = str(value.get("correct_answer", "")).upper()
            if (
                isinstance(value.get("question"), str)
                and isinstance(options, list)
                and len(options) == 4
                and all(isinstance(option, str) and option.strip() for option in options)
                and len({option.strip().casefold() for option in options}) == 4
                and correct in "ABCD"
                and len(correct) == 1
                and isinstance(value.get("explanation"), str)
            ):
                item = dict(value, correct_answer=correct, difficulty=difficulty)
                if content_rotation.remember_generated(f"ai:{game_type}:{difficulty}", item):
                    generated.append(item)
            if len(generated) == 5:
                break
        if len(generated) < 5:
            generated.extend(
                content_rotation.take(
                    f"fallback:{game_type}:{difficulty}", fallback, 5 - len(generated)
                )
            )
        random.shuffle(generated)
        return generated

    async def _would_you_rather_content(
        self,
        ctx: commands.Context,
        difficulty: str,
        fallback: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        payload = await self._ai_json(
            ctx,
            f"Create 5 unique {difficulty}-level Would You Rather prompts for a learning game. "
            "Return {\"questions\":[{\"option_a\":str,\"option_b\":str,"
            "\"learning_focus\":str}]}. Keep them safe, thoughtful, age-appropriate, and debatable.",
        )
        values = payload.get("questions", []) if isinstance(payload, dict) else []
        generated = []
        for value in values:
            if not isinstance(value, dict) or not all(
                isinstance(value.get(key), str) and value[key].strip()
                for key in ("option_a", "option_b", "learning_focus")
            ):
                continue
            item = dict(value, difficulty=difficulty)
            if item["option_a"].strip().casefold() == item["option_b"].strip().casefold():
                continue
            if content_rotation.remember_generated(f"ai:wyr:{difficulty}", item):
                generated.append(item)
            if len(generated) == 5:
                break
        if len(generated) < 5:
            generated.extend(
                content_rotation.take(f"fallback:wyr:{difficulty}", fallback, 5 - len(generated))
            )
        random.shuffle(generated)
        return generated

    async def _wordbloom_content(self, ctx: commands.Context, difficulty: str) -> dict[str, str]:
        payload = await self._ai_json(
            ctx,
            f"Create one fresh {difficulty}-level English vocabulary challenge. Return "
            "{\"word\":\"one word\",\"definition\":\"clear definition without naming the word\"}. "
            "Choose an age-appropriate word and make the definition sufficient to guess it.",
        )
        if isinstance(payload, dict):
            word = str(payload.get("word", "")).strip().casefold()
            definition = str(payload.get("definition", "")).strip()
            item = {"word": word, "definition": definition}
            if (
                re.fullmatch(r"[a-z][a-z'-]{2,24}", word)
                and len(definition) >= 12
                and word not in definition.casefold()
                and content_rotation.remember_generated(f"ai:wordbloom:{difficulty}", item)
            ):
                return item
        fallback = [
            {"word": word, "definition": DEFAULT_WORDS[word]}
            for word in WORDS_BY_DIFFICULTY[difficulty]
        ]
        return content_rotation.take(f"fallback:wordbloom:{difficulty}", fallback)[0]

    async def _riddle_content(
        self,
        ctx: commands.Context,
        difficulty: str,
        fallback: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = await self._ai_json(
            ctx,
            f"Create one original {difficulty}-level wordplay riddle. Return "
            "{\"riddle\":str,\"answer\":str,\"accepted_answers\":[str],\"explanation\":str}. "
            "The clue must uniquely support the short answer; do not reuse a classic common riddle.",
        )
        if isinstance(payload, dict) and all(
            isinstance(payload.get(key), str) and payload[key].strip()
            for key in ("riddle", "answer", "explanation")
        ) and len(payload["answer"].strip()) <= 50:
            item = dict(payload, difficulty=difficulty)
            accepted = item.get("accepted_answers", [])
            item["accepted_answers"] = (
                [answer for answer in accepted if isinstance(answer, str) and answer.strip()]
                if isinstance(accepted, list)
                else []
            )
            if content_rotation.remember_generated(f"ai:riddle:{difficulty}", item):
                return item
        return dict(content_rotation.take(f"fallback:riddle:{difficulty}", fallback)[0])

    async def _escape_content(self, ctx: commands.Context, difficulty: str) -> dict[str, Any] | None:
        payload = await self._ai_json(
            ctx,
            f"Create one original interactive {difficulty}-level educational escape-room puzzle. "
            "Return a JSON object with: title, scene, items (object of 3-5 lowercase item names "
            "to descriptions), clue_item, key_item, clues (object with easy, medium, hard), "
            "answer (one short word or code), success, and learning_note. clue_item and key_item "
            "must exactly match keys in items. The clue must logically determine the answer.",
        )
        if isinstance(payload, dict) and isinstance(payload.get("items"), dict):
            payload["items"] = {
                str(name).strip().casefold(): str(description).strip()
                for name, description in payload["items"].items()
            }
            payload["clue_item"] = str(payload.get("clue_item", "")).strip().casefold()
            payload["key_item"] = str(payload.get("key_item", "")).strip().casefold()
            payload["answer"] = str(payload.get("answer", "")).strip().casefold()
        if valid_escape_puzzle(payload) and content_rotation.remember_generated(
            f"ai:escape:{difficulty}", payload
        ):
            return payload
        return None

    async def _garden_content(self, ctx: commands.Context, difficulty: str) -> list[dict[str, Any]]:
        payload = await self._ai_json(
            ctx,
            f"Create 10 unique {difficulty}-level English grammar questions in random order: "
            "exactly 2 multiple_choice, 2 fill_blank, 2 true_false, 2 sentence_creation, and "
            "2 correction. Return {\"questions\":[{\"topic\":str,\"question_type\":str,"
            "\"prompt\":str,\"answers\":[accepted strings],\"model_answer\":str,"
            "\"explanation\":str,\"options\":[4 strings when multiple_choice],"
            "\"required_words\":[str when sentence_creation],\"min_words\":number}]}. "
            "Explanations must briefly say why the correct form works and why a likely wrong "
            "form fails. Keep every answer unambiguous.",
        )
        values = payload.get("questions", []) if isinstance(payload, dict) else []
        result = []
        for value in values:
            if not isinstance(value, dict):
                continue
            if valid_garden_question(value) and content_rotation.remember_generated(
                f"ai:garden:{difficulty}", value
            ):
                result.append(value)
            if len(result) == 10:
                break
        expected_types = {
            "multiple_choice", "fill_blank", "true_false", "sentence_creation", "correction"
        }
        if len(result) != 10 or any(
            sum(item["question_type"] == question_type for item in result) != 2
            for question_type in expected_types
        ):
            return []
        return result

    async def _story_content(self, ctx: commands.Context, difficulty: str) -> str | None:
        payload = await self._ai_json(
            ctx,
            f"Create one original {difficulty}-level collaborative story opening for a Discord "
            "learning game. Return {\"opening_prompt\":str}. It should invite many possible "
            "continuations and fit in two sentences.",
        )
        if isinstance(payload, dict) and isinstance(payload.get("opening_prompt"), str):
            prompt = payload["opening_prompt"].strip()
            if 20 <= len(prompt) <= 400 and content_rotation.remember_generated(
                f"ai:story:{difficulty}", {"title": prompt}
            ):
                return prompt
        return None

    async def _create_game(
        self,
        ctx: commands.Context,
        game_type: str,
        state: dict[str, Any] | None = None,
        lobby: bool | None = None,
    ) -> None:
        game = self.bot.game_manager.get_game(game_type)
        if game is None:
            await ctx.reply("That game is not configured.", mention_author=False)
            return
        try:
            session = self.bot.game_manager.create_session(
                ctx.channel.id,
                ctx.guild.id if ctx.guild else 0,
                game_type,
                ctx.author.id,
            )
        except RuntimeError:
            await ctx.reply(
                "A game or lobby is already active here. Use `luna stop` first.",
                mention_author=False,
            )
            return

        session.state.update(state or {})
        session.state.update(host_id=ctx.author.id, finished=False)
        needs_lobby = game.max_players > 1 if lobby is None else lobby
        if needs_lobby:
            session.state["lobby"] = True
            details = GAME_HELP.get(game_type, {})
            await ctx.reply(
                f"🌸 **{game_type.replace('_', ' ').title()} lobby created!**\n"
                f"**What this game is:** {GAME_DESCRIPTIONS.get(game_type, game.description)}\n"
                f"**Example:** {details.get('example', 'Follow Luna’s prompt when the game begins.')}\n"
                f"Others can use `luna join`. Host <@{ctx.author.id}> starts it with `luna begin`.",
                mention_author=False,
            )
            return

        session.state["lobby"] = False
        try:
            await game.start(session, ctx)
        except Exception:
            self.bot.game_manager.delete_session(ctx.channel.id)
            raise
        if session.state.get("finished"):
            self.bot.game_manager.delete_session(ctx.channel.id)

    @commands.command(name="join")
    async def join_game(self, ctx: commands.Context) -> None:
        session = self.bot.game_manager.get_session(ctx.channel.id)
        if not session or not session.state.get("lobby"):
            await ctx.reply("There is no open game lobby in this channel.", mention_author=False)
            return
        game = self.bot.game_manager.get_game(session.game_type)
        if ctx.author.id in session.player_ids:
            await ctx.reply("You're already in this lobby.", mention_author=False)
            return
        if game is None or len(session.player_ids) >= game.max_players:
            await ctx.reply("That lobby is full.", mention_author=False)
            return
        session.add_player(ctx.author.id)
        session.update_activity()
        await ctx.reply(
            f"<@{ctx.author.id}> joined! **{len(session.player_ids)}/{game.max_players}** players.",
            mention_author=False,
        )

    @commands.command(name="begin", aliases=["start"])
    async def begin_game(self, ctx: commands.Context) -> None:
        session = self.bot.game_manager.get_session(ctx.channel.id)
        if not session or not session.state.get("lobby"):
            await ctx.reply("There is no lobby waiting to begin.", mention_author=False)
            return
        if ctx.author.id != session.state.get("host_id"):
            await ctx.reply("Only the lobby host can begin this game.", mention_author=False)
            return
        game = self.bot.game_manager.get_game(session.game_type)
        if game is None:
            self.bot.game_manager.delete_session(ctx.channel.id)
            await ctx.reply("That game is no longer configured.", mention_author=False)
            return
        minimum = getattr(game, "min_players", 1)
        if len(session.player_ids) < minimum:
            await ctx.reply(
                f"This game needs at least **{minimum} players**. "
                f"Current lobby: **{len(session.player_ids)}**.",
                mention_author=False,
            )
            return
        session.state["lobby"] = False
        session.update_activity()
        try:
            await game.start(session, ctx)
        except Exception:
            self.bot.game_manager.delete_session(ctx.channel.id)
            raise
        if session.state.get("finished"):
            self.bot.game_manager.delete_session(ctx.channel.id)

    @commands.command(name="stop", aliases=["endgame", "cancelgame"])
    async def stop_game(self, ctx: commands.Context) -> None:
        session = self.bot.game_manager.get_session(ctx.channel.id)
        if not session:
            await ctx.reply("No game is active here.", mention_author=False)
            return
        if ctx.author.id != session.state.get("host_id"):
            await ctx.reply("Only the game host can stop it.", mention_author=False)
            return
        game = self.bot.game_manager.get_game(session.game_type)
        if game:
            await game.end(session)
        self.bot.game_manager.delete_session(ctx.channel.id)
        await ctx.reply("Game stopped. The channel is ready for a new one. 🌸", mention_author=False)

    @commands.command(name="score", aliases=["scores"])
    async def score(self, ctx: commands.Context) -> None:
        session = self.bot.game_manager.get_session(ctx.channel.id)
        if not session:
            await ctx.reply("No game is active here.", mention_author=False)
            return
        lines = [f"<@{uid}>: **{session.score.get(uid, 0)}**" for uid in session.player_ids]
        await ctx.reply("**Current scores**\n" + "\n".join(lines), mention_author=False)

    @commands.command(name="help")
    async def luna_help(self, ctx: commands.Context, topic: str = "") -> None:
        requested = topic.strip().casefold().replace("-", "_")
        requested = GAME_HELP_ALIASES.get(requested, requested)
        if requested in GAME_HELP:
            details = GAME_HELP[requested]
            await ctx.reply(
                f"**{requested.replace('_', ' ').title()}**\n"
                f"**Command:** `{details['command']}`\n"
                f"**Players:** {details['players']}\n"
                f"**How to play:** {details['how']}\n"
                f"**Example:** {details['example']}\n"
                f"**What you learn:** {details['learning']}",
                mention_author=False,
            )
            return
        if requested and requested not in {"games", "game", "all"}:
            await ctx.reply(
                "I don't have that help topic. Use `luna help games` or "
                "`luna help <game name>`—for example, `luna help wyr`.",
                mention_author=False,
            )
            return

        lines = [
            "**Luna Help — Learning Games** 🌸🤍",
            "**Choose one flower level (all games default to 🌱):**",
            "🌱 **Easy** — gentle questions and clearer clues",
            "🌼 **Moderate** — more thinking and richer language",
            "🌺 **Difficult** — advanced questions and fewer hints",
            "Use the flower directly, for example: `luna escape 🌼` or `luna trivia 🌺`.",
            "AI creates fresh validated content when configured; curated content rotates without repeats.",
            "",
        ]
        for name, description in GAME_DESCRIPTIONS.items():
            command = GAME_HELP[name]["command"]
            lines.append(f"**`{command}`**\n{description}")
        lines.extend(
            [
                "",
                "**Multiplayer:** create the game → others use `luna join` → host uses `luna begin`.",
                "**Controls:** `luna score`, `luna stop`.",
                "**Detailed rules:** `luna help <game>`; examples: `luna help wyr`, `luna help escape`.",
                "**Other tools:** `luna about`, `luna meaning <word>`, `luna spell <word>`, "
                "`luna quote`, `luna joke`, `luna fact`, `luna search`, `luna story`, `luna chat`.",
            ]
        )
        await self._send_chunks(ctx, lines)

    @commands.command(name="game", aliases=["games"])
    async def game_list(self, ctx: commands.Context) -> None:
        help_command = self.bot.get_command("help")
        if help_command:
            await ctx.invoke(help_command, topic="games")

    @commands.command(name="wordbloom", aliases=["tea", "word"])
    async def wordbloom(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is None:
            return
        item = await self._wordbloom_content(ctx, difficulty)
        await self._create_game(
            ctx, "wordbloom",
            {"word": item["word"], "definition": item["definition"], "difficulty": difficulty},
        )

    @commands.command(name="wordquiz", aliases=["trio"])
    async def wordquiz(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is None:
            return
        fallback = _items_for_difficulty(
            _load_json_list("word_quiz.json", "word_quiz_questions"), difficulty
        )
        questions = await self._mcq_content(ctx, "wordquiz", difficulty, fallback)
        await self._create_game(ctx, "wordquiz", {"questions": questions, "difficulty": difficulty})

    @commands.command(name="trivia")
    async def trivia(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is None:
            return
        fallback = _items_for_difficulty(
            _load_json_list("trivia.json", "trivia_questions"), difficulty
        )
        questions = await self._mcq_content(ctx, "trivia", difficulty, fallback)
        await self._create_game(ctx, "trivia", {"questions": questions, "difficulty": difficulty})

    @commands.command(name="quiz")
    async def quiz(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is None:
            return
        fallback = _items_for_difficulty(
            _load_json_list("quiz_questions.json", "quiz_questions"), difficulty
        )
        questions = await self._mcq_content(ctx, "quiz", difficulty, fallback)
        await self._create_game(ctx, "quiz", {"questions": questions, "difficulty": difficulty})

    @commands.command(name="riddle")
    async def riddle(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is None:
            return
        riddles = _items_for_difficulty(_load_json_list("riddles.json", "riddles"), difficulty)
        if not riddles:
            await ctx.reply("The riddle book is unavailable right now.", mention_author=False)
            return
        state = await self._riddle_content(ctx, difficulty, riddles)
        state["difficulty"] = difficulty
        await self._create_game(ctx, "riddle", state)

    @commands.command(name="escape", aliases=["escaperoom"])
    async def escape(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is not None:
            puzzle = await self._escape_content(ctx, difficulty)
            await self._create_game(
                ctx, "escape", {"difficulty": difficulty, **({"puzzle": puzzle} if puzzle else {})}
            )

    @commands.command(name="storyteller")
    async def storyteller(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is not None:
            opening = await self._story_content(ctx, difficulty)
            await self._create_game(
                ctx,
                "storyteller",
                {"difficulty": difficulty, **({"opening_prompt": opening} if opening else {})},
            )

    @commands.command(name="wyr", aliases=["wouldyourather", "would_you_rather"])
    async def would_you_rather(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is None:
            return
        fallback = _items_for_difficulty(
            _load_json_list("would_you_rather.json", "would_you_rather_questions"), difficulty
        )
        questions = await self._would_you_rather_content(ctx, difficulty, fallback)
        await self._create_game(ctx, "would_you_rather", {"questions": questions, "difficulty": difficulty})

    @commands.command(name="cherrygarden")
    async def cherry_garden(self, ctx: commands.Context, mode: str = "easy") -> None:
        mode = await self._difficulty(ctx, mode)
        if mode is None:
            return
        questions = await self._garden_content(ctx, mode)
        await self._create_game(
            ctx,
            "cherrygarden",
            {"mode": mode, **({"questions": questions} if questions else {})},
        )

    @commands.command(name="cherrywords", aliases=["arena"])
    async def cherry_words(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is not None:
            await self._create_game(ctx, "cherrywords", {"difficulty": difficulty})

    @commands.command(name="codenames", aliases=["codename"])
    async def codenames(self, ctx: commands.Context, mode: str = "solo", difficulty: str = "easy") -> None:
        mode = mode.casefold().strip("'\"")
        shortcut_level = parse_difficulty(mode)
        if shortcut_level and difficulty == "easy":
            difficulty, mode = shortcut_level, "solo"
        mode = {
            "single": "solo",
            "singleplayer": "solo",
            "multiple": "multi",
            "multiplayer": "multi",
        }.get(mode, mode)
        if mode not in {"solo", "multi"}:
            await ctx.reply(
                "Use `luna codenames solo <level>` or `luna codenames multi <level>`.",
                mention_author=False,
            )
            return
        if mode == "multi" and ctx.guild is None:
            await ctx.reply("Multiplayer Codenames must be started in a server channel.", mention_author=False)
            return
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is None:
            return
        await self._create_game(
            ctx,
            "codenames",
            {"play_mode": mode, "difficulty": difficulty},
            lobby=(mode == "multi"),
        )

    @commands.command(name="about", aliases=["personality", "whoareyou"])
    async def about(self, ctx: commands.Context) -> None:
        await ctx.reply(luna_about_text(), mention_author=False)

    @commands.command(name="meaning")
    async def meaning(self, ctx: commands.Context, *, term: str) -> None:
        try:
            result = await fetch_meaning(term.strip())
        except (DefinitionNotFound, aiohttp.ClientError, TimeoutError):
            await ctx.reply(f"I couldn't find **{term}** in the dictionary.", mention_author=False)
            return
        await ctx.reply(format_definition_response(result.get("word", term), result), mention_author=False)

    async def _llm_reply(
        self,
        ctx: commands.Context,
        prompt: str,
        unavailable: str,
        boundary_text: str | None = None,
        max_words: int = 80,
    ) -> None:
        if boundary_text is not None:
            await ctx.reply(await generate_luna_chat_reply(boundary_text), mention_author=False)
            return
        boundary = romantic_boundary_reply(boundary_text) if boundary_text else None
        if boundary:
            await ctx.reply(boundary, mention_author=False)
            return
        special = special_chat_reply(boundary_text) if boundary_text else None
        if special:
            await ctx.reply(special, mention_author=False)
            return
        key = os.environ.get("LUNA_API_KEY", "")
        if not key:
            await ctx.reply(f"{unavailable} Set `LUNA_API_KEY` to enable it.", mention_author=False)
            return
        async with ctx.typing():
            try:
                answer = await call_llm(
                    os.environ.get("LUNA_API_URL"),
                    key,
                    prompt + f"\nKeep the response within {max_words} words.",
                    system_prompt=LUNA_PERSONA,
                    max_tokens=min(600, max(100, int(max_words * 1.8))),
                )
            except (RuntimeError, ValueError):
                await ctx.reply("The language model is unavailable right now. Try again later.", mention_author=False)
                return
        await ctx.reply(
            ensure_emoji(limit_response_words(answer, max_words, compact=max_words <= 100)),
            mention_author=False,
        )

    @commands.command(name="quote")
    async def quote(self, ctx: commands.Context) -> None:
        await self._llm_reply(
            ctx, "Give one short inspirational quote.", "Quote generation needs an LLM key.", max_words=50
        )

    @commands.command(name="joke")
    async def joke(self, ctx: commands.Context) -> None:
        async with ctx.typing():
            answer = await generate_luna_joke()
        await ctx.reply(answer, mention_author=False)

    @commands.command(name="fact")
    async def fact(self, ctx: commands.Context) -> None:
        await self._llm_reply(
            ctx, "Share one accurate, interesting fact.", "Fact generation needs an LLM key.", max_words=100
        )

    @commands.command(name="search")
    async def search(self, ctx: commands.Context, *, query: str) -> None:
        await self._llm_reply(
            ctx,
            f"Answer accurately with useful detail: {query}",
            "Search needs an LLM key.",
            max_words=300,
        )

    @commands.command(name="story")
    async def story(self, ctx: commands.Context, *, theme: str) -> None:
        await self._llm_reply(
            ctx,
            f"Write a warm short story about: {theme}",
            "Story generation needs an LLM key.",
            max_words=300,
        )

    @commands.command(name="chat")
    async def chat(self, ctx: commands.Context, *, message: str) -> None:
        await self._llm_reply(
            ctx, message, "Chat needs an LLM key.", boundary_text=message, max_words=80
        )

    @commands.command(name="spell")
    async def spell(self, ctx: commands.Context, *, word: str) -> None:
        await self._llm_reply(
            ctx,
            f"Explain the spelling and pronunciation of: {word}",
            "Spelling help needs an LLM key.",
            max_words=180,
        )
