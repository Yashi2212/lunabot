from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands

from .birthday import (
    PIL_AVAILABLE as BIRTHDAY_IMAGES_AVAILABLE,
    birthday_caption,
    birthday_wish,
    clean_birthday_name,
    render_birthday_gif,
)
from .core import GameManager, TimeoutManager
from .content_rotation import content_rotation
from .definitions import DictionaryUnavailable, DefinitionNotFound, fetch_meaning
from .games import (
    CherryGardenGame,
    CherryWordsArenaGame,
    CodenamesGame,
    EscapeRoomGame,
    JumbledWordGame,
    MemoryGame,
    RiddleGame,
    StorytellerGame,
    TriviaGame,
    WordleGame,
    WordQuizGame,
)
from .games.difficulty import parse_difficulty
from .games.cherry_garden import valid_garden_question
from .games.codenames import validate_ai_codenames_board
from .games.cherry_words_arena import CHERRYWORDS_FALLBACK_SEQUENCES
from .games.escape import ESCAPE_PUZZLES, valid_escape_puzzle
from .games.round_plan import DIFFICULTY_COUNTS, ROUND_SIZE
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
EMOJI_ACCENTS = ("🌸", "🤍", "✨", "🌟", "💖", "🌙", "☁️", "🫶", "🔎")
DEFAULT_OSS_MODEL = "openai/gpt-oss-120b"
DEFAULT_FALLBACK_MODEL = "openai/gpt-oss-20b"
DEFAULT_CHERRY_GAMES_MODEL = "llama-3.1-8b-instant"
DEFAULT_CHERRY_GAMES_FALLBACK_MODEL = DEFAULT_OSS_MODEL
DEFAULT_CHERRYWORDS_MODEL = DEFAULT_CHERRY_GAMES_MODEL
DEFAULT_CHERRYWORDS_FALLBACK_MODEL = DEFAULT_OSS_MODEL
DEFAULT_CHERRYGARDEN_MODEL = DEFAULT_CHERRY_GAMES_MODEL
DEFAULT_CHERRYGARDEN_FALLBACK_MODEL = DEFAULT_CHERRY_GAMES_FALLBACK_MODEL
DEFAULT_LLAMA_MODEL = "llama-3.3-70b-versatile"
DATA_DIR = Path(__file__).resolve().parent / "data"
RIDDLE_BANK_SIZE = ROUND_SIZE
RIDDLE_BATCH_SIZE = 10
RIDDLE_MAX_API_ATTEMPTS = 8
JUMBLE_BANK_SIZE = ROUND_SIZE
JUMBLE_BATCH_SIZE = 5
JUMBLE_MAX_API_ATTEMPTS = 4
CHERRYWORDS_BATCH_SIZE = 10
CHERRYWORDS_MAX_API_ATTEMPTS = 5
CHERRYGARDEN_BATCH_SIZE = 5
CHERRYGARDEN_MAX_API_ATTEMPTS = 5

CHERRYWORDS_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "cherrywords_sequences",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "sequences": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "letters": {"type": "string"},
                            "examples": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["letters", "examples"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["sequences"],
            "additionalProperties": False,
        },
    },
}

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

OFFLINE_TOPIC_FACTS = {
    "alps": (
        "The Alps are a major mountain range in Europe, stretching across countries "
        "including France, Switzerland, Italy, Austria, and Slovenia.",
        "https://en.wikipedia.org/wiki/Alps",
    ),
    "japan": (
        "Japan is an island country in East Asia. Its capital and largest city is Tokyo.",
        "https://en.wikipedia.org/wiki/Japan",
    ),
}

GAME_DESCRIPTIONS = {
    "wordquiz": "Choose A-D for vocabulary meanings, then learn why the answer is correct.",
    "riddle": "Ten-riddle race with 2 difficult, 3 moderate, and 5 easy riddles.",
    "messed": "Ten-round jumbled-word race with 2 difficult, 3 moderate, and 5 easy words.",
    "memo": "Ten memory challenges with 2 difficult, 3 moderate, and 5 easy sequences.",
    "escape": "Search, collect, inspect, and solve a rotating interactive puzzle room.",
    "trivia": "Single-player or multiplayer race across geography, history, countries, world facts, and basic knowledge.",
    "storyteller": "Players take turns adding one sentence to a collaborative story.",
    "cherrygarden": "Multiplayer English grammar and sentence-correction competition.",
    "cherrywords": "Turn-based word game: each player gets a separate letter prompt before the timer.",
    "wordle": "Single-player six-row Wordle board with green, yellow, and black feedback.",
    "codenames": "Connect clues to words on a pastel 5x4 board, solo or in two teams.",
}

GAME_HELP = {
    "wordquiz": {
        "command": "luna wordquiz <level>",
        "players": "Single-player",
        "how": "Read a vocabulary question and reply A, B, C, or D.",
        "example": "‘Which word means calm?’ A) Serene B) Rough → reply `A`.",
        "learning": "Every answer is followed immediately by a definition and explanation.",
    },
    "riddle": {
        "command": "luna riddle",
        "players": "Single-player or multiplayer · 1–10 (lobby)",
        "how": "Play exactly 10 fresh riddles. The round always contains 2 Difficult, 3 Moderate, and 5 Easy riddles; each riddle gives 1, 2, or 3 attempts respectively.",
        "example": "`luna riddle` → Luna generates one mixed 10-riddle round.",
        "learning": "Use up to two shared hints for the first letter and letter count; every answer reveal explains the wordplay.",
    },
    "messed": {
        "command": "luna jumbled",
        "players": "Single-player or multiplayer · 1–10 (lobby)",
        "how": "Unscramble exactly 10 fresh words. The round always contains 2 Difficult, 3 Moderate, and 5 Easy words; the first correct answer earns a point.",
        "example": "`luna jumbled` → Luna generates one mixed 10-word round. (`luna messed` is also supported.)",
        "learning": "Each answer reveal includes a short definition so the word sticks.",
    },
    "memo": {
        "command": "luna memo",
        "players": "Single-player or multiplayer · 1–10 (lobby)",
        "how": "Play exactly 10 memory challenges. The round always contains 2 Difficult, 3 Moderate, and 5 Easy sequences; the display time follows each sequence's level.",
        "example": "`luna memo` → Luna starts a mixed 10-sequence round.",
        "learning": "Practises visual recall, order, and attention to detail.",
    },
    "escape": {
        "command": "luna escape <level>",
        "players": "Single-player",
        "how": "Use `look`, `search`, `take <item>`, `inspect <item>`, `hint`, and `solve <answer>`.",
        "example": "`search` → `take star chart` → `inspect star chart` → `solve 4217`.",
        "learning": "Every solved room ends with the idea behind its puzzle.",
    },
    "trivia": {
        "command": "luna trivia <level>",
        "players": "Single-player or multiplayer · 1–5 (lobby)",
        "how": "Questions rotate through geography, history, general knowledge, countries, world facts, and basic facts. React 🇦-🇩 or type A-D; each player's first choice locks and the first correct choice wins.",
        "example": "Capital of France? 🇦 Rome 🇧 Paris → react 🇧 quickly.",
        "learning": "The correct answer appears with a factual explanation on the next line.",
    },
    "storyteller": {
        "command": "luna storyteller <level>",
        "players": "Single-player or multiplayer · 1–5 (lobby)",
        "how": "Follow the opening prompt and add exactly one sentence on your turn.",
        "example": "Opening: ‘A lantern appeared…’ → `Mira picked it up carefully.`",
        "learning": "Difficulty changes the writing skill: clarity, vivid description, or figurative language.",
    },
    "cherrygarden": {
        "command": "luna cherrygarden <level>",
        "players": "Single-player or multiplayer · 1–5 (lobby)",
        "how": "Correct a sentence or fill a blank; each player submits one answer.",
        "example": "‘She ___ a book each night.’ → `reads`.",
        "learning": "The accepted answer is followed by its grammar explanation.",
    },
    "cherrywords": {
        "command": "luna cherrywords <level> [meaning] [time N seconds] / luna cherrywords timeless",
        "players": "Single-player or multiplayer · 1–5 (lobby)",
        "how": "Players take turns. Timed games use HP; timeless mode has no timer or lifelines.",
        "example": "`luna cherrywords medium time 5 seconds`, `luna cherrywords timeless`, or `luna cherrywords help alg`.",
        "learning": "Meanings are hidden during fast play unless you add `meaning`.",
    },
    "wordle": {
        "command": "luna wordle",
        "players": "Single-player",
        "how": "Play one six-row board. Submit valid five-letter guesses; 🟩 is correct place, 🟨 is the word in another place, and ⬛ is absent.",
        "example": "`luna wordle` → `crane` → read the colored row and keep guessing.",
        "learning": "Each row gives precise letter-placement feedback, including duplicate-letter handling.",
    },
    "codenames": {
        "command": "luna codenames <solo|multi> <level>",
        "players": "Single-player or multiplayer · 1 solo; 4–10 multiplayer",
        "how": "Connect a clue to board words and select cards with A-T. Avoid neutral, opponent, and assassin cards.",
        "example": "Clue `OCEAN — 2` might point to `WHALE` and `CORAL`; reply with their card letters.",
        "learning": "Every revealed word receives a concise vocabulary definition.",
    },
}

