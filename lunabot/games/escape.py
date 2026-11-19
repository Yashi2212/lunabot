"""Data-driven, rotating Escape Room puzzles."""

from __future__ import annotations

import random
import re
from copy import deepcopy

import discord

from ..content_rotation import content_rotation
from ..core.base_game import BaseGame
from ..sessions.game_session import GameSession
from .difficulty import level_label, normalize_difficulty


# Keep a local bank so Escape remains playable when the model is unavailable and
# so a deterministic model response cannot make every new room identical.
ESCAPE_PUZZLES = [
    {
        "title": "The Moonlit Library",
        "scene": "A coded chest blocks the library exit. A desk, a globe, and dusty shelves wait in the moonlight.",
        "items": {
            "atlas": "A world atlas with the word NORTH scratched beside a compass rose.",
            "brass key": "A small key shaped like a compass needle.",
            "candle": "Wax has melted into an arrow pointing upward.",
        },
        "clue_item": "atlas",
        "key_item": "brass key",
        "clues": {
            "easy": "The atlas directly marks the word **NORTH**.",
            "medium": "The compass rose emphasises the direction opposite south.",
            "hard": "Read the upward point on a conventional map.",
        },
        "answer": "north",
        "success": "The compass lock turns north and the library door opens.",
        "learning_note": "On conventional maps, north is normally shown at the top.",
    },
    {
        "title": "The Silent Observatory",
        "scene": "The observatory dome is sealed. A telescope faces a star chart while a four-wheel number lock guards the stairs.",
        "items": {
            "star chart": "Four circled constellations contain 4, 2, 1, and 7 marked stars.",
            "silver lens": "The lens reveals an arrow reading the circled groups from largest drawing to smallest.",
            "meteorite": "A heavy iron-rich rock that pulls weakly toward a magnet.",
        },
        "clue_item": "star chart",
        "key_item": "silver lens",
        "clues": {
            "easy": "Read the circled star counts as **4-2-1-7**.",
            "medium": "Count each circled group, following the lens arrow.",
            "hard": "Magnitude orders the drawings; cardinality supplies each digit.",
        },
        "answer": "4217",
        "success": "The dome rotates, revealing the open stairway beneath it.",
        "learning_note": "Cardinality is the number of elements in a set; here each star group supplied one digit.",
    },
    {
        "title": "The Clockmaker's Attic",
        "scene": "Hundreds of clocks have stopped at different times. One locked cabinet continues ticking every fifteen minutes.",
        "items": {
            "repair journal": "A note reads: one fourth of an hour is the cabinet's spoken password.",
            "winding key": "A delicate key that fits the cabinet mechanism.",
            "pendulum": "It swings exactly once per second.",
        },
        "clue_item": "repair journal",
        "key_item": "winding key",
        "clues": {
            "easy": "One fourth of an hour is called a **quarter** hour.",
            "medium": "Divide sixty minutes into four equal parts and name the fraction.",
            "hard": "The password is the fractional noun represented by 15/60.",
        },
        "answer": "quarter",
        "success": "The cabinet chimes and a hidden ladder unfolds from the wall.",
        "learning_note": "A quarter is one of four equal parts; a quarter hour is fifteen minutes.",
    },
    {
        "title": "The Glasshouse Cipher",
        "scene": "Vines cover the greenhouse exit. A botanical console asks for the process plants use to turn light into food.",
        "items": {
            "botany journal": "A diagram joins sunlight, water, and carbon dioxide to glucose and oxygen.",
            "pruning shears": "Sharp shears can free the console from the vines.",
            "blue orchid": "Its petals turn toward the brightest window.",
        },
        "clue_item": "botany journal",
        "key_item": "pruning shears",
        "clues": {
            "easy": "The process is **photosynthesis**.",
            "medium": "Name the light-powered process that produces glucose in plants.",
            "hard": "Combine the Greek roots for light and putting together.",
        },
        "answer": "photosynthesis",
        "success": "The console glows green and the vines release the exit.",
        "learning_note": "Photosynthesis uses light energy to convert carbon dioxide and water into glucose and oxygen.",
    },
    {
        "title": "The Curator's Gallery",
        "scene": "A portrait gallery has rearranged itself. The exit plaque asks for the European era whose name means rebirth.",
        "items": {
            "curator notes": "The notes describe a rebirth of classical art and learning from the 14th to 17th centuries.",
            "marble token": "The token fits a circular slot beneath the exit plaque.",
            "paintbrush": "Pigment on the brush contains ground lapis lazuli.",
        },
        "clue_item": "curator notes",
        "key_item": "marble token",
        "clues": {
            "easy": "The era described is the **Renaissance**.",
            "medium": "Its French-derived name literally means rebirth.",
            "hard": "Identify the cultural movement bridging medieval and early modern Europe.",
        },
        "answer": "renaissance",
        "success": "The portraits bow as the gallery doors swing open.",
        "learning_note": "Renaissance means rebirth and refers to renewed interest in classical art and scholarship.",
    },
    {
        "title": "The Lighthouse Signal",
        "scene": "A storm has locked the lighthouse lantern room. A signal console requests the maritime distress code.",
        "items": {
            "signal log": "Three short marks, three long marks, then three short marks repeat across the page.",
            "copper switch": "The switch restores power to the signal console.",
            "fog bell": "Its rhythm matches the marks in the signal log.",
        },
        "clue_item": "signal log",
        "key_item": "copper switch",
        "clues": {
            "easy": "Three short, three long, three short is **SOS** in Morse code.",
            "medium": "Decode ... --- ... using Morse code.",
            "hard": "Translate dit-dit-dit, dah-dah-dah, dit-dit-dit.",
        },
        "answer": "sos",
        "success": "The distress signal flashes and the lantern-room door unlocks.",
        "learning_note": "SOS is represented in Morse code as three dots, three dashes, and three dots.",
    },
]


