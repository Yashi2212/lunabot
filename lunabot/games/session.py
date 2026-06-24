from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Generic, Optional, TypeVar

T = TypeVar("T")

@dataclass
class GameSession(Generic[T]):
    session_id: int
    channel_id: int
    player_id: int
    game_name: str
    state: T
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=15))

    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at


class GameSessionManager:
    def __init__(self, expiry_minutes: int = 15) -> None:
        self.sessions: Dict[int, GameSession] = {}
        self.expiry_minutes = expiry_minutes

    def _make_session_id(self, channel_id: int, player_id: int, game_name: str) -> int:
        return hash((channel_id, player_id, game_name))

    def create(self, channel_id: int, player_id: int, game_name: str, state: T) -> GameSession[T]:
        session_id = self._make_session_id(channel_id, player_id, game_name)
        session = GameSession(session_id=session_id, channel_id=channel_id, player_id=player_id, game_name=game_name, state=state)
        self.sessions[session_id] = session
        return session

    def get(self, channel_id: int, player_id: int, game_name: str) -> Optional[GameSession[T]]:
        session_id = self._make_session_id(channel_id, player_id, game_name)
        session = self.sessions.get(session_id)
        if session and session.is_expired():
            del self.sessions[session_id]
            return None
        return session

    def remove(self, channel_id: int, player_id: int, game_name: str) -> None:
        session_id = self._make_session_id(channel_id, player_id, game_name)
        self.sessions.pop(session_id, None)

    def cleanup(self) -> None:
        expired = [session_id for session_id, session in self.sessions.items() if session.is_expired()]
        for session_id in expired:
            del self.sessions[session_id]
