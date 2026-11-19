"""Pastel Codenames-style vocabulary game for Discord."""

from __future__ import annotations

import io
import random
import re
from collections import Counter
from typing import Any

import discord
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ModuleNotFoundError:  # The bot still runs with a text board.
    Image = ImageDraw = ImageFont = None
    PIL_AVAILABLE = False

from ..content_rotation import content_rotation
from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from .difficulty import level_label, normalize_difficulty


PALETTE = {
    "background": "#F7D9C4",
    "header": "#DBCDF0",
    "unrevealed": "#FAEDCB",
    "A": "#C6DEF1",
    "B": "#F2C6DE",
    "neutral": "#C9E4DE",
    "assassin": "#4B4652",
    "border": "#FFFFFF",
    "text": "#554D56",
    "light_text": "#FFFFFF",
}

# category -> word -> short learning definition. Keep board words single-token so
# Discord guesses and clue validation stay simple.
WORD_GROUPS: dict[str, dict[str, str]] = {
    "MUSIC": {
        "COUNTERPOINT": "independent melodies woven together", "TIMBRE": "the colour or quality of a sound",
        "CADENCE": "a musical phrase ending", "LEITMOTIF": "a recurring theme linked to an idea",
        "SYNCOPATION": "rhythm stressing normally weak beats", "POLYPHONY": "several simultaneous melodic lines",
    },
    "HISTORY": {
        "ARMISTICE": "an agreement to stop fighting", "CHRONICLE": "a record of events in order",
        "DIASPORA": "a scattered population away from its homeland", "HEGEMONY": "dominant political influence",
        "REGENCY": "rule on behalf of a monarch", "INSURRECTION": "an organised revolt against authority",
    },
    "CIVICS": {
        "SUFFRAGE": "the right to vote", "REFERENDUM": "a direct public vote on a question",
        "QUORUM": "the minimum number needed for official business", "ORDINANCE": "a local law or regulation",
        "CONSTITUENCY": "voters represented by an elected official", "OMBUDSMAN": "an official who investigates complaints",
    },
    "BIOLOGY": {
        "MITOSIS": "cell division producing matching cells", "RIBOSOME": "a structure that builds proteins",
        "HOMEOSTASIS": "maintenance of stable internal conditions", "ALLELE": "a variant form of a gene",
        "SYMBIOSIS": "close interaction between different organisms", "PHYLOGENY": "evolutionary history of organisms",
    },
    "GEOGRAPHY": {
        "ISTHMUS": "a narrow strip of land joining larger areas", "PLATEAU": "a raised flat landform",
        "ESTUARY": "a river mouth mixed with seawater", "ARCHIPELAGO": "a chain or cluster of islands",
        "OROGRAPHY": "the study of mountains", "DEMOGRAPHY": "statistical study of populations",
    },
    "ASTROLOGY": {
        "ZODIAC": "the twelve-sign celestial belt in astrology", "ASCENDANT": "the rising sign at birth",
        "EPHEMERIS": "a table of celestial positions", "RETROGRADE": "apparent backward planetary motion",
        "SYNASTRY": "comparison of birth charts", "HOROSCOPE": "an astrological chart or forecast",
    },
    "BIOPHYSICS": {
        "DIFFUSION": "movement from high to low concentration", "OSMOSIS": "water movement through a membrane",
        "ENTROPY": "measure of disorder or unavailable energy", "KINETICS": "study of rates of processes",
        "FLUORESCENCE": "light emitted after absorbing radiation", "VISCOSITY": "resistance to flow",
    },
    "NETWORKING": {
        "ROUTER": "a device that directs network traffic", "SUBNET": "a divided portion of a network",
        "PACKET": "a small unit of network data", "LATENCY": "delay before data transfer begins",
        "FIREWALL": "a filter for network traffic", "BANDWIDTH": "maximum data transfer capacity",
    },
    "POLITICS": {
        "DIPLOMACY": "management of relations between states", "SANCTION": "a penalty used to influence behaviour",
        "MANIFESTO": "a public declaration of policy", "COALITION": "an alliance for shared political action",
        "FILIBUSTER": "a delaying tactic in debate", "SOVEREIGNTY": "supreme authority over a territory",
    },
    "PHILOSOPHY": {
        "EPISTEME": "knowledge or a system of understanding", "ONTOLOGY": "study of being and existence",
        "AXIOM": "a statement accepted as self-evident", "SYLLOGISM": "deductive reasoning from premises",
        "TELEOLOGY": "explanation by purpose or end", "EMPIRICISM": "knowledge grounded in experience",
    },
    "PSYCHOLOGY": {
        "COGNITION": "mental processing and understanding", "HEURISTIC": "a practical mental shortcut",
        "SCHEMA": "a mental framework for organising knowledge", "AFFECT": "observable emotional state",
        "PRIMING": "influence from prior exposure", "METACOGNITION": "thinking about one's own thinking",
    },
    "ZOOMUSICOLOGY": {
        "BIRDSONG": "structured vocal sound made by birds", "BIOACOUSTICS": "study of sound in living organisms",
        "ECHOLALIA": "repetition of heard vocal sounds", "STRIDULATION": "sound made by rubbing body parts",
        "CHORUSING": "coordinated group vocal signalling", "ULTRASOUND": "sound above human hearing range",
    },
    "MAGICAL": {
        "GRIMOIRE": "a book of magical instructions", "TALISMAN": "an object believed to bring power or luck",
        "INCANTATION": "spoken words used as a spell", "ALCHEMY": "early mystical transformation practice",
        "DIVINATION": "attempting to discover hidden knowledge", "ENCHANTMENT": "a charm or magical influence",
    },
    "TABOO": {
        "ANATHEMA": "something formally cursed or rejected", "PROSCRIPTION": "an official banning of something",
        "SACRILEGE": "violation of something held sacred", "INTERDICT": "an authoritative prohibition",
        "STIGMA": "a mark of social disgrace", "HERESY": "belief opposing accepted doctrine",
    },
    "ROYAL": {
        "SCEPTRE": "a ceremonial staff of royal authority", "VASSAL": "a holder of land under a lord",
        "CORONET": "a small crown for nobles", "DUCHY": "territory ruled by a duke or duchess",
        "CHANCERY": "a royal or legal records office", "LIEGE": "a feudal superior owed loyalty",
    },
    "EXTINCT": {
        "TRILOBITE": "an extinct marine arthropod", "AMMONITE": "an extinct spiral-shelled mollusc",
        "MAMMOTH": "an extinct elephant relative", "DODO": "an extinct flightless bird",
        "MEGATHERIUM": "an extinct giant ground sloth", "PTEROSAUR": "an extinct flying reptile",
    },
    "APPLICATIONS": {
        "SPREADSHEET": "software for tabular calculations", "FIRMWARE": "software embedded in hardware",
        "DASHBOARD": "a visual interface for key information", "COMPILER": "a tool that translates code",
        "AUTHENTICATOR": "a tool for verifying identity", "WORKFLOW": "a sequence of operational steps",
    },
    "BRITISH": {
        "LORRY": "British English for a truck", "QUEUE": "a line of waiting people",
        "POSTCODE": "British English for a postal code", "PAVEMENT": "British English for a sidewalk",
        "CHEMIST": "British English for a pharmacy", "BISCUIT": "British English for a cookie-like snack",
    },
    "AMERICAN": {
        "TRUCK": "American English for a lorry", "SIDEWALK": "American English for pavement",
        "ZIPCODE": "American English for a postcode", "APARTMENT": "American English for a flat",
        "GASOLINE": "American English for petrol", "CANDY": "American English for sweets",
    },
}