GAME_HELP_ALIASES = {
    "trio": "wordquiz",
    "arena": "cherrywords", "codename": "codenames", "escaperoom": "escape",
    "jumble": "messed", "jumbled": "messed", "anagram": "messed",
    "memory": "memo", "memorymatch": "memo", "emojimemory": "memo",
}


class HelpPaginator(discord.ui.View):
    """Interactive, requester-scoped pagination for Luna's command guide."""

    def __init__(self, pages: list[str], author_id: int) -> None:
        super().__init__(timeout=180)
        self.pages = pages
        self.author_id = author_id
        self.page = 0
        self.message: discord.Message | None = None
        self._sync_buttons()

    @property
    def current_page(self) -> str:
        return f"{self.pages[self.page]}\n\n*Page {self.page + 1}/{len(self.pages)}*"

    def _sync_buttons(self) -> None:
        self.previous_button.disabled = self.page == 0
        self.next_button.disabled = self.page == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message(
            "Only the person who requested this help menu can turn its pages.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page > 0:
            self.page -= 1
        self._sync_buttons()
        await interaction.response.edit_message(content=self.current_page, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if self.page < len(self.pages) - 1:
            self.page += 1
        self._sync_buttons()
        await interaction.response.edit_message(content=self.current_page, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.HTTPException, discord.NotFound):
                pass

AUTO_MODEL_KEYWORDS = {
    "meaning", "define", "word", "grammar", "translate", "sentence",
    "synonym", "spelling", "spell", "vocabulary",
}


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
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    if response_format:
        payload["response_format"] = response_format
    if model in {DEFAULT_OSS_MODEL, DEFAULT_FALLBACK_MODEL}:
        # GPT-OSS can spend the entire output budget on hidden reasoning when
        # generating large JSON batches. Keep reasoning light and return the
        # final answer in message.content for the JSON parser.
        payload["reasoning_effort"] = "low"
        payload["include_reasoning"] = False
    return payload


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


def looks_like_dictionary_query(query: str) -> bool:
    cleaned = query.strip()
    if not cleaned or len(cleaned) > 40:
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z'-]*", cleaned))


def extract_containing_letters_query(query: str) -> str | None:
    cleaned = " ".join(query.casefold().split())
    match = re.search(r"\b(?:words?\s+)?(?:containing|with|using)\s+([a-z]{3})\b", cleaned)
    if match:
        return match.group(1)
    return None


def format_search_definition_response(term: str, result: dict[str, Any]) -> str:
    return format_search_definition_card(term, result)


def format_search_definition_card(
    term: str,
    result: dict[str, Any],
    wikipedia_url: str | None = None,
) -> str:
    word = result.get("word") or term
    phonetic = result.get("phonetic") or ""
    lines = [f"🔎 **{word}** {phonetic}".rstrip()]

    for meaning in result.get("meanings", [])[:3]:
        part = meaning.get("partOfSpeech") or "word"
        lines.append(f"\n**{part}**")
        for item in meaning.get("definitions", [])[:2]:
            definition = item.get("definition")
            if definition:
                lines.append(f"• {definition}")
            example = item.get("example")
            if example:
                lines.append(f"  _Example:_ {example}")
        synonyms = meaning.get("synonyms") or []
        if synonyms:
            lines.append(f"  Similar: {', '.join(synonyms[:5])}")

    source_urls = result.get("sourceUrls") or []
    if source_urls:
        lines.append(f"\nSource: {source_urls[0]}")
    if wikipedia_url:
        lines.append(f"Wikipedia: {wikipedia_url}")
    lines.append(CHERRY_BLOSSOM)
    return limit_response_words("\n".join(lines), 360)


async def fetch_wikipedia_url(term: str) -> str | None:
    cleaned = term.strip()
    if not cleaned:
        return None
    api_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "opensearch",
        "search": cleaned,
        "limit": "1",
        "namespace": "0",
        "format": "json",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, params=params) as response:
                if response.status != 200:
                    return None
                data = await response.json()
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return None

    if (
        isinstance(data, list)
        and len(data) >= 4
        and isinstance(data[1], list)
        and isinstance(data[3], list)
        and data[1]
        and data[3]
    ):
        return str(data[3][0])
    return f"https://en.wikipedia.org/wiki/{quote(cleaned.replace(' ', '_'))}"


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


def trim_incomplete_long_response(text: str) -> str:
    """Remove a model's visibly cut-off final fragment from a long answer."""
    result = text.strip()
    if not result:
        return result
    if re.search(r"[.!?](?:[\"'’”)*_~`\]]*)$", result):
        return result
    if any(result.endswith(emoji) for emoji in EMOJI_ACCENTS):
        return result

    endings = list(re.finditer(r"[.!?](?:[\"'’”)*_~`\]]*)", result))
    if endings:
        last_end = endings[-1].end()
        # Only trim when a useful majority of the answer remains.
        if last_end >= len(result) // 2:
            return result[:last_end].rstrip()
    return result.rstrip(" ,;:-") + "…"


def split_discord_message(text: str, limit: int = 1900) -> list[str]:
    """Split a complete answer at readable boundaries before Discord's limit."""
    remaining = text.strip()
    chunks: list[str] = []
    while len(remaining) > limit:
        cut = max(
            remaining.rfind("\n\n", 0, limit),
            remaining.rfind("\n", 0, limit),
            remaining.rfind(". ", 0, limit),
        )
        if cut < limit // 2:
            cut = remaining.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        elif remaining[cut:cut + 2] == ". ":
            cut += 1
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def call_llm(
    url: str | None,
    key: str,
    prompt: str,
    model: str | None = None,
    system_prompt: str | None = None,
    max_tokens: int = 250,
    fallback_model: str | None = None,
    response_format: dict[str, Any] | None = None,
) -> str:
    if not key:
        raise ValueError("LLM API key is required.")
    endpoint = url or os.environ.get("LUNA_API_URL") or "https://api.groq.com/openai/v1/chat/completions"
    chosen_model = model or os.environ.get("LUNA_MODEL") or choose_llm_model(prompt)
    selected_fallback_model = (
        fallback_model or os.environ.get("LUNA_FALLBACK_MODEL") or DEFAULT_FALLBACK_MODEL
    )
    models = list(dict.fromkeys([chosen_model, selected_fallback_model]))
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    errors: list[str] = []

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for current_model in models:
            try:
                async with session.post(
                    endpoint,
                    json=build_llm_payload(
                        prompt,
                        current_model,
                        system_prompt,
                        max_tokens,
                        (
                            {"type": "json_object"}
                            if isinstance(response_format, dict)
                            and response_format.get("type") == "json_schema"
                            and current_model not in {DEFAULT_OSS_MODEL, DEFAULT_FALLBACK_MODEL}
                            else response_format
                        ),
                    ),
                    headers=headers,
                ) as response:
                    body = await response.text()
                    if response.status != 200:
                        errors.append(f"{current_model}: HTTP {response.status} {body[:500]}")
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
        (
            "what is ", "what are ", "define ", "explain ", "how does ",
            "how do ", "how to ", "how can ", "why ", "when ", "where ",
            "tell me about ",
        )
    )
    word_limit = 300 if information_request else 80
    request_prompt = prompt + f"\nReply in no more than {word_limit} words."
    if information_request:
        request_prompt += (
            "\nAnswer clearly and practically first. Add at most one subtle moonlit "
            "gothic-cherry-blossom image; do not turn factual guidance into poetry "
            "or add stage directions."
        )
    try:
        answer = await call_llm(
            os.environ.get("LUNA_API_URL"),
            key,
            request_prompt,
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
            WordQuizGame(), CherryGardenGame(), CherryWordsArenaGame(),
            TriviaGame(), WordleGame(), RiddleGame(), EscapeRoomGame(),
            StorytellerGame(), CodenamesGame(),
            JumbledWordGame(), MemoryGame(),
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

    @staticmethod
    async def _add_luna_reaction(message: discord.Message) -> None:
        """React only after a message is confirmed as an interaction with Luna."""
        try:
            await message.add_reaction(CHERRY_BLOSSOM)
        except (discord.HTTPException, discord.Forbidden):
            pass

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        content = message.content.casefold()
        is_command = content == "luna" or content.startswith("luna ") or content.startswith("!")
        if is_command:
            await self._add_luna_reaction(message)
            await self.process_commands(message)
            return
        session = self.game_manager.get_session(message.channel.id)
        is_riddle_answer = bool(
            session
            and session.game_type == "riddle"
            and not session.state.get("lobby")
        )
        handled = await self.game_manager.handle_message(message, self)
        if handled:
            if not is_riddle_answer:
                await self._add_luna_reaction(message)
            return
        if await self._is_reply_to_luna(message):
            await self._add_luna_reaction(message)
            answer = await generate_luna_chat_reply(message.content.strip() or "hi")
            await message.reply(answer, mention_author=False)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        await self.game_manager.handle_reaction(payload, self)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            content = ctx.message.content.strip()
            is_luna_message = content.casefold() == "luna" or content.casefold().startswith("luna ")
            prompt = content[5:].strip() if content.casefold().startswith("luna ") else ""
            if is_luna_message:
                prompt = prompt or "hi"
                if prompt.casefold() == "chat" or prompt.casefold().startswith("chat "):
                    await ctx.reply(
                        "There is no `luna chat` command now—just write what you want to ask, "
                        "for example `luna how to study`.",
                        mention_author=False,
                    )
                    return
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
                    except (
                        DictionaryUnavailable,
                        DefinitionNotFound,
                        aiohttp.ClientError,
                        TimeoutError,
                    ):
                        pass
                await ctx.reply(await generate_luna_chat_reply(prompt), mention_author=False)
                return
            await ctx.reply("I don't know that command. Try `luna help`.", mention_author=False)
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"Missing `{error.param.name}`. Try `luna help` for usage.", mention_author=False)
            return
        if isinstance(error, commands.TooManyArguments):
            if ctx.command and ctx.command.name in {"riddle", "messed", "jumbled", "memo"}:
                await ctx.reply(
                    "Riddle, Jumbled, and Memo use one fixed mixed round: "
                    "2 Difficult, 3 Moderate, and 5 Easy. Do not add a level.",
                    mention_author=False,
                )
            else:
                await ctx.reply("Too many values. Try `luna help` for usage.", mention_author=False)
            return
        if isinstance(error, commands.BadArgument):
            await ctx.reply("I couldn't understand that value. Try `luna help` for usage.", mention_author=False)
            return
        if isinstance(error, commands.CommandInvokeError):
            print(f"Command {ctx.command} failed: {error.original!r}")
            await ctx.reply(
                "That command hit an unexpected error and was safely stopped. Try again in a moment.",
                mention_author=False,
            )
            return
        raise error


