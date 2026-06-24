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

# category -> word -> short learning definition
WORD_GROUPS: dict[str, dict[str, str]] = {
    "SPACE": {
        "MOON": "Earth's natural satellite", "STAR": "a luminous ball of hot gas",
        "COMET": "an icy body orbiting the Sun", "PLANET": "a large body orbiting a star",
        "ORBIT": "the curved path of one body around another",
    },
    "OCEAN": {
        "WHALE": "a very large marine mammal", "CORAL": "a sea animal that forms reefs",
        "WAVE": "a moving ridge on the surface of water", "SHELL": "a hard protective outer covering",
        "TIDE": "the regular rise and fall of sea level",
    },
    "MUSIC": {
        "PIANO": "a keyboard instrument with strings", "DRUM": "a percussion instrument",
        "VIOLIN": "a four-stringed bowed instrument", "SONG": "words performed with music",
        "RHYTHM": "a repeated pattern of sound or movement",
    },
    "NATURE": {
        "FOREST": "a large area covered mainly with trees", "RIVER": "a natural flowing watercourse",
        "FLOWER": "the reproductive bloom of a plant", "CLOUD": "visible droplets suspended in air",
        "MEADOW": "grassland often used for hay",
    },
    "FOOD": {
        "APPLE": "a crisp round fruit", "BREAD": "baked food made from flour and water",
        "HONEY": "sweet food made by bees", "PEPPER": "a spice or a hollow-fruited plant",
        "GINGER": "a pungent root used as a spice",
    },
    "TRAVEL": {
        "TRAIN": "connected railway vehicles", "PASSPORT": "an official international travel document",
        "HOTEL": "a place providing paid lodging", "MAP": "a visual representation of an area",
        "JOURNEY": "the act of travelling from one place to another",
    },
    "TECH": {
        "ROBOT": "a programmable machine", "SCREEN": "a surface that displays images",
        "MOUSE": "a handheld computer pointing device", "CODE": "instructions written for a computer",
        "SERVER": "a computer that provides services to others",
    },
    "SCHOOL": {
        "PENCIL": "a graphite writing tool", "BOOK": "written pages bound together",
        "CLASS": "a group learning together", "TEACHER": "a person who helps others learn",
        "LESSON": "a period or unit of learning",
    },
    "ANIMALS": {
        "TIGER": "a large striped wild cat", "RABBIT": "a small long-eared mammal",
        "EAGLE": "a large bird of prey", "HORSE": "a large domesticated hoofed mammal",
        "DOLPHIN": "an intelligent marine mammal",
    },
}

WORD_INFO = {
    word: {"category": category, "definition": definition}
    for category, words in WORD_GROUPS.items()
    for word, definition in words.items()
}


