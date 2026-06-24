"""
BaseGame — abstract base class for all games.
Every game MUST inherit from this and implement required methods.
"""
from abc import ABC, abstractmethod
import discord
from ..sessions.game_session import GameSession


class BaseGame(ABC):
    """Abstract base class for all Luna games."""
    
    name: str = "base"
    description: str = "Base game class"
    max_players: int = 1
    
    def __init__(self):
        pass
    
    @abstractmethod
    async def start(self, session: GameSession, ctx) -> None:
        """Initialize and start the game.
        
        Args:
            session: Active GameSession
            ctx: Discord context
        """
        pass
    
    @abstractmethod
    async def handle_message(self, session: GameSession, message: discord.Message) -> None:
        """Process player message.
        
        Args:
            session: Active GameSession
            message: Discord message from player
        """
        pass
    
    @abstractmethod
    async def end(self, session: GameSession) -> None:
        """Clean up and end the game.
        
        Args:
            session: Active GameSession
        """
        pass
    
    @abstractmethod
    async def timeout(self, session: GameSession) -> None:
        """Handle game timeout (120 seconds inactivity).
        
        Args:
            session: Active GameSession
        """
        pass
