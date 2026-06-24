import os
from pathlib import Path

import discord

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
    load_dotenv()
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit(
            "Missing Discord token. Set DISCORD_TOKEN before running run_luna.py."
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
            "DISCORD_TOKEN is still a placeholder or is too short.\n"
            "Open https://discord.com/developers/applications, select Luna, "
            "go to Bot > Reset Token, copy the new token, and set:\n"
            "DISCORD_TOKEN=paste_the_real_token_here\n"
            "Do not include quotes or the word 'Bot'."
        )

    bot = DiscordLuna()
    try:
        bot.run(token)
    except discord.LoginFailure as exc:
        raise SystemExit(
            "Discord rejected DISCORD_TOKEN (401 Unauthorized). Reset the token "
            "in Developer Portal > Bot, update .env, and run again."
        ) from exc


if __name__ == "__main__":
    main()