WORD_INFO = {
    word: {"category": category, "definition": definition}
    for category, words in WORD_GROUPS.items()
    for word, definition in words.items()
}

ROLE_COUNTS_BY_ASSASSINS = {
    1: {"A": 8, "B": 8, "neutral": 3, "assassin": 1},
    2: {"A": 8, "B": 8, "neutral": 2, "assassin": 2},
}

GENERIC_CLUES = {
    "ACADEMIC",
    "CONCEPTS",
    "FIELD",
    "KNOWLEDGE",
    "NATURAL",
    "SCIENCE",
    "SCIENTIFIC",
    "STUDY",
    "SUBJECTS",
    "TECHNICAL",
    "TERMS",
    "THINGS",
    "WORDS",
}


def _clean_board_word(value: Any) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalpha())


def _clean_clue(value: Any) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalpha())


def _clean_definition(value: Any) -> str:
    return " ".join(str(value).strip().split())[:140]


def validate_ai_codenames_board(payload: Any, assassin_count: int) -> dict[str, Any] | None:
    """Return a safe AI board, or None if the generated board is not strong enough."""
    if not isinstance(payload, dict):
        return None
    raw_cards = payload.get("cards")
    raw_clues = payload.get("team_a_clues") or payload.get("clues")
    if not isinstance(raw_cards, list) or not isinstance(raw_clues, list):
        return None

    expected_counts = ROLE_COUNTS_BY_ASSASSINS[assassin_count]
    cards: list[dict[str, Any]] = []
    word_info: dict[str, dict[str, str]] = {}
    seen_words: set[str] = set()
    for raw_card in raw_cards:
        if not isinstance(raw_card, dict):
            return None
        word = _clean_board_word(raw_card.get("word"))
        raw_role = str(raw_card.get("role", "")).casefold().strip()
        role = {"a": "A", "team_a": "A", "b": "B", "team_b": "B"}.get(raw_role, raw_role)
        definition = _clean_definition(raw_card.get("definition"))
        category = _clean_clue(raw_card.get("category") or raw_card.get("clue") or "AI")
        if (
            not 3 <= len(word) <= 18
            or word in seen_words
            or role not in expected_counts
            or len(definition.split()) < 4
        ):
            return None
        cards.append({"word": word, "role": role, "revealed": False})
        word_info[word] = {"category": category or "AI", "definition": definition}
        seen_words.add(word)

    if dict(Counter(card["role"] for card in cards)) != expected_counts:
        return None

    team_a_words = {card["word"] for card in cards if card["role"] == "A"}
    clues: list[dict[str, Any]] = []
    covered: set[str] = set()
    for raw_clue in raw_clues:
        if not isinstance(raw_clue, dict):
            continue
        clue = _clean_clue(raw_clue.get("clue"))
        clue_words = [_clean_board_word(word) for word in raw_clue.get("cards", [])]
        clue_words = [word for word in clue_words if word]
        if (
            3 <= len(clue) <= 18
            and len(clue_words) == 4
            and len(set(clue_words)) == 4
            and set(clue_words).issubset(team_a_words)
            and clue not in seen_words
            and clue not in GENERIC_CLUES
            and all(clue not in word and word not in clue for word in seen_words)
        ):
            clues.append(
                {
                    "clue": clue,
                    "cards": clue_words,
                    "teaching": _clean_definition(raw_clue.get("teaching")),
                }
            )
            covered.update(clue_words)

    if len(clues) < 2 or covered != team_a_words:
        return None

    random.shuffle(cards)
    board = [
        {
            "label": chr(65 + index),
            "word": card["word"],
            "role": card["role"],
            "revealed": False,
        }
        for index, card in enumerate(cards)
    ]
    return {
        "theme": _clean_definition(payload.get("theme")) or "AI learning board",
        "board": board,
        "word_info": word_info,
        "clues": clues,
    }


