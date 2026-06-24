"""
SessionManager — handles session creation, deletion, and validation.
Ensures only one game per channel and validates player access.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
from ..sessions.game_session import GameSession


class SessionManager:
    """Manages active game sessions."""
    
    def __init__(self):
        self.active_sessions: Dict[int, GameSession] = {}  # channel_id -> session
    
    def create_session(self, channel_id: int, guild_id: int, game_type: str, player_id: int) -> GameSession:
        """Create a new session.
        
        Args:
            channel_id: Discord channel ID
            guild_id: Discord guild ID
            game_type: Type of game (e.g., "trivia", "wordbomb")
            player_id: Starting player ID
        
        Returns:
            New GameSession object
        
        Raises:
            RuntimeError: If game already running in channel
        """
        if channel_id in self.active_sessions:
            raise RuntimeError(f"A game is already running in channel {channel_id}")
        
        session = GameSession(
            channel_id=channel_id,
            guild_id=guild_id,
            game_type=game_type,
        )
        session.add_player(player_id)
        self.active_sessions[channel_id] = session
        return session
    
    def get_session(self, channel_id: int) -> Optional[GameSession]:
        """Get active session for channel.
        
        Args:
            channel_id: Discord channel ID
        
        Returns:
            GameSession or None
        """
        return self.active_sessions.get(channel_id)
    
    def delete_session(self, channel_id: int) -> None:
        """Delete session for channel.
        
        Args:
            channel_id: Discord channel ID
        """
        if channel_id in self.active_sessions:
            del self.active_sessions[channel_id]
    
    def session_exists(self, channel_id: int) -> bool:
        """Check if session exists in channel.
        
        Args:
            channel_id: Discord channel ID
        
        Returns:
            True if session exists
        """
        return channel_id in self.active_sessions
    
    def get_expired_sessions(self, timeout_seconds: int = 120) -> list:
        """Get sessions that have timed out.
        
        Args:
            timeout_seconds: Inactivity threshold (default 120)
        
        Returns:
            List of expired channel IDs
        """
        expired = []
        now = datetime.now()
        
        for channel_id, session in self.active_sessions.items():
            session_timeout = session.state.get("timeout_seconds", timeout_seconds)
            if (now - session.last_activity) > timedelta(seconds=session_timeout):
                expired.append(channel_id)
        
        return expired
    
    def add_player_to_session(self, channel_id: int, player_id: int) -> bool:
        """Add player to existing session.
        
        Args:
            channel_id: Discord channel ID
            player_id: Player ID to add
        
        Returns:
            True if added successfully
        """
        session = self.get_session(channel_id)
        if not session:
            return False
        
        if player_id in session.player_ids:
            return False

        if len(session.player_ids) >= 10:
            return False
        
        session.add_player(player_id)
        return True
    
    def is_player_in_session(self, channel_id: int, player_id: int) -> bool:
        """Check if player is in session.
        
        Args:
            channel_id: Discord channel ID
            player_id: Player ID
        
        Returns:
            True if player is in session
        """
        session = self.get_session(channel_id)
        if not session:
            return False
        return session.is_player_valid(player_id)
