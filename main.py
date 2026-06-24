import argparse
import os
from pathlib import Path

import discord

from lunabot.bot import LunaBot
from lunabot.discord_bot import DiscordLuna


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(__file__).resolve().parent / path
    if not env_path.exists():
        return
    with env_path.open("r", encoding="utf-8") as fp:
        for raw_line in fp:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and key not in os.environ:
                os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LunaBot CLI or Discord bot.")
    parser.add_argument("--name", default="World", help="Name to greet for the CLI bot")
    parser.add_argument(
        "--discord",
        action="store_true",
        help="Run Luna as a Discord bot using the DISCORD_TOKEN environment variable",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Optional Discord bot token; falls back to DISCORD_TOKEN",
    )
    args = parser.parse_args()

    if args.discord:
        load_dotenv()
        token = args.token or os.environ.get("DISCORD_TOKEN")
        if not token:
            raise SystemExit(
                "Missing Discord token. Set DISCORD_TOKEN or use --token to start Luna."
            )

        token = token.strip()
        if token.lower().startswith("bot "):
            token = token[4:].strip()
        if len(token) < 30 or token.casefold() in {
            "your_discord_token",
            "your_bot_token",
            "replace_with_your_token",
        }:
            raise SystemExit(
                "DISCORD_TOKEN is still a placeholder or is too short. Reset and "
                "copy the real token from Discord Developer Portal > Bot."
            )

        bot = DiscordLuna()
        try:
            bot.run(token)
        except discord.LoginFailure as exc:
            raise SystemExit(
                "Discord rejected DISCORD_TOKEN (401 Unauthorized). Reset it in "
                "Developer Portal > Bot, update .env, and run again."
            ) from exc
        return

    bot = LunaBot(name=args.name)
    print(bot.greet())


if __name__ == "__main__":
    main()
