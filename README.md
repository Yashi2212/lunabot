# LunaBot

Luna is a sweet Discord helper bot that uses cherry blossoms, friendly Gen Z tone, word meaning lookup, and fun English games.

## Access Luna

[Add Luna to your Discord server](https://discord.com/oauth2/authorize?client_id=1518678773229424804)

Open the link, choose your server, and authorize Luna. Once Luna is online, type `luna help` in your server to get started.

## Get Your Discord Bot Token

1. Go to **Discord Developer Portal**: https://discord.com/developers/applications
2. Click **New Application** and name it "Luna"
3. Go to the **Bot** tab on the left
4. Click **Add Bot**
5. Under **TOKEN**, click **Copy** to copy your bot token
6. Save this token safely — you'll need it to run Luna

**Important**: If you see `401 Unauthorized` or `Improper token has been passed`, the token is incorrect.

**Note**: The OAuth2 link you may have seen (like `https://discord.com/oauth2/authorize?client_id=...`) is for **inviting** the bot to servers, not for getting the token. The token comes from the Bot tab.

## Invite Luna to Your Server

### Recommended Permissions (Safe & Smart)

Luna needs **minimal, safe permissions** to function well:

**Essential Permissions:**
- ⚪ `applications.commands` - Optional OAuth scope; select this only if Luna has slash commands such as `/help` or `/ping`
- ✅ `messages.read` - Read messages to respond
- ✅ `messages.send` - Send replies
- ✅ `message_history.read` - Read context from messages
- ✅ `reactions.add` - React with cherry blossoms 🌸

**Optional (for DM support):**
- ⚪ `dm_channels.read` - Allow users to DM Luna
- ⚪ `dm_channels.messages.write` - Reply in DMs

**NOT recommended (Security Risk):**
- ❌ `administrator` - Too powerful
- ❌ `ban_members`, `kick_members` - Unnecessary
- ❌ `manage_messages` - Could delete messages
- ❌ `manage_roles`, `manage_channels` - Unnecessary
- ❌ Any moderation permissions

### Enable Message Content Intent

Because Luna reads message content to detect `luna ...`, you must enable the Message Content Intent in your bot settings.

1. Go to **Discord Developer Portal**: https://discord.com/developers/applications
2. Select your "Luna" application
3. Go to the **Bot** tab
4. Scroll down to **Privileged Gateway Intents**
5. Enable:
   - ✅ `MESSAGE CONTENT INTENT`
6. Save changes

### How to Invite Luna Safely

1. Go to **OAuth2** > **URL Generator**
2. Under **Scopes**, select:
   - ✅ `bot`
3. Under **Permissions**, select:
   - ⚪ applications.commands (optional; Luna currently uses `luna ...` message commands)
   - ✅ messages.read
   - ✅ messages.send
   - ✅ message_history.read
   - ✅ reactions.add
   - ⚪ dm_channels.read (optional)
   - ⚪ dm_channels.messages.write (optional)
4. Copy the generated URL at the bottom
5. Open the URL in your browser
6. Select your Discord server and authorize

**Your generated URL should look like:**
```
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8192&scope=bot,applications.commands
```

(The `permissions` number changes based on what you select)

## Setup

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Set your Discord bot token:

```bash
set DISCORD_TOKEN=YOUR_DISCORD_TOKEN
```

3. **Optional**: Set LLM env vars for commands like `luna quote`, `luna joke`, `luna search`, etc.

Using **Groq API** (recommended for free tier):

```bash
set LUNA_API_URL=https://api.groq.com/openai/v1/chat/completions
set LUNA_API_KEY=YOUR_GROQ_API_KEY
set LUNA_MODEL=openai/gpt-oss-120b
set LUNA_FALLBACK_MODEL=openai/gpt-oss-20b
```

Optional separate game-content models:

```bash
set LUNA_CHERRYWORDS_MODEL=llama-3.1-8b-instant
set LUNA_CHERRYWORDS_FALLBACK_MODEL=openai/gpt-oss-120b
set LUNA_CHERRYGARDEN_MODEL=llama-3.1-8b-instant
set LUNA_CHERRYGARDEN_FALLBACK_MODEL=openai/gpt-oss-120b
```

If the primary model is unavailable or rate-limited, Luna automatically tries `LUNA_FALLBACK_MODEL`. Both model names must be valid for your Groq organization.

CherryWords and CherryGarden use `llama-3.1-8b-instant` first and fall back to `openai/gpt-oss-120b` for game-content generation. CherryWords requests fresh prompts in small validated JSON batches, and CherryGarden generates its ten questions in smaller batches too. Override these with `LUNA_CHERRYWORDS_MODEL`, `LUNA_CHERRYWORDS_FALLBACK_MODEL`, `LUNA_CHERRYGARDEN_MODEL`, and `LUNA_CHERRYGARDEN_FALLBACK_MODEL` if needed. Static CherryWords emergency prompts are disabled by default; enable `LUNA_CHERRYWORDS_ALLOW_STATIC_FALLBACK=1` only when you explicitly accept non-AI prompts.

Or use any compatible OpenAI-style LLM provider.

> Note: On Windows, set the vars in the same terminal session where you run `python run_luna.py` or `python main.py --discord`.

## Run Luna

### CLI greeting

```bash
python main.py --name Alice
```

### Start Discord bot with the built-in launcher

```bash
python main.py --discord
```

### Start Discord bot with the dedicated startup script

```bash
python run_luna.py
```

If you prefer explicit token passing:

```bash
python main.py --discord --token YOUR_DISCORD_TOKEN
```

## Discord commands

Just type `luna` followed by a command or natural-language question. No special prefix needed!

### Available Commands

- `luna help` - Show all available commands with descriptions
- `luna meaning <word>` - Get the meaning and definition of a word
- `luna quote` - Generate an inspirational quote
- `luna joke` - Tell a funny joke
- `luna fact` - Share an interesting fact
- `luna search <topic>` - Search for information on any topic
- `luna story <theme>` - Generate a short story based on a theme
- `luna <message>` - Talk with Luna naturally, for example `luna how to study`
- `luna game` - Show every game and the multiplayer flow
- `luna wordquiz <level>` (alias: `trio`) - Vocabulary quiz with answer explanations
- `luna riddle` - Play one fresh 10-riddle multiplayer round (`2` difficult, `3` moderate, `5` easy)
- `luna jumbled` - Play one fresh 10-word jumbled-word round (`messed` and `jumble` remain aliases)
- `luna memo` - Play one 10-sequence memory round (`memory` remains an alias)
- `luna escape <level>` - Play a rotating learning puzzle room (AI-generated when available)
- `luna trivia <level>` - Create a fastest-answer learning-trivia lobby
- `luna wordle` - Play a six-row Wordle board with green/yellow/black feedback
- `luna storyteller <level>` - Practise collaborative writing
- `luna cherrygarden <level>` - Ten mixed grammar rounds with personalized explanations
- `luna cherrywords <level>` - Create a vocabulary battle lobby
- `luna codenames solo <level>` - Play against Luna on a pastel 5x4 word board
- `luna codenames multi <level>` - Team game with private spymaster boards in DMs
- `luna join` - Join the open lobby in the current channel
- `luna begin` - Start a lobby (host only)
- `luna score` - Show current scores
- `luna hint` - Take one of the two shared riddle hints
- `luna stop` - Stop the current lobby/game (host only)
- `luna spell <word>` - Help with spelling and pronunciation

Games that accept a `<level>` default to 🌱. Use one flower for `<level>`:

- 🌱 Easy
- 🌼 Moderate
- 🌺 Difficult

For example: `luna trivia 🌼`, `luna cherrygarden 🌺`, or `luna codenames 🌼`. Multiplayer Codenames needs at least four players; the first two lobby members become Team A and Team B spymasters.

Use `luna help games` for the complete list, or `luna help <game>` for players, rules, an example, and the learning goal—for example, `luna help wordle` or `luna help escape`.

### Codenames flow

Solo:

```text
luna codenames solo easy
```

Luna gives a clue and number. Reply with a card letter from `A` to `T`, or type `pass`.

Multiplayer:

```text
luna codenames multi hard
luna join
luna join
luna join
luna begin
```

Spymasters receive the colour key privately in DMs. On their team's turn they post `clue <word> <number>` in the common channel; only that team's operatives can select cards. Easy and medium boards have one assassin, while hard boards have two.

Pillow enables the pastel PNG board. If Pillow is unavailable, Luna automatically uses a dependency-free 5x4 text board instead, so the rest of the bot still starts normally.

### Examples

```
luna help
luna meaning serendipity
luna quote
luna joke
luna fact
luna search What is photosynthesis?
luna story A magical forest
luna how to study
luna trivia
luna join
luna begin
luna riddle
luna jumbled
luna memo
luna hint
luna spell beautiful
```

### Features

- 🌸 **Cherry Blossom Reactions** - Luna reacts to every non-bot message with her favourite cherry blossom
- 🤍 **Warm Personality** - Luna uses white hearts in her gentle, cheerful replies without flooding messages
- 🎮 **Eleven Learning Games** - Word games, riddles, jumbles, memory, an escape room, trivia, voting, storytelling, grammar, word battles, and pastel Codenames
- 📖 **Dictionary** - Uses free DictionaryAPI.dev for word meanings
- 💬 **Chat-style fallback** - Ask Luna `luna what is whimsy` or `luna how are you` and she will answer even when no exact command matches
- 🤖 **LLM Integration** - Supports GPT-OSS 120B and Llama 3.3 70B
- 💖 **Sweet Personality** - Cute, friendly, Gen Z style responses

### Fresh game content

Luna asks the language model for new validated Word Quiz, mixed-category Trivia, Riddle, Jumbled, Escape Room, Storyteller, Would You Rather, CherryGarden, CherryWords, and Codenames content. Trivia combines geography, history, general knowledge, countries, world facts, and basic everyday facts. Invalid or repeated AI output is discarded automatically. Escape rotates through six local learning rooms when AI is unavailable or repeats. Each Riddle and Jumbled game loads exactly 10 fresh items: 2 Difficult, 3 Moderate, and 5 Easy. Jumbled gives every challenge a 30-second answer window. CherryWords requests 30 fresh AI sequences in three smaller batches, and CherryGarden requests its ten mixed grammar questions in smaller batches; both refuse to start when they cannot obtain enough validated AI content. A static CherryWords emergency bank exists only when `LUNA_CHERRYWORDS_ALLOW_STATIC_FALLBACK=1`.

Memo plays exactly 10 five-emoji sequences with the same 2 Difficult, 3 Moderate, and 5 Easy distribution. Each sequence hides after 7 seconds on Easy, 5 seconds on Moderate, or 3 seconds on Difficult. Players react to the emoji choice for positions 1 through 5 in order.

Escape Room now rotates between multiple interactive locations. Use `look`, `search`, `take <item>`, `inspect <item>`, `inventory`, `hint`, and `solve <answer>`.

Luna's personality and romantic boundaries are defined centrally in `lunabot/persona.py`. She uses a calm, encouraging voice, moderate emoji, dry humour, and firm non-romantic responses.

Casual chat and questions about Luna stay short and charming, usually under 80 words. Searches, definitions, stories, and explicit teaching requests may be longer, but every generated response is capped at 300 words. Bedtime requests receive a small gesture and rotating four-line lullaby.

Any unknown `luna ...` text is treated as conversation rather than a broken command, so `luna hi` and `luna how was your day?` receive chat replies. Users can also reply directly to one of Luna's Discord messages to continue chatting without typing `luna` again; active game answers still take priority.

### LLM-Powered Commands

If you set `LUNA_API_URL` and `LUNA_API_KEY`, these commands become available:

- `luna quote` - Generates inspirational quotes
- `luna joke` - Tells funny jokes
- `luna fact` - Shares interesting facts
- `luna search <topic>` - Searches and provides info
- `luna story <theme>` - Generates short stories
- `luna <message>` - General conversation, such as `luna how to study`
- `luna spell <word>` - Helps with spelling and pronunciation

## Verify Luna is working

1. Run the bot:

```bash
python run_luna.py
```

or

```bash
python main.py --discord
```

2. Invite Luna to a Discord server (see "Invite Luna to Your Server" above)

3. In Discord, test the basic commands (no LLM required):

```
luna help                    (shows all commands)
luna meaning serendipity     (looks up word meaning)
luna wordquiz                (starts a local multiple-choice quiz)
```

Luna should:
- React with 🌸 to every message
- Reply with cute, friendly responses
- Show command descriptions in `luna help`

4. **Optional**: Test LLM commands if you set the API vars:

```
luna quote
luna joke
luna search What is photosynthesis?
```
