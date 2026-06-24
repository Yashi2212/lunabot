"""
GameManager — routes messages to correct game instance.
Handles message validation and game dispatch.
"""
import discord
from typing import Dict, Optional
from ..sessions.game_session import GameSession
from ..core.session_manager import SessionManager


class GameManager:
    """Manages game routing and execution."""
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.active_games: Dict[str, object] = {}  # game_type -> game instance
    
    def register_game(self, game_type: str, game_instance) -> None:
        """Register a game type.
        
        Args:
            game_type: Name of game (e.g., "trivia")
            game_instance: Instance of BaseGame subclass
        """
        self.active_games[game_type] = game_instance
    
    def get_game(self, game_type: str) -> Optional[object]:
        """Get game instance by type.
        
        Args:
            game_type: Name of game
        
        Returns:
            Game instance or None
        """
        return self.active_games.get(game_type)
    
    async def handle_message(self, message: discord.Message, bot) -> bool:
        """Route message to correct game.
        
        Message routing logic:
        1. Check if session exists in channel
        2. Verify user is in session
        3. Update activity timestamp
        4. Route to game handler
        
        Args:
            message: Discord message
            bot: Discord bot instance
        
        Returns:
            True if message was handled by a game
        """
        channel_id = message.channel.id
        user_id = message.author.id
        
        # Get session for channel
        session = self.session_manager.get_session(channel_id)
        if not session:
            return False
        
        # Verify user is in session
        if not session.is_player_valid(user_id):
            return False

        # A completion response may still be awaiting Discord I/O while another
        # message arrives. Remove the terminal session before it can score twice.
        if session.state.get("finished", False):
            self.delete_session(channel_id)
            return True
        
        # Lobby chat must not be swallowed by the game router. Only Luna
        # commands such as join/begin/stop interact with a lobby.
        if session.state.get("lobby", False):
            return False

        # Update activity only after validating that the user is a player.
        session.update_activity()
        
        # Get game instance
        game = self.get_game(session.game_type)
        if not game:
            self.delete_session(channel_id)
            return False
        
        # Route to game handler
        try:
            await game.handle_message(session, message)
            if session.state.get("finished", False):
                self.delete_session(channel_id)
            return True
        except Exception as e:
            # Never leave a channel locked behind a crashed game session.
            print(f"Error in {session.game_type} game handler: {e}")
            self.delete_session(channel_id)
            try:
                await message.channel.send(
                    "That game hit an unexpected error and was safely stopped. "
                    "You can start a fresh game now."
                )
            except discord.HTTPException:
                pass
            return True
    
    def create_session(self, channel_id: int, guild_id: int, game_type: str, player_id: int) -> GameSession:
        """Create new game session.
        
        Args:
            channel_id: Discord channel ID
            guild_id: Discord guild ID
            game_type: Type of game
            player_id: Starting player ID
        
        Returns:
            New GameSession
        
        Raises:
            RuntimeError: If game already running
        """
        return self.session_manager.create_session(channel_id, guild_id, game_type, player_id)
    
    def get_session(self, channel_id: int) -> Optional[GameSession]:
        """Get session for channel.
        
        Args:
            channel_id: Discord channel ID
        
        Returns:
            GameSession or None
        """
        return self.session_manager.get_session(channel_id)
    
    def delete_session(self, channel_id: int) -> None:
        """Delete session.
        
        Args:
            channel_id: Discord channel ID
        """
        self.session_manager.delete_session(channel_id)
    
    def get_expired_sessions(self, timeout_seconds: int = 120) -> list:
        """Get expired sessions.
        
        Args:
            timeout_seconds: Inactivity threshold
        
        Returns:
            List of expired channel IDs
        """
        return self.session_manager.get_expired_sessions(timeout_seconds)
