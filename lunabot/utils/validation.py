"""Validation utilities."""


def is_valid_channel_id(channel_id: int) -> bool:
    """Validate Discord channel ID.
    
    Args:
        channel_id: Channel ID
    
    Returns:
        True if valid
    """
    return isinstance(channel_id, int) and channel_id > 0


def is_valid_user_id(user_id: int) -> bool:
    """Validate Discord user ID.
    
    Args:
        user_id: User ID
    
    Returns:
        True if valid
    """
    return isinstance(user_id, int) and user_id > 0


def is_valid_game_type(game_type: str, valid_types: list) -> bool:
    """Validate game type.
    
    Args:
        game_type: Game type string
        valid_types: List of valid game types
    
    Returns:
        True if valid
    """
    return game_type in valid_types


def validate_player_count(player_count: int, max_players: int = 5) -> bool:
    """Validate player count.
    
    Args:
        player_count: Number of players
        max_players: Maximum allowed
    
    Returns:
        True if valid
    """
    return 1 <= player_count <= max_players
