"""Background cleanup for inactive game sessions."""

import asyncio
from typing import Optional

from discord.ext import commands


class TimeoutManager:
    TIMEOUT_CHECK_INTERVAL = 60
    INACTIVITY_THRESHOLD = 120

    def __init__(self, game_manager, bot: commands.Bot):
        self.game_manager = game_manager
        self.bot = bot
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._timeout_loop())
        print("Luna TimeoutManager started")

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        print("Luna TimeoutManager stopped")

    async def _timeout_loop(self) -> None:
        while self.running:
            try:
                await self._check_timeouts()
            except Exception as exc:
                print(f"Error in timeout check: {exc}")
            await asyncio.sleep(self.TIMEOUT_CHECK_INTERVAL)

    async def _check_timeouts(self) -> None:
        expired = self.game_manager.get_expired_sessions(self.INACTIVITY_THRESHOLD)
        for channel_id in expired:
            session = self.game_manager.get_session(channel_id)
            if not session:
                continue
            if session.state.get("finished", False):
                self.game_manager.delete_session(channel_id)
                continue
            try:
                game = self.game_manager.get_game(session.game_type)
                if game:
                    await game.timeout(session)
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(
                        "🌙 Game ended due to inactivity. Start another whenever you're ready!"
                    )
            except Exception as exc:
                print(f"Error handling timeout for channel {channel_id}: {exc}")
            finally:
                self.game_manager.delete_session(channel_id)
