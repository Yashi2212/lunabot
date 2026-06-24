# 🌙 Luna Discord Game Engine Architecture

## Overview

Luna is a **session-based Discord game engine** that provides multiplayer and single-player games with strict state management, timeout handling, and clean message routing.

All games run inside a **GameSession** with:
- Player management (max 5 per game)
- Memory-safe state
- Automatic timeout (120s inactivity)
- Shared scoring system
- Activity tracking

---

## 📁 Directory Structure

```
lunabot/
├── core/                    # Engine core
│   ├── base_game.py        # Abstract base class
│   ├── game_manager.py     # Game routing
│   ├── session_manager.py  # Session lifecycle
│   ├── timeout_manager.py  # Timeout loop
│   └── __init__.py
├── sessions/
│   ├── game_session.py     # Session object
│   └── __init__.py
├── games/                   # Game implementations
│   ├── tea_challenge.py    # Single-player word guess
│   ├── trivia.py           # Multiplayer fast Q&A
│   ├── quiz.py             # Multiplayer independent scoring
│   ├── riddle.py           # Single-player riddle
│   ├── escape.py           # Single-player exploration
│   ├── storyteller.py      # Turn-based story
│   ├── would_you_rather.py # Voting game
│   └── __init__.py
├── commands/               # Discord commands (stub)
│   └── __init__.py
├── data/                   # Static game data
│   ├── riddles.json
│   ├── trivia.json
│   ├── quiz_questions.json
│   └── would_you_rather.json
├── utils/                  # Utilities
│   ├── text_utils.py      # Text normalization, fuzzy matching
│   ├── validation.py      # Input validation
│   └── __init__.py
├── assets/                 # UI/UX
│   ├── emojis.py          # Emojis and responses
│   └── __init__.py
└── games/
    ├── session.py         # (OLD - keep for now)
    ├── tea_time.py        # (OLD - keep for now)
    └── wordbomb.py        # (OLD - being phased out)
```

---

## 🧠 Core Components

### 1. **GameSession** (`sessions/game_session.py`)

Unified session object for all games:

```python
session = GameSession(
    channel_id=123456,
    guild_id=789012,
    game_type="trivia",
    player_ids=[user1, user2],
    state={...},
    score={user1: 5, user2: 3}
)
```

**Methods:**
- `add_player(user_id)` — Add player (max 5)
- `is_player_valid(user_id)` — Check authorization
- `update_activity()` — Update timestamp
- `increment_score(user_id, points)` — Add points
- `mark_answered(user_id)` — Track who answered this round

---

### 2. **BaseGame** (`core/base_game.py`)

Abstract class all games inherit from:

```python
class MyGame(BaseGame):
    async def start(self, session, ctx):
        pass
    
    async def handle_message(self, session, message):
        pass
    
    async def end(self, session):
        pass
    
    async def timeout(self, session):
        pass
```

---

### 3. **GameManager** (`core/game_manager.py`)

Routes messages to correct game:

```python
manager = GameManager()
manager.register_game("trivia", TriviaGame())

# Message comes in
handled = await manager.handle_message(message, bot)
```

**Message Routing:**
1. Check session exists in channel
2. Verify user in session
3. Update activity timestamp
4. Route to game handler

---

### 4. **SessionManager** (`core/session_manager.py`)

Manages session lifecycle:

```python
sm = SessionManager()

# Create
session = sm.create_session(channel_id, guild_id, "trivia", player_id)

# Retrieve
session = sm.get_session(channel_id)

# Delete
sm.delete_session(channel_id)

# Check expired
expired = sm.get_expired_sessions(timeout_seconds=120)
```

---

### 5. **TimeoutManager** (`core/timeout_manager.py`)

Background loop (runs every 60 seconds):

```python
timeout_mgr = TimeoutManager(game_manager, bot)
await timeout_mgr.start()

# Every 60 seconds:
# - Check for sessions > 120s inactive
# - Call game.timeout(session)
# - Delete session
# - Send "🌙 Game ended due to inactivity."
```

---

## 🎮 Game Implementations

### 1. **TeaChallengeGame** (`games/tea_challenge.py`)

**Type:** Single-player  
**Rules:** Guess word from definition (3 attempts)

```
Bot: "A gentle wind"
Player: breeze
Bot: "✅ Correct!"
```

---

### 2. **TriviaGame** (`games/trivia.py`)

**Type:** Multiplayer (2-5 players)  
**Rules:** 5 rounds, fastest correct answer wins round

```
Bot: "Q1: What is the capital of France?"
Players reply: A, B, C, D
Fastest correct gets +1 point
```

---

### 3. **QuizGame** (`games/quiz.py`)

**Type:** Multiplayer (2-5 players)  
**Rules:** 10 questions, independent scoring, highest score wins

```
Bot: "Q1: 2+2?"
Player A: B (correct) → +1
Player B: C (wrong) → +0
```

---

### 4. **RiddleGame** (`games/riddle.py`)

**Type:** Single-player  
**Rules:** Solve one riddle, get points if correct

```
Bot: "I speak without a mouth..."
Player: echo
Bot: "✅ Correct!"
```

---

### 5. **EscapeRoomGame** (`games/escape.py`)

**Type:** Single-player  
**Rules:** Explore room, collect items, solve puzzle, escape

```
Player: search
Bot: "You find: key, book, candle"

Player: solve 1952
Bot: "✅ Correct! You escaped!"
```

---

### 6. **StorytellerGame** (`games/storyteller.py`)

**Type:** Multiplayer (2-5 players)  
**Rules:** 10 turns, each player adds one sentence