class LunaCog(commands.Cog):
    def __init__(self, bot: DiscordLuna) -> None:
        self.bot = bot
        self._cherrywords_help_cache: dict[str, str] = {}
        self._last_ai_diagnostic = ""

    async def _difficulty(self, ctx: commands.Context, value: str) -> str | None:
        difficulty = parse_difficulty(value)
        if difficulty is None:
            await ctx.reply(
                "Choose a flower level: 🌱 Easy, 🌼 Moderate, or 🌺 Difficult.",
                mention_author=False,
            )
            return None
        return difficulty

    async def _send_help_pages(self, ctx: commands.Context, pages: list[str]) -> None:
        view = HelpPaginator(pages, ctx.author.id)
        view.message = await ctx.reply(
            view.current_page,
            view=view,
            mention_author=False,
        )

    async def _generation_unavailable(self, ctx: commands.Context, content_name: str) -> None:
        """Tell the player when fresh AI content could not be generated."""
        diagnostic = (
            f"\n_AI diagnostic: {self._last_ai_diagnostic}_"
            if self._last_ai_diagnostic
            else ""
        )
        await ctx.reply(
            f"🌙 I'm having trouble generating fresh {content_name} right now. "
            f"Please try again later.{diagnostic}",
            mention_author=False,
        )

    async def _ai_json(
        self,
        ctx: commands.Context,
        prompt: str,
        max_tokens: int = 900,
        model: str | None = None,
        fallback_model: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> Any | None:
        """Generate JSON from the configured model; callers decide how to fail closed."""
        key = os.environ.get("LUNA_API_KEY", "")
        if not key:
            self._last_ai_diagnostic = "LUNA_API_KEY is missing"
            return None
        primary_model = model or os.environ.get("LUNA_MODEL") or DEFAULT_OSS_MODEL
        selected_fallback_model = (
            fallback_model or os.environ.get("LUNA_FALLBACK_MODEL") or DEFAULT_FALLBACK_MODEL
        )
        selected_response_format = response_format or {"type": "json_object"}
        try:
            async with ctx.typing():
                text = await call_llm(
                    os.environ.get("LUNA_API_URL"),
                    key,
                    prompt,
                    model=primary_model,
                    system_prompt=GAME_GENERATOR_PERSONA,
                    max_tokens=max_tokens,
                    fallback_model=selected_fallback_model,
                    response_format=selected_response_format,
                )
        except (RuntimeError, ValueError, aiohttp.ClientError, TimeoutError) as exc:
            print(f"[ai] JSON generation failed: {type(exc).__name__}: {str(exc)[:500]}")
            status_match = re.search(r"HTTP (\d{3})", str(exc))
            self._last_ai_diagnostic = (
                f"Groq HTTP {status_match.group(1)}"
                if status_match
                else f"{type(exc).__name__} from AI provider"
            )
            return None
        parsed = parse_ai_json(text)
        if parsed is None and selected_fallback_model != primary_model:
            print(
                f"[ai] JSON was malformed from {primary_model}; retrying with "
                f"{selected_fallback_model}."
            )
            try:
                text = await call_llm(
                    os.environ.get("LUNA_API_URL"),
                    key,
                    prompt,
                    model=selected_fallback_model,
                    system_prompt=GAME_GENERATOR_PERSONA,
                    max_tokens=max_tokens,
                    fallback_model=selected_fallback_model,
                    response_format=selected_response_format,
                )
                parsed = parse_ai_json(text)
            except (RuntimeError, ValueError, aiohttp.ClientError, TimeoutError) as exc:
                print(
                    f"[ai] fallback JSON generation failed: {type(exc).__name__}: "
                    f"{str(exc)[:500]}"
                )
                status_match = re.search(r"HTTP (\d{3})", str(exc))
                self._last_ai_diagnostic = (
                    f"Groq fallback HTTP {status_match.group(1)}"
                    if status_match
                    else f"fallback {type(exc).__name__} from AI provider"
                )
        if parsed is None:
            self._last_ai_diagnostic = "AI returned invalid JSON"
            print(
                f"[ai] JSON response was not parseable ({len(text)} chars): "
                f"{text[:300]!r}"
            )
        else:
            self._last_ai_diagnostic = ""
        return parsed

    async def _mcq_content(
        self,
        ctx: commands.Context,
        game_type: str,
        difficulty: str,
        target: int = 5,
    ) -> list[dict[str, Any]]:
        focus = {
            "wordquiz": "English vocabulary meanings and usage",
            "trivia": (
                "a balanced mix of geography, history, general knowledge, countries, "
                "world facts, and basic everyday facts. Spread the questions across "
                "those categories instead of concentrating on one subject"
            ),
        }[game_type]
        payload = await self._ai_json(
            ctx,
            f"Create exactly {target} unique {difficulty}-level multiple-choice questions about {focus}. "
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
            if len(generated) == target:
                break
        if len(generated) < target:
            print(
                f"[{game_type}] AI supplied {len(generated)}/{target} fresh questions; "
                "game not started (no static fallback)."
            )
            return []
        random.shuffle(generated)
        return generated

    async def _jumbled_content(
        self,
        ctx: commands.Context,
        difficulty: str,
        target: int = JUMBLE_BANK_SIZE,
    ) -> list[dict[str, Any]]:
        """Build a complete fresh AI-only jumble bank; never reuse static words."""
        if target <= 0:
            return []
        if not os.environ.get("LUNA_API_KEY"):
            print("[messed] LUNA_API_KEY is unavailable; game not started (no static fallback).")
            return []

        generated: list[dict[str, Any]] = []
        seen_words: set[str] = set()
        no_progress_attempts = 0
        for _ in range(JUMBLE_MAX_API_ATTEMPTS):
            if len(generated) >= target:
                break
            before = len(generated)
            batch_size = min(JUMBLE_BATCH_SIZE, target - len(generated))
            avoid = ", ".join(sorted(seen_words)) or "none"
            payload = await self._ai_json(
                ctx,
                f"Create exactly {batch_size} original {difficulty}-level English word-jumble "
                "challenges. Return minified JSON only in this shape: "
                "{\"words\":[{\"word\":\"single word\",\"definition\":\"short definition\"}]}. "
                "Use single alphabetic words from 4 to 16 letters. Definitions must not contain "
                "the answer. Every word must be different, must be a real English word, and must "
                f"not reuse these words: {avoid}.",
                max_tokens=4096,
            )
            values = payload.get("words", []) if isinstance(payload, dict) else []
            for value in values:
                if not isinstance(value, dict):
                    continue
                word = re.sub(r"[^a-z]", "", str(value.get("word", "")).casefold())
                definition = " ".join(str(value.get("definition", "")).split())
                item = {"word": word, "definition": definition, "difficulty": difficulty}
                if (
                    re.fullmatch(r"[a-z]{4,16}", word)
                    and len(definition) >= 12
                    and word not in definition.casefold()
                    and word not in seen_words
                    and content_rotation.remember_generated(f"ai:jumble:{difficulty}", item)
                ):
                    generated.append(item)
                    seen_words.add(word)
                if len(generated) >= target:
                    break
            if len(generated) == before:
                no_progress_attempts += 1
                if no_progress_attempts >= 2:
                    break
            else:
                no_progress_attempts = 0

        if len(generated) < target:
            print(
                f"[messed] AI supplied {len(generated)}/{target} fresh words; "
                "game not started (no static fallback)."
            )
            return []
        random.shuffle(generated)
        return generated

    async def _jumbled_round_content(self, ctx: commands.Context) -> list[dict[str, Any]]:
        """Generate one complete ten-word bank with the fixed level mix."""
        generated: list[dict[str, Any]] = []
        for difficulty, target in DIFFICULTY_COUNTS.items():
            values = await self._jumbled_content(ctx, difficulty, target=target)
            if len(values) != target:
                print(
                    f"[messed] Mixed round needs {target} {difficulty} words; "
                    f"received {len(values)}."
                )
                return []
            generated.extend(values)
        random.shuffle(generated)
        return generated

    async def _riddle_content(
        self,
        ctx: commands.Context,
        difficulty: str,
    ) -> dict[str, Any]:
        """Keep the old single-item helper available to callers/tests."""
        values = await self._riddle_content_pool(ctx, difficulty, target=RIDDLE_BANK_SIZE)
        return values[0] if values else {}

    async def _riddle_content_pool(
        self,
        ctx: commands.Context,
        difficulty: str,
        target: int = RIDDLE_BANK_SIZE,
    ) -> list[dict[str, Any]]:
        """Generate a complete AI-only riddle bank without reusing static riddles."""
        if target <= 0:
            return []

        api_enabled = bool(os.environ.get("LUNA_API_KEY"))
        if not api_enabled:
            print(
                f"[riddle] LUNA_API_KEY is unavailable for {difficulty}; "
                "game not started (no static fallback)."
            )
            return []

        generated: list[dict[str, Any]] = []
        seen_riddle_fingerprints: set[str] = set()
        seen_answers: set[str] = set()
        attempts = 0
        no_progress_attempts = 0
        max_attempts = max(RIDDLE_MAX_API_ATTEMPTS, (target // RIDDLE_BATCH_SIZE) + 3)
        while api_enabled and len(generated) < target and attempts < max_attempts:
            attempts += 1
            generated_before_attempt = len(generated)
            batch_size = min(RIDDLE_BATCH_SIZE, target - len(generated))
            previous_answers = {
                str(item["answer"]).casefold()
                for item in generated
            }
            avoid = ", ".join(sorted(previous_answers)) or "none"
            payload = await self._ai_json(
                ctx,
                f"Create exactly {batch_size} original {difficulty}-level wordplay riddles. "
                "Return minified JSON only in this shape: "
                "{\"riddles\":[{\"riddle\":\"question\",\"answer\":\"short answer\","
                "\"accepted_answers\":[\"optional variant\"],\"explanation\":\"why it fits\"}]}. "
                "Every riddle must be self-contained, have one unambiguous answer, and be "
                "different from the others. Do not use classic stock riddles, do not include "
                "the answer in the question, and do not repeat these answers: "
                f"{avoid}.",
                max_tokens=4096,
            )
            if payload is None:
                print(
                    f"[riddle] AI generation failed for {difficulty} after "
                    f"{len(generated)}/{target} fresh riddles; game not started "
                    "(no static fallback)."
                )
                return []
            values = payload.get("riddles", []) if isinstance(payload, dict) else []
            if not values and isinstance(payload, dict) and payload.get("riddle"):
                values = [payload]
            for value in values:
                if not isinstance(value, dict):
                    continue
                riddle = " ".join(str(value.get("riddle", "")).split())
                answer = " ".join(str(value.get("answer", "")).split())
                explanation = " ".join(str(value.get("explanation", "")).split())
                answer_fingerprint = " ".join(answer.casefold().split())
                if (
                    not riddle
                    or not answer
                    or not explanation
                    or len(answer) > 50
                    or answer.casefold() in riddle.casefold()
                    or answer_fingerprint in seen_answers
                ):
                    continue
                accepted = value.get("accepted_answers", [])
                item = {
                    "riddle": riddle,
                    "answer": answer,
                    "accepted_answers": (
                        [entry for entry in accepted if isinstance(entry, str) and entry.strip()]
                        if isinstance(accepted, list) else []
                    ),
                    "explanation": explanation,
                    "difficulty": difficulty,
                }
                fingerprint = " ".join(riddle.casefold().split())
                if (
                    fingerprint not in seen_riddle_fingerprints
                    and content_rotation.remember_generated(f"ai:riddle:{difficulty}", item)
                ):
                    generated.append(item)
                    seen_riddle_fingerprints.add(fingerprint)
                    seen_answers.add(answer_fingerprint)
                if len(generated) == target:
                    break

            if len(generated) == generated_before_attempt:
                no_progress_attempts += 1
                if no_progress_attempts >= 3:
                    break
            else:
                no_progress_attempts = 0

        if api_enabled and len(generated) < target:
            print(
                f"[riddle] AI supplied {len(generated)}/{target} valid {difficulty} riddles; "
                "game not started (no static fallback)."
            )
        if len(generated) < target:
            return []
        random.shuffle(generated)
        return generated

    async def _riddle_round_content(self, ctx: commands.Context) -> list[dict[str, Any]]:
        """Generate one complete ten-riddle bank with the fixed level mix."""
        generated: list[dict[str, Any]] = []
        for difficulty, target in DIFFICULTY_COUNTS.items():
            values = await self._riddle_content_pool(ctx, difficulty, target=target)
            if len(values) != target:
                print(
                    f"[riddle] Mixed round needs {target} {difficulty} riddles; "
                    f"received {len(values)}."
                )
                return []
            generated.extend(values)
        random.shuffle(generated)
        return generated

    async def _escape_content(self, ctx: commands.Context, difficulty: str) -> dict[str, Any] | None:
        # Rotate the requested theme as well as the final puzzle. This keeps
        # deterministic model output from producing the same room each time.
        theme = content_rotation.take(
            f"escape:themes:{difficulty}",
            ESCAPE_PUZZLES,
            fingerprint=lambda puzzle: str(puzzle["title"]),
        )[0]
        payload = await self._ai_json(
            ctx,
            f"Create one original interactive {difficulty}-level educational escape-room puzzle. "
            f"Use this room theme as inspiration, but make the puzzle and wording distinct: {theme['title']}. "
            "Return a JSON object with: title, scene, items (object of 3-5 lowercase item names "
            "to descriptions), clue_item, key_item, clues (object with easy, medium, hard), "
            "answer (one short word or code), success, and learning_note. clue_item and key_item "
            "must exactly match keys in items. The clue must logically determine the answer. "
            "Do not reuse the title, answer, or central puzzle from any previous room.",
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
        # A local rotating bank guarantees that Escape still offers a new
        # playable room when the provider repeats or cannot generate JSON.
        fallback = content_rotation.take(
            f"escape:fallback:{difficulty}",
            ESCAPE_PUZZLES,
            fingerprint=lambda puzzle: str(puzzle["title"]),
        )[0]
        print(f"[escape] using rotating local {difficulty} puzzle fallback")
        return fallback

    async def _garden_content(self, ctx: commands.Context, difficulty: str) -> list[dict[str, Any]]:
        question_types = (
            "multiple_choice",
            "fill_blank",
            "true_false",
            "sentence_creation",
            "correction",
        )
        result: list[dict[str, Any]] = []
        attempts = 0
        no_progress_attempts = 0
        validation_rejections = 0
        api_model = os.environ.get("LUNA_CHERRYGARDEN_MODEL") or DEFAULT_CHERRYGARDEN_MODEL
        api_fallback_model = (
            os.environ.get("LUNA_CHERRYGARDEN_FALLBACK_MODEL")
            or DEFAULT_CHERRYGARDEN_FALLBACK_MODEL
        )
        print(
            f"[cherrygarden] requesting fresh AI questions with {api_model}; "
            f"fallback {api_fallback_model}"
        )

        while len(result) < 10 and attempts < CHERRYGARDEN_MAX_API_ATTEMPTS:
            attempts += 1
            batch_size = min(CHERRYGARDEN_BATCH_SIZE, 10 - len(result))
            counts = {question_type: 0 for question_type in question_types}
            for question in result:
                counts[question["question_type"]] += 1
            requested_types = [
                question_type
                for question_type in question_types
                if counts[question_type] < 2
            ]
            requested_types = requested_types[:batch_size]
            avoid = "; ".join(
                f"{question['question_type']}: {question['prompt']}" for question in result
            ) or "none"
            payload = await self._ai_json(
                ctx,
                f"Create exactly {batch_size} original {difficulty}-level English grammar questions. "
                f"Use these question types, one per type in this batch: {', '.join(requested_types)}. "
                "Return JSON only in this shape: {\"questions\":[{\"topic\":str,"
                "\"question_type\":str,\"prompt\":str,\"answers\":[accepted strings],"
                "\"model_answer\":str,\"explanation\":str,"
                "\"options\":[4 strings for multiple_choice],"
                "\"required_words\":[str for sentence_creation],\"min_words\":number}]}. "
                "For every question include all fields required by its type. Explanations must "
                "briefly say why the correct form works and why a likely wrong form fails. "
                "Keep every answer unambiguous and do not repeat these existing prompts: "
                f"{avoid}",
                max_tokens=2600,
                model=api_model,
                fallback_model=api_fallback_model,
                response_format={"type": "json_object"},
            )
            values = payload.get("questions", []) if isinstance(payload, dict) else []
            before = len(result)
            if not isinstance(values, list):
                values = []
            for value in values:
                if not isinstance(value, dict) or not valid_garden_question(value):
                    validation_rejections += 1
                    continue
                if value["question_type"] not in question_types:
                    validation_rejections += 1
                    continue
                counts[value["question_type"]] += 1
                if counts[value["question_type"]] > 2:
                    validation_rejections += 1
                    counts[value["question_type"]] -= 1
                    continue
                if content_rotation.remember_generated(f"ai:garden:{difficulty}", value):
                    result.append(value)
                else:
                    validation_rejections += 1
                if len(result) == 10:
                    break
            if len(result) == before:
                no_progress_attempts += 1
            else:
                no_progress_attempts = 0
            if no_progress_attempts >= 2 and len(result) < 10:
                print(
                    f"[cherrygarden] AI made no validation progress in {no_progress_attempts} "
                    f"batches; {validation_rejections} values rejected so far."
                )
                break

        expected_types = {
            "multiple_choice", "fill_blank", "true_false", "sentence_creation", "correction"
        }
        if len(result) != 10 or any(
            sum(item["question_type"] == question_type for item in result) != 2
            for question_type in expected_types
        ):
            self._last_ai_diagnostic = (
                f"AI validation produced {len(result)}/10 usable questions"
            )
            print(
                f"[cherrygarden] AI supplied {len(result)}/10 valid questions after "
                f"{attempts} batches; {validation_rejections} values rejected."
            )
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
        print(
            f"[storyteller] AI did not supply a fresh {difficulty} opening; "
            "game not started (no static fallback)."
        )
        return None

    async def _cherryword_sequences(self, ctx: commands.Context, difficulty: str) -> list[str]:
        sequences: list[str] = []
        attempts = 0
        no_progress_attempts = 0
        validation_rejections = 0
        api_model = os.environ.get("LUNA_CHERRYWORDS_MODEL") or DEFAULT_CHERRYWORDS_MODEL
        api_fallback_model = (
            os.environ.get("LUNA_CHERRYWORDS_FALLBACK_MODEL")
            or DEFAULT_CHERRYWORDS_FALLBACK_MODEL
        )
        print(
            f"[cherrywords] requesting fresh AI sequences with {api_model}; "
            f"fallback {api_fallback_model}"
        )

        while len(sequences) < 30 and attempts < CHERRYWORDS_MAX_API_ATTEMPTS:
            attempts += 1
            batch_size = min(CHERRYWORDS_BATCH_SIZE, 30 - len(sequences))
            avoid = ", ".join(sequences) or "none"
            payload = await self._ai_json(
                ctx,
                f"Create exactly {batch_size} fresh CherryWords prompts for a {difficulty}-level "
                "English word game. Each prompt must be exactly 3 lowercase letters that appear "
                "consecutively inside at least one longer real English word. Easy should be common, "
                "medium less obvious, and hard uncommon but solvable. Every example must be a single "
                "alphabetic word longer than 3 letters and must contain the prompt as a contiguous "
                "substring. Do not repeat any prompt from this list: "
                f"{avoid}. Return only the requested JSON object.",
                max_tokens=1600,
                model=api_model,
                fallback_model=api_fallback_model,
                response_format=CHERRYWORDS_RESPONSE_FORMAT,
            )
            values = payload.get("sequences", []) if isinstance(payload, dict) else []
            before = len(sequences)
            if not isinstance(values, list):
                values = []

            for value in values:
                if not isinstance(value, dict):
                    validation_rejections += 1
                    continue
                letters = "".join(
                    ch for ch in str(value.get("letters", "")).casefold() if ch.isalpha()
                )
                examples = value.get("examples")
                valid_examples = (
                    isinstance(examples, list)
                    and any(
                        isinstance(example, str)
                        and example.strip().isalpha()
                        and len(example.strip()) > len(letters)
                        and letters in example.strip().casefold()
                        for example in examples
                    )
                )
                if (
                    len(letters) != 3
                    or not valid_examples
                    or letters in sequences
                    or not content_rotation.remember_generated(
                        f"ai:cherrywords:{difficulty}", {"letters": letters}
                    )
                ):
                    validation_rejections += 1
                    continue
                sequences.append(letters)
                if len(sequences) == 30:
                    break

            if len(sequences) == before:
                no_progress_attempts += 1
            else:
                no_progress_attempts = 0
            if no_progress_attempts >= 2 and len(sequences) < 30:
                print(
                    f"[cherrywords] AI made no validation progress in {no_progress_attempts} "
                    f"batches; {validation_rejections} values rejected so far."
                )
                break

        ai_count = len(sequences)
        if ai_count < 30 and os.environ.get(
            "LUNA_CHERRYWORDS_ALLOW_STATIC_FALLBACK", ""
        ).casefold() not in {"1", "true", "yes", "on"}:
            self._last_ai_diagnostic = f"AI validation produced {ai_count}/30 usable sequences"
            print(
                f"[cherrywords] AI supplied {ai_count}/30 after {attempts} batches; "
                f"{validation_rejections} values rejected. Static fallback is disabled."
            )
            return []
        if ai_count < 30:
            # Emergency-only mode. Normal gameplay must use fresh AI prompts.
            fallback_pool = list(
                dict.fromkeys(
                    sequence
                    for sequence in CHERRYWORDS_FALLBACK_SEQUENCES
                    if sequence not in sequences
                )
            )
            sequences.extend(
                content_rotation.take(
                    f"fallback:cherrywords:{difficulty}",
                    fallback_pool,
                    count=30 - ai_count,
                    fingerprint=lambda sequence: sequence,
                )
            )
        if len(sequences) < 30:
            print(
                f"[cherrywords] AI supplied {ai_count}/30 and emergency fallback only "
                f"provided {len(sequences)}/30; game not started."
            )
            return []
        if ai_count < 30:
            print(
                f"[cherrywords] AI supplied {ai_count}/30; emergency static fallback "
                f"filled {30 - ai_count}."
            )
        random.shuffle(sequences)
        return sequences

    async def _cherrywords_help(self, ctx: commands.Context, sequence: str) -> str:
        letters = "".join(ch for ch in sequence.casefold() if ch.isalpha())
        if not 2 <= len(letters) <= 12:
            return "Use `luna cherrywords help <letters>` with 2–12 letters, for example `ALG`."
        if letters in self._cherrywords_help_cache:
            return self._cherrywords_help_cache[letters]

        examples: list[tuple[str, str]] = []
        seen: set[str] = set()

        def add_example(raw_word: Any, raw_meaning: Any) -> None:
            word = "".join(ch for ch in str(raw_word).casefold() if ch.isalpha())
            meaning = " ".join(str(raw_meaning).split())
            if (
                len(word) > len(letters)
                and letters in word
                and word not in seen
                and 4 <= len(word) <= 24
                and 8 <= len(meaning) <= 120
            ):
                examples.append((word, meaning))
                seen.add(word)

        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "https://api.datamuse.com/words",
                    params={"sp": f"*{letters}*", "md": "d", "max": 40},
                    headers={"User-Agent": "LunaBot/1.0"},
                ) as response:
                    if response.status == 200:
                        values = await response.json(content_type=None)
                    else:
                        values = []
        except (aiohttp.ClientError, TimeoutError, ValueError):
            values = []

        for value in values if isinstance(values, list) else []:
            if not isinstance(value, dict):
                continue
            definitions = value.get("defs") or []
            meaning = ""
            for definition in definitions:
                candidate = str(definition).split("\t", 1)[-1].strip()
                if candidate:
                    meaning = candidate
                    break
            if meaning:
                add_example(value.get("word", ""), meaning)
            if len(examples) == 7:
                break

        if examples:
            lines = [
                f"CherryWords help: **{letters.upper()}**",
                "Dictionary words containing that exact sequence:",
            ]
            lines.extend(f"- **{word}** - {meaning}" for word, meaning in examples)
            result = "\n".join(lines)
            self._cherrywords_help_cache[letters] = result
            return result

        return_value = (
            f"CherryWords help: **{letters.upper()}**\n"
            "No dictionary words were found containing that exact sequence."
        )
        self._cherrywords_help_cache[letters] = return_value
        return return_value

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
            lobby_message = await ctx.reply(
                f"🌸 **{game_type.replace('_', ' ').title()} lobby created!**\n"
                f"**What this game is:** {GAME_DESCRIPTIONS.get(game_type, game.description)}\n"
                f"**Example:** {details.get('example', 'Follow Luna’s prompt when the game begins.')}\n"
                f"React ✅ or use `luna join`. Host <@{ctx.author.id}> starts it with `luna begin`.",
                mention_author=False,
            )
            session.state["lobby_message_id"] = lobby_message.id
            try:
                await lobby_message.add_reaction("✅")
            except (discord.HTTPException, discord.Forbidden):
                pass
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
        if session and not session.state.get("lobby"):
            if ctx.author.id == session.state.get("host_id"):
                await ctx.reply("This game has already begun.", mention_author=False)
            return
        if not session:
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
        if session.state.get("beginning"):
            return
        session.state["beginning"] = True
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

    @commands.command(name="hint", aliases=["hints"])
    async def hint(self, ctx: commands.Context) -> None:
        session = self.bot.game_manager.get_session(ctx.channel.id)
        if not session or session.game_type != "riddle" or session.state.get("lobby"):
            await ctx.reply("Hints are available after a riddle game begins.", mention_author=False)
            return
        game = self.bot.game_manager.get_game("riddle")
        if game is None:
            await ctx.reply("The riddle game is not configured right now.", mention_author=False)
            return
        if not session.is_player_valid(ctx.author.id):
            await ctx.reply("Only players in the riddle can use its hints.", mention_author=False)
            return
        session.update_activity()
        await game.handle_hint(session, ctx)

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
                "`luna help <game name>`—for example, `luna help wordle`.",
                mention_author=False,
            )
            return

        def game_help(name: str) -> str:
            details = GAME_HELP[name]
            return (
                f"**`{details['command']}`**\n"
                f"**Players:** {details['players']}\n"
                f"{GAME_DESCRIPTIONS[name]}"
            )

        pages = [
            "\n".join(
                [
                    "**Luna Help — Commands & Learning Games** 🌙🌸",
                    "**Choose one flower level for games that support it (default: 🌱):**",
                    "🌱 **Easy** — gentle questions and clearer clues",
                    "🌼 **Moderate** — more thinking and richer language",
                    "🌺 **Difficult** — advanced questions and fewer hints",
                    "Use the flower directly, for example: `luna escape 🌼` or `luna trivia 🌺`.",
                    "Riddle, Jumbled, and Memo use a fixed 10-item mixed round: 2 Difficult, 3 Moderate, and 5 Easy.",
                    "Those three commands do not take a flower level; other games still accept one.",
                    "",
                    game_help("wordquiz"),
                    "",
                    game_help("riddle"),
                    "",
                    game_help("messed"),
                    "",
                    game_help("memo"),
                ]
            ),
            "\n\n".join(
                [
                    game_help("escape"),
                    game_help("trivia"),
                    game_help("storyteller"),
                    game_help("cherrygarden"),
                    game_help("cherrywords"),
                    game_help("wordle"),
                ]
            ),
            "\n\n".join(
                [
                    game_help("codenames"),
                    "**Multiplayer:** create the game → others use `luna join` → host uses `luna begin`.",
                    "**Game controls:** `luna join`, `luna begin` (`start`), `luna score` (`scores`), `luna stop` (`endgame`, `cancelgame`).",
                    "**Riddle hint:** During a riddle, type `hint` or `luna hint` (two hints maximum).",
                    "**Detailed rules:** `luna help <game>`; examples: `luna help wordle`, `luna help escape`.",
                    "**Game list shortcut:** `luna game` or `luna games`.",
                    "**Utilities:**",
                    "`luna about`— Luna’s personality.",
                    "`luna bday <name>` (`birthday`) — make a looping animated GIF signed by you and Luna.",
                    "`luna meaning <word>` — dictionary definition.",
                    "`luna spell <word>` — spelling and pronunciation help.",
                    "`luna quote`, `luna joke`, `luna fact` — short generated content.",
                    "`luna search <topic>` — dictionary, word, or topic search.",
                    "`luna story <theme>` — generate a short story.",
                ]
            ),
        ]
        await self._send_help_pages(ctx, pages)

    @commands.command(name="game", aliases=["games"])
    async def game_list(self, ctx: commands.Context) -> None:
        help_command = self.bot.get_command("help")
        if help_command:
            await ctx.invoke(help_command, topic="games")

    @commands.command(name="wordquiz", aliases=["trio"])
    async def wordquiz(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is None:
            return
        questions = await self._mcq_content(ctx, "wordquiz", difficulty)
        if not questions:
            await self._generation_unavailable(ctx, "Word Quiz questions")
            return
        await self._create_game(ctx, "wordquiz", {"questions": questions, "difficulty": difficulty})

    @commands.command(name="jumbled", aliases=["messed", "jumble", "anagram"])
    async def jumble(self, ctx: commands.Context) -> None:
        words = await self._jumbled_round_content(ctx)
        if not words:
            await self._generation_unavailable(ctx, "Jumbled word challenges")
            return
        await self._create_game(ctx, "messed", {"words": words})

    @commands.command(name="memo", aliases=["memory", "memorymatch", "emojimemory"])
    async def memory(self, ctx: commands.Context) -> None:
        await self._create_game(ctx, "memo", {})

    @commands.command(name="trivia")
    async def trivia(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is None:
            return
        questions = await self._mcq_content(ctx, "trivia", difficulty)
        if not questions:
            await self._generation_unavailable(ctx, "Trivia questions")
            return
        await self._create_game(ctx, "trivia", {"questions": questions, "difficulty": difficulty})

    @commands.command(name="wordle")
    async def wordle(self, ctx: commands.Context) -> None:
        await self._create_game(ctx, "wordle", {})

    @commands.command(name="riddle")
    async def riddle(self, ctx: commands.Context) -> None:
        riddle_pool = await self._riddle_round_content(ctx)
        if not riddle_pool:
            await self._generation_unavailable(ctx, "riddles")
            return
        random.shuffle(riddle_pool)
        state = dict(riddle_pool[0], riddle_pool=riddle_pool[1:])
        await self._create_game(ctx, "riddle", state)

    @commands.command(name="escape", aliases=["escaperoom"])
    async def escape(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is not None:
            puzzle = await self._escape_content(ctx, difficulty)
            if not puzzle:
                await self._generation_unavailable(ctx, "an Escape Room puzzle")
                return
            await self._create_game(
                ctx, "escape", {"difficulty": difficulty, "puzzle": puzzle}
            )

    @commands.command(name="storyteller")
    async def storyteller(self, ctx: commands.Context, difficulty: str = "easy") -> None:
        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is not None:
            opening = await self._story_content(ctx, difficulty)
            if not opening:
                await self._generation_unavailable(ctx, "a Storyteller opening")
                return
            await self._create_game(
                ctx,
                "storyteller",
                {"difficulty": difficulty, "opening_prompt": opening},
            )

    @commands.command(name="cherrygarden")
    async def cherry_garden(self, ctx: commands.Context, mode: str = "easy") -> None:
        mode = await self._difficulty(ctx, mode)
        if mode is None:
            return
        questions = await self._garden_content(ctx, mode)
        if len(questions) < 10:
            print("[cherrygarden] No complete fresh question bank; game not started.")
            await self._generation_unavailable(ctx, "CherryGarden questions")
            return
        await self._create_game(
            ctx,
            "cherrygarden",
            {"mode": mode, "questions": questions},
        )

    @commands.command(name="cherrywords", aliases=["arena"])
    async def cherry_words(
        self,
        ctx: commands.Context,
        difficulty: str = "easy",
        *,
        options: str = "",
    ) -> None:
        meaning_tokens = {"meaning", "meanings", "(meaning)", "(meanings)", "define", "definitions"}
        help_tokens = {"help", "hint", "hints", "search", "words"}
        timeless_tokens = {"timeless", "practice", "kid", "kids", "notime", "lifeless"}
        no_time_phrases = {"no time", "no timer", "without time", "without timer"}
        requested = difficulty.casefold().strip("'\"")
        if requested in help_tokens:
            if not options:
                await ctx.reply(
                    "Use `luna cherrywords help <letters>` — example: `luna cherrywords help ALG`.",
                    mention_author=False,
                )
                return
            await ctx.reply(await self._cherrywords_help(ctx, options), mention_author=False)
            return

        option_text = options.casefold().strip("'\"")
        option_tokens = [item.strip("'\"(),") for item in option_text.split()]
        if requested in meaning_tokens and not option_tokens:
            difficulty, option_tokens = "easy", [requested]
        if requested in timeless_tokens and not option_tokens:
            difficulty, option_tokens = "easy", [requested]

        difficulty = await self._difficulty(ctx, difficulty)
        if difficulty is not None:
            show_meanings = any(token in meaning_tokens for token in option_tokens)
            has_no_time_phrase = any(phrase in option_text for phrase in no_time_phrases)
            timeless = (
                any(token in timeless_tokens for token in option_tokens)
                or has_no_time_phrase
            )
            round_seconds = None
            if not has_no_time_phrase and ("time" in option_tokens or "timer" in option_tokens):
                timer_index = next(
                    index for index, token in enumerate(option_tokens)
                    if token in {"time", "timer"}
                )
                if timer_index + 1 >= len(option_tokens) or not option_tokens[timer_index + 1].isdigit():
                    await ctx.reply(
                        "Use seconds only, like `luna cherrywords medium time 5 seconds`.",
                        mention_author=False,
                    )
                    return
                if timer_index + 2 < len(option_tokens):
                    unit = option_tokens[timer_index + 2]
                    if unit not in {"second", "seconds", "sec", "secs", "s"}:
                        await ctx.reply(
                            "CherryWords timer accepts seconds only.",
                            mention_author=False,
                        )
                        return
                round_seconds = int(option_tokens[timer_index + 1])
                if not 3 <= round_seconds <= 60:
                    await ctx.reply(
                        "CherryWords timer must be between 3 and 60 seconds.",
                        mention_author=False,
                    )
                    return
                timeless = False

            extra_sequences = await self._cherryword_sequences(ctx, difficulty)
            if len(extra_sequences) < 30:
                await self._generation_unavailable(ctx, "CherryWords prompts")
                return
            await self._create_game(
                ctx,
                "cherrywords",
                {
                    "difficulty": difficulty,
                    "show_meanings": show_meanings,
                    "round_seconds": round_seconds,
                    "timeless": timeless,
                    "extra_sequences": extra_sequences,
                },
            )

    async def _codenames_ai_board(self, ctx: commands.Context, difficulty: str) -> dict[str, Any] | None:
        assassin_count = 2 if difficulty == "hard" else 1
        payload = await self._ai_json(
            ctx,
            "Return minified JSON only. Build a fresh 20-card Codenames learning board. "
            f"Difficulty: {difficulty}. "
            "Schema: {\"theme\":str,\"team_a_clues\":[{\"clue\":str,\"cards\":[str,str,str,str],"
            "\"teaching\":str},{\"clue\":str,\"cards\":[str,str,str,str],\"teaching\":str}],"
            "\"cards\":[{\"word\":str,\"role\":\"A|B|neutral|assassin\",\"category\":str,"
            "\"definition\":str}]}. "
            f"Counts: 8 A, 8 B, {3 if assassin_count == 1 else 2} neutral, {assassin_count} assassin. "
            "Words: unique, single alphabetic token, 3-18 letters. Definitions: 5-12 words. "
            "Two clues must each point to exactly 4 A cards. Clues must not equal, contain, "
            "or appear inside any board word. Clues must be specific, vivid connectors; never use "
            "generic category clues like SCIENTIFIC, TECHNICAL, NATURAL, KNOWLEDGE, TERMS, or WORDS. "
            "Use diverse advanced terms from British/American "
            "English, music, history, civics, biology, geography, astrology, biophysics, "
            "networking, politics, philosophy, psychology, zoomusicology, magic, taboos, "
            "software, royal-era terms, and extinct organisms. Avoid MOON STAR BOOK CLASS SONG TIGER FOOD.",
            max_tokens=4096,
        )
        validated = validate_ai_codenames_board(payload, assassin_count)
        if not validated:
            print(
                f"[codenames] AI did not supply a fresh valid {difficulty} board; "
                "game not started (no static fallback)."
            )
            return None
        word_key = " ".join(sorted(card["word"] for card in validated["board"]))
        if not content_rotation.remember_generated(
            f"ai:codenames:{difficulty}", {"title": word_key}
        ):
            print(
                f"[codenames] AI repeated a previous {difficulty} board; "
                "game not started (no static fallback)."
            )
            return None
        return validated

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
        ai_board = await self._codenames_ai_board(ctx, difficulty)
        if not ai_board:
            await self._generation_unavailable(ctx, "a Codenames board")
            return
        state: dict[str, Any] = {"play_mode": mode, "difficulty": difficulty}
        state["ai_codenames_board"] = ai_board
        await self._create_game(
            ctx,
            "codenames",
            state,
            lobby=(mode == "multi"),
        )

    @commands.command(name="about", aliases=["personality", "whoareyou"])
    async def about(self, ctx: commands.Context) -> None:
        await ctx.reply(luna_about_text(), mention_author=False)

    @commands.command(name="bday", aliases=["birthday"])
    async def birthday(self, ctx: commands.Context, *, person: str) -> None:
        name = clean_birthday_name(person)
        if not name:
            await ctx.reply(
                "Whose birthday is it? Try `luna bday Cherry`.",
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        wish = birthday_wish(name)
        from_name = clean_birthday_name(
            getattr(ctx.author, "display_name", None)
            or getattr(ctx.author, "name", None)
            or "a friend"
        ) or "a friend"
        caption = birthday_caption(discord.utils.escape_markdown(name), wish, from_name)
        if not BIRTHDAY_IMAGES_AVAILABLE:
            await ctx.reply(
                caption + "\nBirthday images need Pillow installed.",
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        async with ctx.typing():
            card = render_birthday_gif(name, wish, from_name)
        filename_name = re.sub(r"[^a-z0-9_-]+", "_", name.casefold()).strip("_") or "friend"
        await ctx.reply(
            caption,
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
            file=discord.File(card, filename=f"luna_birthday_{filename_name}.gif"),
        )

    @commands.command(name="meaning")
    async def meaning(self, ctx: commands.Context, *, term: str) -> None:
        try:
            result = await fetch_meaning(term.strip())
        except DictionaryUnavailable:
            await ctx.reply(
                "Both dictionary providers are temporarily unavailable. Please try again shortly.",
                mention_author=False,
            )
            return
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
                    prompt
                    + f"\nReturn a complete answer within {max_words} words. "
                    "Never stop mid-sentence or begin a section you cannot finish.",
                    system_prompt=LUNA_PERSONA,
                    max_tokens=min(900, max(140, int(max_words * 2.5))),
                )
            except (RuntimeError, ValueError, aiohttp.ClientError, TimeoutError):
                await ctx.reply("The language model is unavailable right now. Try again later.", mention_author=False)
                return
        formatted = limit_response_words(answer, max_words, compact=max_words <= 100)
        if max_words > 100:
            formatted = trim_incomplete_long_response(formatted)
        chunks = split_discord_message(ensure_emoji(formatted))
        await ctx.reply(chunks[0], mention_author=False)
        for chunk in chunks[1:]:
            await ctx.send(chunk)

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
        query = query.strip()
        if not query:
            await ctx.reply("Search what? Try `luna search gallop`.", mention_author=False)
            return

        containing_letters = extract_containing_letters_query(query)
        if containing_letters:
            response = await self._cherrywords_help(ctx, containing_letters)
            lines = response.splitlines()
            if lines:
                lines[0] = f"🔎 **Words containing {containing_letters.upper()}**"
            if lines and lines[-1] != CHERRY_BLOSSOM:
                lines.append(CHERRY_BLOSSOM)
            await ctx.reply("\n".join(lines), mention_author=False)
            return

        offline_topic = OFFLINE_TOPIC_FACTS.get(query.casefold())
        if offline_topic:
            summary, source = offline_topic
            await ctx.reply(
                f"🔎 **{query.title()}**\n{summary}\n\nSource: {source}\n{CHERRY_BLOSSOM}",
                mention_author=False,
            )
            return

        dictionary_query = extract_definition_target(query) or query
        if looks_like_dictionary_query(dictionary_query):
            result = None
            try:
                async with ctx.typing():
                    wikipedia_url = await fetch_wikipedia_url(dictionary_query)
                    result = await fetch_meaning(dictionary_query)
            except DefinitionNotFound:
                # A one-word search can be a place, country, or other topic;
                # continue to the general search path when it is not a word.
                pass
            except (DictionaryUnavailable, aiohttp.ClientError, TimeoutError):
                # Dictionary providers are optional. A failed dictionary request
                # must not prevent a topic search or AI search from running.
                pass
            if result is not None:
                await ctx.reply(
                    format_search_definition_card(
                        result.get("word", dictionary_query),
                        result,
                        wikipedia_url=wikipedia_url,
                    ),
                    mention_author=False,
                )
                return

        key = os.environ.get("LUNA_API_KEY", "")
        if not key:
            await ctx.reply("AI search needs an LLM key.", mention_author=False)
            return

        wikipedia_url = await fetch_wikipedia_url(query)
        prompt = (
            "Return a concise Discord search card in this exact style:\n"
            "🔎 **Title**\n"
            "Short direct answer.\n\n"
            "**Key points**\n"
            "• point\n"
            "• point\n\n"
            "Source: URL if you know a reliable source, otherwise omit the Source line.\n"
            "No playful persona, no gestures, no jokes, no sign-off. "
            f"Query: {query}\n"
            f"Wikipedia URL if useful: {wikipedia_url or 'none found'}"
        )
        try:
            async with ctx.typing():
                answer = await call_llm(
                    os.environ.get("LUNA_API_URL"),
                    key,
                    prompt,
                    model=os.environ.get("LUNA_MODEL") or DEFAULT_OSS_MODEL,
                    system_prompt="You format concise, factual search results for a Discord bot.",
                    max_tokens=650,
                )
        except (RuntimeError, ValueError, aiohttp.ClientError, TimeoutError):
            await ctx.reply("AI search is unavailable right now. Try again in a moment.", mention_author=False)
            return

        answer = trim_incomplete_long_response(limit_response_words(answer, 320))
        if wikipedia_url and wikipedia_url not in answer:
            answer = f"{answer.rstrip()}\nWikipedia: {wikipedia_url}"
        if not answer.endswith(CHERRY_BLOSSOM):
            answer = f"{answer.rstrip()}\n{CHERRY_BLOSSOM}"
        await ctx.reply(answer, mention_author=False)

    @commands.command(name="story")
    async def story(self, ctx: commands.Context, *, theme: str) -> None:
        await self._llm_reply(
            ctx,
            f"Write a warm short story about: {theme}",
            "Story generation needs an LLM key.",
            max_words=300,
        )

    @commands.command(name="spell")
    async def spell(self, ctx: commands.Context, *, word: str) -> None:
        await self._llm_reply(
            ctx,
            f"Explain the spelling and pronunciation of: {word}",
            "Spelling help needs an LLM key.",
            max_words=180,
        )