def valid_escape_puzzle(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    required_strings = ("title", "scene", "clue_item", "key_item", "answer", "success", "learning_note")
    if not all(isinstance(value.get(key), str) and value[key].strip() for key in required_strings):
        return False
    if len(value["title"]) > 80 or len(value["scene"]) > 600 or len(value["answer"]) > 40:
        return False
    items = value.get("items")
    clues = value.get("clues")
    if not isinstance(items, dict) or not 3 <= len(items) <= 5:
        return False
    if not all(
        isinstance(key, str)
        and re.fullmatch(r"[a-z][a-z -]{1,30}", key)
        and isinstance(description, str)
        and 5 <= len(description) <= 500
        for key, description in items.items()
    ):
        return False
    if (
        value["clue_item"] not in items
        or value["key_item"] not in items
        or value["clue_item"] == value["key_item"]
    ):
        return False
    return isinstance(clues, dict) and all(isinstance(clues.get(level), str) for level in ("easy", "medium", "hard"))


class EscapeRoomGame(BaseGame):
    name = "escape"
    description = "Rotating interactive learning escape rooms"
    max_players = 1

    async def start(self, session: GameSession, ctx) -> None:
        difficulty = normalize_difficulty(session.state.get("difficulty"))
        supplied = session.state.get("puzzle")
        if not valid_escape_puzzle(supplied):
            session.state["finished"] = True
            await ctx.reply(
                "🌙 Escape Room needs a fresh AI puzzle and could not start.",
                mention_author=False,
            )
            return
        puzzle = deepcopy(supplied)
        attempts = {"easy": 4, "medium": 3, "hard": 2}[difficulty]
        item_names = list(puzzle["items"])
        random.shuffle(item_names)
        session.state.update(
            puzzle=puzzle,
            inventory=[],
            discovered=[],
            search_order=item_names,
            solve_attempts=0,
            hints_used=0,
            difficulty=difficulty,
            max_solve_attempts=attempts,
        )
        await ctx.reply(
            f"🚪 **Escape Room: {puzzle['title']}**\n"
            f"Level: **{level_label(difficulty)}** — {attempts} answer attempts.\n\n"
            f"{puzzle['scene']}\n\n"
            "**How to play:** Explore, collect the clue and key items, inspect them, then solve the exit.\n"
            "**Example:** `search` → `take atlas` → `inspect atlas` → `solve north`.\n"
            "Use `look`, `search`, `take <item>`, `inspect <item>`, `inventory`, "
            "`hint`, or `solve <answer>`.",
            mention_author=False,
        )

    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        content = " ".join(message.content.strip().casefold().split())
        puzzle = session.state["puzzle"]
        inventory = session.state["inventory"]
        discovered = session.state["discovered"]

        if content == "look":
            await message.reply(
                f"👀 {puzzle['scene']}\nTry `search` to examine the room closely.",
                mention_author=False,
            )
        elif content == "search":
            hidden = [item for item in session.state["search_order"] if item not in discovered]
            if not hidden:
                await message.reply("You have already found every movable item here.", mention_author=False)
                return
            found_count = 2 if session.state["difficulty"] == "easy" else 1
            found = hidden[:found_count]
            discovered.extend(found)
            await message.reply(
                "🔎 You discover: " + ", ".join(f"**{item}**" for item in found) + ".",
                mention_author=False,
            )
        elif content.startswith("take "):
            item = content[5:].strip()
            if item not in puzzle["items"] or item not in discovered:
                await message.reply("You have not discovered that item yet. Search again.", mention_author=False)
            elif item in inventory:
                await message.reply(f"The **{item}** is already in your inventory.", mention_author=False)
            else:
                inventory.append(item)
                await message.reply(f"You take the **{item}**.", mention_author=False)
        elif content.startswith("inspect "):
            item = content[8:].strip()
            if item not in inventory:
                await message.reply("Take that item before inspecting it.", mention_author=False)
                return
            description = puzzle["items"][item]
            if item == puzzle["clue_item"]:
                description += "\n🧩 " + puzzle["clues"][session.state["difficulty"]]
            elif item == puzzle["key_item"]:
                description += "\n🔑 This looks essential for activating the exit mechanism."
            await message.reply(description, mention_author=False)
        elif content == "inventory":
            await message.reply(
                "🎒 Inventory: " + (", ".join(inventory) if inventory else "empty"),
                mention_author=False,
            )
        elif content == "hint":
            session.state["hints_used"] += 1
            if puzzle["clue_item"] not in inventory:
                hint = f"Find, take, and inspect the **{puzzle['clue_item']}**."
            elif puzzle["key_item"] not in inventory:
                hint = f"The exit also needs the **{puzzle['key_item']}**."
            else:
                hint = puzzle["clues"][session.state["difficulty"]]
            await message.reply(f"💡 Hint: {hint}", mention_author=False)
        elif content.startswith("solve "):
            if puzzle["clue_item"] not in inventory or puzzle["key_item"] not in inventory:
                await message.reply(
                    f"You need both the **{puzzle['clue_item']}** and **{puzzle['key_item']}** first.",
                    mention_author=False,
                )
                return
            session.state["solve_attempts"] += 1
            answer = content[6:].strip()
            if answer == puzzle["answer"].strip().casefold():
                session.increment_score(message.author.id)
                session.state["finished"] = True
                await message.reply(
                    f"🏆 <@{message.author.id}> escaped!\n"
                    f"🎉 {puzzle['success']}\n**Correct answer:** {puzzle['answer']}\n"
                    f"💡 **Explanation:** {puzzle['learning_note']}",
                    mention_author=False,
                )
            elif session.state["solve_attempts"] >= session.state["max_solve_attempts"]:
                session.state["finished"] = True
                await message.reply(
                    f"The mechanism locks after {session.state['max_solve_attempts']} wrong attempts. "
                    f"**Correct answer:** {puzzle['answer']}\n"
                    f"💡 **Explanation:** {puzzle['learning_note']}",
                    mention_author=False,
                )
            else:
                left = session.state["max_solve_attempts"] - session.state["solve_attempts"]
                await message.reply(
                    f"That answer does not unlock it. **{left}** attempt{'s' if left != 1 else ''} remain.",
                    mention_author=False,
                )
        else:
            await message.reply(
                "Try `look`, `search`, `take <item>`, `inspect <item>`, `inventory`, `hint`, or `solve <answer>`.",
                mention_author=False,
            )

    async def end(self, session: GameSession) -> None:
        session.state["finished"] = True

    async def timeout(self, session: GameSession) -> None:
        session.state["finished"] = True
