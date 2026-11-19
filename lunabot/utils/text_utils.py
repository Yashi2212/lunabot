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


def format_winner_line(
    scores: dict[int, int],
    winner_ids: list[int] | None = None,
    reason: str = "",
) -> str:
    """Return a compact winner announcement for scored games.

    ``winner_ids`` is useful for elimination games where the survivor wins even
    when another player has a higher accumulated score.
    """
    if not scores:
        return "No winner this time."

    if winner_ids is None:
        winning_score = max(scores.values(), default=0)
        if winning_score <= 0:
            return "No winner this time."
        winner_ids = [
            user_id for user_id, score in scores.items() if score == winning_score
        ]
    else:
        winner_ids = [user_id for user_id in winner_ids if user_id in scores]
        if not winner_ids:
            return "No winner this time."
        winning_score = max(scores.get(user_id, 0) for user_id in winner_ids)

    mentions = " ".join(f"<@{user_id}>" for user_id in winner_ids)
    label = "Winner" if len(winner_ids) == 1 else "Winners"
    suffix = f" — {reason}" if reason else ""
    unit = "point" if winning_score == 1 else "points"
    return f"🏆 {label}: {mentions} with **{winning_score}** {unit}{suffix}."