```
Player 1: "Once upon a time..."
Player 2: "a dragon woke up."
Player 3: "It was very confused."
```

---

### 7. **WouldYouRatherGame** (`games/would_you_rather.py`)

**Type:** Multiplayer (2-5 players)  
**Rules:** Vote A or B, see results, next question

```
Bot: "Would you rather: A) Fly  B) Swim"
Players vote: A, B, A, A
Results: A (3), B (1) — "A wins!"
```

---

## 🔌 Integration with Main Bot

### Register Games

```python
from lunabot.core import GameManager
from lunabot.games import TeaChallengeGame, TriviaGame, QuizGame, RiddleGame, EscapeRoomGame, StorytellerGame, WouldYouRatherGame

game_manager = GameManager()
game_manager.register_game("tea", TeaChallengeGame())
game_manager.register_game("trivia", TriviaGame())
game_manager.register_game("quiz", QuizGame())
game_manager.register_game("riddle", RiddleGame())
game_manager.register_game("escape", EscapeRoomGame())
game_manager.register_game("storyteller", StorytellerGame())
game_manager.register_game("would_you_rather", WouldYouRatherGame())
```

### Start Timeout Loop

```python
from lunabot.core import TimeoutManager

timeout_mgr = TimeoutManager(game_manager, bot)
await timeout_mgr.start()
```

### Route Messages

```python
async def on_message(message):
    if message.author.bot:
        return
    
    # Try game routing first
    handled = await game_manager.handle_message(message, bot)
    if handled:
        return
    
    # Then process commands
    await bot.process_commands(message)
```

---

## 💾 Memory Management

**What's stored:**
- Active sessions (channel_id → GameSession)
- Session state (game variables)
- Scores (player_id → int)
- History (max 50 entries per session)

**Auto-cleanup:**
- Timeout after 120s inactivity
- Session deleted from memory
- No database required
- Memory safe for free hosting

---

## ⏱ Timeout System

Every 60 seconds:

```python
expired = game_manager.get_expired_sessions(timeout_seconds=120)

for channel_id in expired:
    session = game_manager.get_session(channel_id)
    
    # Call game timeout handler
    game = game_manager.get_game(session.game_type)
    await game.timeout(session)
    
    # Send message
    channel.send("🌙 Game ended due to inactivity.")
    
    # Delete
    game_manager.delete_session(channel_id)
```

---

## 👥 Multiplayer Rules

- **Max players:** 5 per session
- **One game per channel:** Block or replace existing
- **Player authorization:** Only players in session.player_ids can interact
- **Activity tracking:** Each message updates last_activity timestamp
- **Score tracking:** Dict[user_id, points]

---

## 🧹 Validation & Utils

### Text Utils
- `normalize_text(text)` — lowercase, strip
- `fuzzy_match(t1, t2)` — fuzzy string comparison
- `validate_choice(choice, options)` — MCQ validation
- `format_score_board(scores)` — pretty scoreboard

### Validation
- `is_valid_channel_id(id)`
- `is_valid_user_id(id)`
- `is_valid_game_type(type, valid_list)`
- `validate_player_count(count, max)`

---

## 🎨 Assets & Styling

Emojis and responses in `assets/emojis.py`:

```python
from lunabot.assets import MOON, CHERRY_BLOSSOM, TROPHY, RESPONSES

MOON = "🌙"
CHERRY_BLOSSOM = "🌸"
TROPHY = "🏆"

RESPONSES = {
    "correct": ["Yaaas!", "✅ Correct!"],
    "incorrect": ["❌ Not quite", "Oh no!"],
    "timeout": ["🌙 Game ended due to inactivity."],
}
```

---

## 🚀 Quick Start

1. **Create session:**
   ```python
   session = game_manager.create_session(channel_id, guild_id, "trivia", user_id)
   ```

2. **Start game:**
   ```python
   game = game_manager.get_game("trivia")
   await game.start(session, ctx)
   ```

3. **Messages route automatically** through `game_manager.handle_message()`

4. **Game ends via:**
   - Player completion
   - Timeout (120s inactivity)
   - Manual `/luna end` command

---

## 📋 Design Principles

✅ **Modular** — Each game is independent  
✅ **Session-based** — All state in session object  
✅ **Memory-safe** — Auto-cleanup, no database  
✅ **Message-routed** — Clean separation of concerns  
✅ **Timeout-aware** — Auto-end inactive games  
✅ **Multiplayer-ready** — Support 2-5 players  
✅ **Extensible** — Easy to add new games  

---

## 📝 Adding a New Game

1. Create `games/my_game.py`
2. Inherit from `BaseGame`
3. Implement: `start()`, `handle_message()`, `end()`, `timeout()`
4. Register in game manager
5. Create command file (optional)

Example:

```python
from ..core.base_game import BaseGame

class MyGame(BaseGame):
    name = "my_game"
    max_players = 5
    
    async def start(self, session, ctx):
        session.state["started"] = True
        await ctx.reply("Game started!")
    
    async def handle_message(self, session, message):
        # Game logic
        pass
    
    async def end(self, session):
        pass
    
    async def timeout(self, session):
        pass

# Register
game_manager.register_game("my_game", MyGame())
```

---

## 🌙 Luna's Game Philosophy

Games should:
- Be **fun and engaging**
- Support **2-5 players** (or 1 for single-player)
- Use **simple controls** (one-word/letter responses)
- Have **clear win conditions**
- Be **quick** (5-15 minute duration)
- Be **replayable** (random questions/riddles)
- Be **memory-light** (session-only state)

---

## Questions?

Refer to specific game files or core components for implementation details.

**Happy gaming! 🌸**
