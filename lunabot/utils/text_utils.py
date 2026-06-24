"""Text utilities for game logic."""


def normalize_text(text: str) -> str:
    """Normalize text for comparison.
    
    Args:
        text: Text to normalize
    
    Returns:
        Normalized text (lowercase, stripped)
    """
    return text.strip().lower()


def fuzzy_match(text1: str, text2: str, threshold: float = 0.8) -> bool:
    """Simple fuzzy string matching.
    
    Args:
        text1: First text
        text2: Second text
        threshold: Match threshold (0-1)
    
    Returns:
        True if texts match above threshold
    """
    t1 = normalize_text(text1)
    t2 = normalize_text(text2)
    
    if t1 == t2:
        return True
    
    # Simple check: if one is substring of other
    if len(t1) > 3 and len(t2) > 3:
        if t1 in t2 or t2 in t1:
            return True
    
    return False


def validate_choice(choice: str, valid_options: list) -> bool:
    """Validate user choice against valid options.
    
    Args:
        choice: User input
        valid_options: List of valid choices
    
    Returns:
        True if valid
    """
    return choice.upper() in valid_options


def format_score_board(scores: dict) -> str:
    """Format scoreboard for display.
    
    Args:
        scores: Dict of user_id -> score
    
    Returns:
        Formatted scoreboard text
    """
    if not scores:
        return "No scores yet."
    
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    lines = []
    
    for rank, (user_id, score) in enumerate(sorted_scores, 1):
        lines.append(f"{rank}. <@{user_id}>: {score}")
    
    return "\n".join(lines)