def _font(size: int, bold: bool = False):
    names = ["DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", "arialbd.ttf" if bold else "arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font, fill: str) -> None:
    left, top, right, bottom = box
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

    title = f"LUNA CODENAMES  •  {session.state['difficulty'].upper()}  •  TURN: TEAM {session.state['turn']}"
    draw.rounded_rectangle((30, 14, width - 30, 91), radius=20, fill=PALETTE["header"])
    draw.text((45, 24), title, font=title_font, fill=PALETTE["text"])
    subtitle = "SPYMASTER VIEW" if reveal_roles else "OPERATIVE BOARD — choose a card with A–T"
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


class CodenamesGame(BaseGame):
    name = "codenames"
    description = "Pastel team word-association game"
    max_players = 10
    min_players = 4

    async def start(self, session: GameSession, ctx) -> None:
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        play_mode = session.state.get("play_mode", "solo")
        assassin_count = 2 if difficulty == "hard" else 1
        roles = ["A"] * 8 + ["B"] * 8 + ["assassin"] * assassin_count
        roles += ["neutral"] * (20 - len(roles))
        random.shuffle(roles)
        words = content_rotation.take(
            "codenames:words", list(WORD_INFO), 20, fingerprint=lambda word: word
        )
        random.shuffle(words)
        board = [
            {
                "label": chr(65 + index),
                "word": word,
                "role": roles[index],
                "revealed": False,
            }
            for index, word in enumerate(words)
        ]
        session.state.update(
            difficulty=difficulty,
            play_mode=play_mode,
            timeout_seconds=300,
            board=board,
            turn="A",
            phase="awaiting_clue",
            clue=None,
            clue_number=0,
            guesses_left=0,
            remaining={"A": 8, "B": 8},
        )

        if play_mode == "multi":
            if len(session.player_ids) < self.min_players:
                session.state["finished"] = True
                await ctx.reply("Codenames multiplayer needs at least **4 players**.", mention_author=False)
                return
            session.state["spymasters"] = {"A": session.player_ids[0], "B": session.player_ids[1]}
            operatives = session.player_ids[2:]
            session.state["operatives"] = {
                "A": operatives[::2],
                "B": operatives[1::2],
            }
            if not session.state["operatives"]["A"] or not session.state["operatives"]["B"]:
                session.state["finished"] = True
                await ctx.reply("Each team needs a spymaster and at least one operative.", mention_author=False)
                return
            await ctx.reply(
                f"🕵️ **Pastel Codenames** — Level: **{level_label(difficulty)}**\n"
                f"Team A spymaster: <@{session.state['spymasters']['A']}> | "
                f"Operatives: {' '.join(f'<@{uid}>' for uid in session.state['operatives']['A'])}\n"
                f"Team B spymaster: <@{session.state['spymasters']['B']}> | "
                f"Operatives: {' '.join(f'<@{uid}>' for uid in session.state['operatives']['B'])}\n"
                "**How to play:** Spymasters post `clue <word> <number>`; their operatives "
                "choose A-T without touching opponent, neutral, or assassin cards.\n"
                "**Example:** `clue OCEAN 2` may point to WHALE and CORAL.\n"
                "Private colour boards are being sent to both spymasters.",
                mention_author=False,
            )
            if not await self._dm_spymasters(session, ctx):
                session.state["finished"] = True
                return
        else:
            session.state["operatives"] = {"A": [session.player_ids[0]], "B": []}
            session.state["spymasters"] = {}
            await ctx.reply(
                f"🕵️ **Solo Pastel Codenames** — Level: **{level_label(difficulty)}**\n"
                "Luna is your spymaster. Connect the clue to Team A words and answer with A-T. "
                "Avoid Team B, neutral, and assassin cards.\n"
                "**Example:** `OCEAN — 2` may point to WHALE and CORAL; reply with their letters.\n"
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
                await ctx.reply(f"Could not find Team {team}'s spymaster.", mention_author=False)
                return False
            try:
                text = (
                    f"You are **Team {team}'s spymaster**. Never reveal this board.\n"
                    "On your turn, post `clue <one-word clue> <number>` in the game channel."
                )
                if PIL_AVAILABLE:
                    await member.send(
                        text,
                        file=discord.File(
                            render_board(session, reveal_roles=True),
                            filename=f"codenames_team_{team}.png",
                        ),
                    )
                else:
                    await member.send(text + "\n" + render_text_board(session, reveal_roles=True))
            except (discord.Forbidden, discord.HTTPException):
                await ctx.reply(
                    f"I could not DM <@{user_id}>. Enable DMs from server members and start again.",
                    mention_author=False,
                )
                return False
        return True

    async def _send_public_board(self, session: GameSession, channel, content: str | None = None) -> None:
        text = content or "Choose cards by their letter: **A** through **T**."
        if PIL_AVAILABLE:
            await channel.send(
                text,
                file=discord.File(render_board(session), filename="luna_codenames_board.png"),
            )
        else:
            await channel.send(text + "\n" + render_text_board(session))

    async def _prompt_spymaster(self, session: GameSession, channel) -> None:
        team = session.state["turn"]
        spymaster = session.state["spymasters"][team]
        session.state["phase"] = "awaiting_clue"
        await channel.send(
            f"Team **{team}** turn. <@{spymaster}>, post `clue <one-word clue> <number>`. "
            "The clue cannot be a visible board word."
        )

    async def _give_bot_clue(self, session: GameSession, channel) -> None:
        own_cards = [card for card in session.state["board"] if not card["revealed"] and card["role"] == "A"]
        danger_categories = {
            WORD_INFO[card["word"]]["category"]
            for card in session.state["board"]
            if not card["revealed"] and card["role"] == "assassin"
        }
        counts = Counter(WORD_INFO[card["word"]]["category"] for card in own_cards)
        ranked = sorted(counts, key=lambda item: (item in danger_categories, -counts[item], item))
        clue = ranked[0]
        maximum = {"easy": 3, "medium": 2, "hard": 2}[session.state["difficulty"]]
        number = min(counts[clue], maximum)
        session.state.update(phase="guessing", clue=clue, clue_number=number, guesses_left=number)
        await channel.send(
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
        max_number = {"easy": 4, "medium": 3, "hard": 2}[session.state["difficulty"]]
        number = int(number_text)
        if number > max_number:
            await message.reply(
                f"At {session.state['difficulty']} level, clues may target at most **{max_number}** cards.",
                mention_author=False,
            )
            return
        session.state.update(phase="guessing", clue=clue.upper(), clue_number=number, guesses_left=number)
        operatives = " ".join(f"<@{uid}>" for uid in session.state["operatives"][team])
        await message.channel.send(
            f"Team **{team}** clue: **{clue.upper()} — {number}**\n"
            f"{operatives}, choose A–T or type `pass`."
        )

    async def _handle_guess(self, session: GameSession, message: discord.Message) -> None:
        team = session.state["turn"]
        if message.author.id not in session.state["operatives"][team]:
            return
        content = message.content.strip().upper()
        if content == "PASS":
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
        definition = WORD_INFO[card["word"]]["definition"]
        await self._send_public_board(
            session,
            message.channel,
            f"<@{message.author.id}> revealed **{card['label']}: {card['word']}**.\n"
            f"💡 **Explanation:** {card['word'].title()} — {definition}.",
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
                await self._finish(session, message.channel, f"🏆 Team **{role}** found all eight words and wins!")
                return

        if role != team:
            label = "neutral" if role == "neutral" else f"Team {role}"
            await message.channel.send(f"That was **{label}**—the turn ends.")
            await self._end_turn(session, message.channel)
            return

        session.state["guesses_left"] -= 1
        if session.state["guesses_left"] <= 0:
            await self._end_turn(session, message.channel)
        else:
            await message.channel.send(
                f"Correct team colour! **{session.state['guesses_left']}** guess(es) remain, or type `pass`."
            )

    async def _end_turn(self, session: GameSession, channel) -> None:
        if session.state["play_mode"] == "solo":
            opponent_cards = [card for card in session.state["board"] if not card["revealed"] and card["role"] == "B"]
            if opponent_cards:
                card = random.choice(opponent_cards)
                card["revealed"] = True
                session.state["remaining"]["B"] -= 1
                await self._send_public_board(
                    session,
                    channel,
                    f"Team B's simulated turn found **{card['label']}: {card['word']}**.\n"
                    f"💡 **Explanation:** {card['word'].title()} — {WORD_INFO[card['word']]['definition']}.",
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
        text = f"{result}\nThe full colour key is revealed below."
        if PIL_AVAILABLE:
            await channel.send(
                text,
                file=discord.File(
                    render_board(session, reveal_roles=True), filename="codenames_final_board.png"
                ),
            )
        else:
            await channel.send(text + "\n" + render_text_board(session, reveal_roles=True))

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