def _font(size: int, bold: bool = False):
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "arialbd.ttf" if bold else "arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_font(text: str, max_width: int, start_size: int, minimum: int = 14, bold: bool = False):
    for size in range(start_size, minimum - 1, -1):
        font = _font(size, bold=bold)
        try:
            width = font.getbbox(text)[2] - font.getbbox(text)[0]
        except AttributeError:
            width = font.getsize(text)[0]
        if width <= max_width:
            return font
    return _font(minimum, bold=bold)


def _text_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font, fill: str) -> None:
    left, top, right, bottom = box
    font = _fit_font(text, right - left - 10, getattr(font, "size", 23), bold=True)
    bounds = draw.textbbox((0, 0), text, font=font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(
        (left + (right - left - width) / 2, top + (bottom - top - height) / 2 - 2),
        text,
        font=font,
        fill=fill,
    )


def render_board(session: GameSession, reveal_roles: bool = False) -> io.BytesIO:
    """Render a readable 5x4 PNG board using the supplied pastel palette."""
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is not installed; use render_text_board instead.")
    width, height = 1100, 720
    image = Image.new("RGB", (width, height), PALETTE["background"])
    draw = ImageDraw.Draw(image)
    title_font = _font(30, bold=True)
    card_font = _font(23, bold=True)
    label_font = _font(17, bold=True)
    small_font = _font(16)

    title = f"CODENAMES - {session.state['difficulty'].upper()} - TURN: TEAM {session.state['turn']}"
    draw.rounded_rectangle((30, 14, width - 30, 91), radius=20, fill=PALETTE["header"])
    draw.text((45, 24), title, font=title_font, fill=PALETTE["text"])
    subtitle = "SPYMASTER VIEW" if reveal_roles else "OPERATIVE BOARD - choose a card with A-T"
    draw.text((47, 66), subtitle, font=small_font, fill=PALETTE["text"])

    margin_x, top = 45, 105
    gap, card_w, card_h = 15, 190, 125
    for index, card in enumerate(session.state["board"]):
        row, col = divmod(index, 5)
        x = margin_x + col * (card_w + gap)
        y = top + row * (card_h + gap)
        show_role = reveal_roles or card["revealed"]
        color = PALETTE[card["role"]] if show_role else PALETTE["unrevealed"]
        text_color = PALETTE["light_text"] if show_role and card["role"] == "assassin" else PALETTE["text"]
        draw.rounded_rectangle(
            (x, y, x + card_w, y + card_h),
            radius=18,
            fill=color,
            outline=PALETTE["border"],
            width=5,
        )
        draw.text((x + 12, y + 9), card["label"], font=label_font, fill=text_color)
        _text_center(draw, (x + 8, y + 25, x + card_w - 8, y + card_h - 10), card["word"], card_font, text_color)
        if card["revealed"]:
            draw.text((x + card_w - 28, y + 8), "X", font=label_font, fill=text_color)

    if reveal_roles:
        legend_y = 680
        legend = [("A", "TEAM A"), ("B", "TEAM B"), ("neutral", "NEUTRAL"), ("assassin", "ASSASSIN")]
        x = 50
        for role, label in legend:
            draw.rounded_rectangle((x, legend_y, x + 27, legend_y + 22), radius=5, fill=PALETTE[role])
            draw.text((x + 35, legend_y), label, font=small_font, fill=PALETTE["text"])
            x += 225

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output


def render_text_board(session: GameSession, reveal_roles: bool = False) -> str:
    """Dependency-free 5x4 fallback board for systems without Pillow."""
    role_marks = {"A": "A", "B": "B", "neutral": "N", "assassin": "X"}
    rows = []
    for start in range(0, 20, 5):
        cells = []
        for card in session.state["board"][start:start + 5]:
            if reveal_roles or card["revealed"]:
                suffix = role_marks[card["role"]]
            else:
                suffix = "?"
            cells.append(f"{card['label']}:{card['word']}[{suffix}]")
        rows.append(" | ".join(cells))
    legend = "A=Team A, B=Team B, N=Neutral, X=Assassin" if reveal_roles else "Choose A-T; ? means unrevealed"
    return "```text\n" + "\n".join(rows) + f"\n{legend}\n```"


def _take_words(category: str, count: int) -> list[str]:
    words = list(WORD_GROUPS[category])
    picked = content_rotation.take(
        f"codenames:words:{category}", words, count, fingerprint=lambda word: word
    )
    if len(picked) < count:
        remaining = [word for word in words if word not in picked]
        random.shuffle(remaining)
        picked.extend(remaining[: count - len(picked)])
    return picked[:count]


def _take_categories(key: str, count: int, exclude: set[str] | None = None) -> list[str]:
    exclude = exclude or set()
    categories = [category for category in WORD_GROUPS if category not in exclude]
    picked = content_rotation.take(key, categories, count, fingerprint=lambda category: category)
    if len(picked) < count:
        remaining = [category for category in categories if category not in picked]
        random.shuffle(remaining)
        picked.extend(remaining[: count - len(picked)])
    return picked[:count]


def _build_clustered_board(difficulty: str, assassin_count: int) -> tuple[list[dict[str, Any]], list[str]]:
    """Create a board where Team A has two safe four-card clue clusters."""
    team_a_categories = _take_categories("codenames:team_a_categories", 2)
    blocked = set(team_a_categories)
    team_b_categories = _take_categories("codenames:team_b_categories", 2, blocked)
    blocked.update(team_b_categories)
    danger_categories = _take_categories("codenames:danger_categories", 4, blocked)

    cards: list[dict[str, Any]] = []
    for category in team_a_categories:
        cards.extend({"word": word, "role": "A"} for word in _take_words(category, 4))
    for category in team_b_categories:
        cards.extend({"word": word, "role": "B"} for word in _take_words(category, 4))

    for category in danger_categories[:assassin_count]:
        cards.append({"word": _take_words(category, 1)[0], "role": "assassin"})

    neutral_count = 20 - len(cards)
    neutral_categories = danger_categories[assassin_count:] + _take_categories(
        f"codenames:neutral_categories:{difficulty}",
        neutral_count,
        set(team_a_categories + team_b_categories + danger_categories),
    )
    for index in range(neutral_count):
        category = neutral_categories[index % len(neutral_categories)]
        cards.append({"word": _take_words(category, 1)[0], "role": "neutral"})

    random.shuffle(cards)
    board = [
        {
            "label": chr(65 + index),
            "word": card["word"],
            "role": card["role"],
            "revealed": False,
        }
        for index, card in enumerate(cards)
    ]
    return board, team_a_categories


def _word_info(session: GameSession, word: str) -> dict[str, str]:
    generated = session.state.get("word_info")
    if isinstance(generated, dict) and word in generated:
        return generated[word]
    return WORD_INFO[word]


def _clean_discord_text(text: str) -> str:
    replacements = {
        "🕵️ ": "",
        "🌙 ": "",
        "💡 ": "",
        "💀 ": "",
        "🏆 ": "",
        "—": "-",
        "–": "-",
        "â€”": "-",
        "â€“": "-",
        "â€¢": "-",
        "ðŸŒ™ ": "",
        "ðŸ•µï¸ ": "",
        "ðŸ’¡ ": "",
        "ðŸ’€ ": "",
        "ðŸ† ": "",
        "Ã°Å¸Å’â„¢ ": "",
        "Ã¢â‚¬â€": "-",
        "colour": "color",
    }
    cleaned = text
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.replace("**-", "** - ")
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cleaned


async def _send_text(target: Any, text: str, *args: Any, **kwargs: Any) -> Any:
    return await target.send(_clean_discord_text(text), *args, **kwargs)


async def _reply_text(ctx: Any, text: str, *args: Any, **kwargs: Any) -> Any:
    return await ctx.reply(_clean_discord_text(text), *args, **kwargs)


def _start_log_turn(session: GameSession, team: str, clue: str, number: int) -> None:
    log = session.state.setdefault("game_log", [])
    entry = {"team": team, "clue": clue, "number": number, "picks": []}
    log.append(entry)
    session.state["current_log_turn"] = entry


def _log_pick(session: GameSession, card: dict[str, Any], picker: str, result: str) -> None:
    entry = session.state.get("current_log_turn")
    if not isinstance(entry, dict):
        return
    entry.setdefault("picks", []).append(
        {
            "picker": picker,
            "label": card["label"],
            "word": card["word"],
            "role": card["role"],
            "result": result,
        }
    )


def _log_pass(session: GameSession, picker: str) -> None:
    entry = session.state.get("current_log_turn")
    if isinstance(entry, dict):
        entry.setdefault("picks", []).append({"picker": picker, "pass": True})


def _format_pick(pick: dict[str, Any]) -> str:
    if pick.get("pass"):
        return f"{pick['picker']} passed"
    role = {"A": "Team A", "B": "Team B", "neutral": "Neutral", "assassin": "Assassin"}[pick["role"]]
    return f"{pick['picker']} -> {pick['label']}:{pick['word']} ({role}, {pick['result']})"


def _format_current_turn_log(session: GameSession) -> str:
    entry = session.state.get("current_log_turn")
    if not isinstance(entry, dict):
        return ""
    picks = entry.get("picks") or []
    if not picks:
        return ""
    lines = [f"**Turn log:** Team {entry['team']} clue `{entry['clue']} - {entry['number']}`"]
    lines.extend(f"- {_format_pick(pick)}" for pick in picks[-4:])
    return "\n" + "\n".join(lines)


def _format_game_log(session: GameSession) -> str:
    entries = session.state.get("game_log") or []
    if not entries:
        return "**Game log:** No turns recorded."
    lines = ["**Game log**"]
    for index, entry in enumerate(entries, start=1):
        lines.append(f"{index}. Team {entry['team']} clue `{entry['clue']} - {entry['number']}`")
        picks = entry.get("picks") or []
        if picks:
            lines.extend(f"   - {_format_pick(pick)}" for pick in picks)
        else:
            lines.append("   - no picks")
    return "\n".join(lines)


class CodenamesGame(BaseGame):
    name = "codenames"
    description = "Pastel team word-association game"
    max_players = 10
    min_players = 4

    async def start(self, session: GameSession, ctx) -> None:
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        play_mode = session.state.get("play_mode", "solo")
        ai_board = session.state.get("ai_codenames_board")
        if not isinstance(ai_board, dict):
            session.state["finished"] = True
            await _reply_text(
                ctx,
                "🌙 Codenames needs a fresh AI board and could not start.",
                mention_author=False,
            )
            return
        board = ai_board["board"]
        safe_clue_categories = []
        word_info = ai_board["word_info"]
        ai_clues = ai_board["clues"]
        board_theme = ai_board["theme"]
        session.state.update(
            difficulty=difficulty,
            play_mode=play_mode,
            timeout_seconds=300,
            board=board,
            safe_clue_categories=safe_clue_categories,
            word_info=word_info,
            ai_clues=ai_clues,
            board_theme=board_theme,
            turn="A",
            phase="awaiting_clue",
            clue=None,
            clue_number=0,
            guesses_left=0,
            remaining={"A": 8, "B": 8},
            game_log=[],
            current_log_turn=None,
        )

        if play_mode == "multi":
            if len(session.player_ids) < self.min_players:
                session.state["finished"] = True
                await _reply_text(ctx, "Codenames multiplayer needs at least **4 players**.", mention_author=False)
                return
            session.state["spymasters"] = {"A": session.player_ids[0], "B": session.player_ids[1]}
            operatives = session.player_ids[2:]
            session.state["operatives"] = {
                "A": operatives[::2],
                "B": operatives[1::2],
            }
            if not session.state["operatives"]["A"] or not session.state["operatives"]["B"]:
                session.state["finished"] = True
                await _reply_text(ctx, "Each team needs a spymaster and at least one operative.", mention_author=False)
                return
            await _reply_text(
                ctx,
                f"**Pastel Codenames** - Level: **{level_label(difficulty)}**\n"
                f"Team A spymaster: <@{session.state['spymasters']['A']}> | "
                f"Operatives: {' '.join(f'<@{uid}>' for uid in session.state['operatives']['A'])}\n"
                f"Team B spymaster: <@{session.state['spymasters']['B']}> | "
                f"Operatives: {' '.join(f'<@{uid}>' for uid in session.state['operatives']['B'])}\n"
                "**How to play:** Spymasters post `clue <word> <number>`; their operatives "
                "choose A-T without touching opponent, neutral, or assassin cards.\n"
                "**Example:** `clue BIOPHYSICS 4` may point to four specialist terms.\n"
                "Private colour boards are being sent to both spymasters.",
                mention_author=False,
            )
            if not await self._dm_spymasters(session, ctx):
                session.state["finished"] = True
                return
        else:
            session.state["operatives"] = {"A": [session.player_ids[0]], "B": []}
            session.state["spymasters"] = {}
            await _reply_text(
                ctx,
                f"**Solo Pastel Codenames** - Level: **{level_label(difficulty)}**\n"
                "Luna is your spymaster. Her clues are built from safe Team A clusters and avoid "
                "Team B, neutral, and assassin categories.\n"
                "**Example:** `BIOPHYSICS - 4` may point to four specialist terms; reply with their letters.\n"
                "Each reveal includes a vocabulary note.",
                mention_author=False,
            )

        await self._send_public_board(session, ctx.channel)
        if play_mode == "solo":
            await self._give_bot_clue(session, ctx.channel)
        else:
            await self._prompt_spymaster(session, ctx.channel)

    async def _dm_spymasters(self, session: GameSession, ctx) -> bool:
        for team, user_id in session.state["spymasters"].items():
            member = ctx.guild.get_member(user_id) if ctx.guild else None
            member = member or ctx.bot.get_user(user_id)
            if member is None:
                await _reply_text(ctx, f"Could not find Team {team}'s spymaster.", mention_author=False)
                return False
            try:
                text = (
                    f"You are **Team {team}'s spymaster**. Never reveal this board.\n"
                    "On your turn, post `clue <one-word clue> <number>` in the game channel."
                )
                if PIL_AVAILABLE:
                    try:
                        await _send_text(
                            member,
                            text,
                            file=discord.File(
                                render_board(session, reveal_roles=True),
                                filename=f"codenames_team_{team}.png",
                            ),
                        )
                        continue
                    except discord.HTTPException:
                        pass
                await _send_text(member, text + "\n" + render_text_board(session, reveal_roles=True))
            except discord.Forbidden:
                await _reply_text(
                    ctx,
                    f"I could not DM <@{user_id}>. Enable DMs from server members and start again.",
                    mention_author=False,
                )
                return False
            except discord.HTTPException:
                await _reply_text(
                    ctx,
                    f"I could not send Team {team}'s private board to <@{user_id}>.",
                    mention_author=False,
                )
                return False
        return True

    async def _send_public_board(self, session: GameSession, channel, content: str | None = None) -> None:
        text = content or "Choose cards by their letter: **A** through **T**."
        if PIL_AVAILABLE:
            try:
                await _send_text(
                    channel,
                    text,
                    file=discord.File(render_board(session), filename="luna_codenames_board.png"),
                )
                return
            except (RuntimeError, discord.HTTPException):
                pass
        await _send_text(
            channel,
            text
            + "\n_Image board unavailable in this runtime; using the text board. "
            "Make sure Pillow is installed from `requirements.txt` and restart Luna._\n"
            + render_text_board(session)
        )

    async def _prompt_spymaster(self, session: GameSession, channel) -> None:
        team = session.state["turn"]
        spymaster = session.state["spymasters"][team]
        session.state["phase"] = "awaiting_clue"
        await _send_text(
            channel,
            f"Team **{team}** turn. <@{spymaster}>, post `clue <one-word clue> <number>`. "
            "The clue cannot be a visible board word."
        )

    async def _give_bot_clue(self, session: GameSession, channel) -> None:
        own_cards = [card for card in session.state["board"] if not card["revealed"] and card["role"] == "A"]
        ai_clues = session.state.get("ai_clues") or []
        for clue_item in ai_clues:
            target_words = set(clue_item.get("cards", []))
            clue_cards = [card for card in own_cards if card["word"] in target_words]
            if clue_cards:
                clue = clue_item["clue"]
                number = min(len(clue_cards), 4)
                session.state.update(
                    phase="guessing",
                    clue=clue,
                    clue_number=number,
                    guesses_left=number,
                    active_clue_cards=[card["word"] for card in clue_cards],
                )
                _start_log_turn(session, "A", clue, number)
                teaching = clue_item.get("teaching")
                teaching_line = f"\nFocus: {teaching}" if teaching else ""
                await _send_text(
                    channel,
                    f"ðŸŒ™ Luna's clue for Team A: **{clue} â€” {number}**{teaching_line}\n"
                    "Reply with a card letter from **A** to **T**, or `pass`."
                )
                return

        opponent_categories = {
            _word_info(session, card["word"])["category"]
            for card in session.state["board"]
            if not card["revealed"] and card["role"] in {"B", "neutral", "assassin"}
        }
        counts = Counter(_word_info(session, card["word"])["category"] for card in own_cards)
        safe_categories = [
            category
            for category in session.state.get("safe_clue_categories", [])
            if counts[category] > 0 and category not in opponent_categories
        ]
        ranked = sorted(
            safe_categories or list(counts),
            key=lambda category: (counts[category] < 3, -counts[category], category),
        )
        clue = ranked[0]
        number = min(counts[clue], 4)
        session.state.update(phase="guessing", clue=clue, clue_number=number, guesses_left=number)
        _start_log_turn(session, "A", clue, number)
        await _send_text(
            channel,
            f"🌙 Luna's clue for Team A: **{clue} — {number}**\n"
            "Reply with a card letter from **A** to **T**, or `pass`."
        )

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        if session.state.get("finished"):
            return
        if session.state["phase"] == "awaiting_clue":
            await self._handle_clue(session, message)
        else:
            await self._handle_guess(session, message)

    async def _handle_clue(self, session: GameSession, message: discord.Message) -> None:
        if session.state["play_mode"] != "multi":
            return
        team = session.state["turn"]
        if message.author.id != session.state["spymasters"][team]:
            return
        match = re.fullmatch(r"clue\s+([a-z]+)\s+([1-4])", message.content.strip().casefold())
        if not match:
            await message.reply("Use exactly: `clue <one-word clue> <number 1-4>`.", mention_author=False)
            return
        clue, number_text = match.groups()
        board_words = [card["word"].casefold() for card in session.state["board"]]
        if any(clue == word or clue in word or word in clue for word in board_words):
            await message.reply("That clue matches part of a visible board word. Choose another.", mention_author=False)
            return
        max_number = 4
        number = int(number_text)
        if number > max_number:
            await message.reply(
                f"At {session.state['difficulty']} level, clues may target at most **{max_number}** cards.",
                mention_author=False,
            )
            return
        session.state.update(phase="guessing", clue=clue.upper(), clue_number=number, guesses_left=number)
        _start_log_turn(session, team, clue.upper(), number)
        operatives = " ".join(f"<@{uid}>" for uid in session.state["operatives"][team])
        await _send_text(
            message.channel,
            f"Team **{team}** clue: **{clue.upper()} — {number}**\n"
            f"{operatives}, choose A–T or type `pass`."
        )

    async def _handle_guess(self, session: GameSession, message: discord.Message) -> None:
        team = session.state["turn"]
        if message.author.id not in session.state["operatives"][team]:
            return
        content = message.content.strip().upper()
        if content == "PASS":
            picker = getattr(message.author, "display_name", None) or f"User {message.author.id}"
            _log_pass(session, picker)
            await _send_text(message.channel, _format_current_turn_log(session))
            await self._end_turn(session, message.channel)
            return
        if content.startswith("GUESS "):
            content = content[6:].strip()
        if len(content) != 1 or content not in "ABCDEFGHIJKLMNOPQRST":
            await message.reply("Choose one unrevealed card using a letter from **A** to **T**.", mention_author=False)
            return
        card = session.state["board"][ord(content) - 65]
        if card["revealed"]:
            await message.reply("That card is already revealed.", mention_author=False)
            return
        card["revealed"] = True
        role = card["role"]
        definition = _word_info(session, card["word"])["definition"]
        picker = getattr(message.author, "display_name", None) or f"User {message.author.id}"
        if role == "assassin":
            pick_result = "assassin"
        elif role == team:
            pick_result = "correct"
        elif role == "neutral":
            pick_result = "neutral"
        else:
            pick_result = "wrong team"
        _log_pick(session, card, picker, pick_result)
        await self._send_public_board(
            session,
            message.channel,
            f"<@{message.author.id}> revealed **{card['label']}: {card['word']}**.\n"
            f"💡 **Explanation:** {card['word'].title()} — {definition}."
            f"{_format_current_turn_log(session)}",
        )

        if role == "assassin":
            winner = "B" if team == "A" else "A"
            if session.state["play_mode"] == "solo":
                await self._finish(session, message.channel, "💀 Assassin revealed—Luna's team loses this board.")
            else:
                await self._finish(session, message.channel, f"💀 Assassin revealed—Team **{winner}** wins!")
            return

        if role in {"A", "B"}:
            session.state["remaining"][role] -= 1
            if session.state["remaining"][role] <= 0:
                if session.state["play_mode"] == "solo" and role == "A":
                    player_id = session.player_ids[0] if session.player_ids else None
                    winner = f"<@{player_id}> (Team A)" if player_id is not None else "Team A"
                    result = f"🏆 {winner} found all eight words and wins!"
                else:
                    result = f"🏆 Team **{role}** found all eight words and wins!"
                await self._finish(session, message.channel, result)
                return

        if role != team:
            label = "neutral" if role == "neutral" else f"Team {role}"
            await _send_text(message.channel, f"That was **{label}**—the turn ends.")
            await self._end_turn(session, message.channel)
            return

        session.state["guesses_left"] -= 1
        if session.state["guesses_left"] <= 0:
            await self._end_turn(session, message.channel)
        else:
            await _send_text(
                message.channel,
                f"Correct team colour! **{session.state['guesses_left']}** guess(es) remain, or type `pass`."
            )

    async def _end_turn(self, session: GameSession, channel) -> None:
        if session.state["play_mode"] == "solo":
            opponent_cards = [card for card in session.state["board"] if not card["revealed"] and card["role"] == "B"]
            if opponent_cards:
                card = random.choice(opponent_cards)
                clue = _word_info(session, card["word"])["category"]
                _start_log_turn(session, "B", clue, 1)
                card["revealed"] = True
                session.state["remaining"]["B"] -= 1
                _log_pick(session, card, "Luna AI", "found")
                await self._send_public_board(
                    session,
                    channel,
                    f"Team B's simulated clue: **{clue} — 1**.\n"
                    f"Team B found **{card['label']}: {card['word']}**.\n"
                    f"💡 **Explanation:** {card['word'].title()} — {_word_info(session, card['word'])['definition']}."
                    f"{_format_current_turn_log(session)}",
                )
            if session.state["remaining"]["B"] <= 0:
                await self._finish(session, channel, "Team B found all its words first. Try another board!")
                return
            session.state["turn"] = "A"
            await self._give_bot_clue(session, channel)
            return

        session.state["turn"] = "B" if session.state["turn"] == "A" else "A"
        await self._prompt_spymaster(session, channel)

    async def _finish(self, session: GameSession, channel, result: str) -> None:
        session.state["finished"] = True
        text = f"{result}\n\n{_format_game_log(session)}\n\nThe full colour key is revealed below."
        if PIL_AVAILABLE:
            try:
                await _send_text(
                    channel,
                    text,
                    file=discord.File(
                        render_board(session, reveal_roles=True), filename="codenames_final_board.png"
                    ),
                )
                return
            except (RuntimeError, discord.HTTPException):
                pass
        await _send_text(channel, text + "\n" + render_text_board(session, reveal_roles=True))

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
