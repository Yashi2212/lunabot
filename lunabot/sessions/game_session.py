"""
GameSession — unified session object for all games.
Handles state, players, scoring, and activity tracking.
"""
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Set
import uuid


@dataclass
class GameSession:
    """Single unified session for any game."""
    
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: int = 0
    guild_id: int = 0
    game_type: str = ""
    player_ids: List[int] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    score: Dict[int, int] = field(default_factory=dict)
    history: deque = field(default_factory=lambda: deque(maxlen=50))
    current_round: int = 0
    current_question: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    answered_users: Set[int] = field(default_factory=set)
    
    def add_player(self, user_id: int) -> None:
        """Add player to session (global safety cap: 10)."""
        if len(self.player_ids) < 10 and user_id not in self.player_ids:
            self.player_ids.append(user_id)
            if user_id not in self.score:
                self.score[user_id] = 0
    
    def remove_player(self, user_id: int) -> None:
        """Remove player from session."""
        if user_id in self.player_ids:
            self.player_ids.remove(user_id)
        self.score.pop(user_id, None)
        self.answered_users.discard(user_id)
    
    def is_player_valid(self, user_id: int) -> bool:
        """Check if user is allowed in this session."""
        return user_id in self.player_ids
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def add_history(self, entry: str) -> None:
        """Add entry to history (auto-limited to 50)."""
        self.history.append(entry)
    
    def increment_score(self, user_id: int, points: int = 1) -> None:
        """Add points to player score."""
        if user_id in self.score:
            self.score[user_id] += points
    
    def reset_answered(self) -> None:
        """Clear answered users (for next round)."""
        self.answered_users.clear()
    
    def is_answered_by(self, user_id: int) -> bool:
        """Check if user already answered this round."""
        return user_id in self.answered_users
    
    def mark_answered(self, user_id: int) -> None:
        """Mark user as having answered."""
        self.answered_users.add(user_id)
