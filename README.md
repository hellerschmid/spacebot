# spacebot

Matrix bot that automatically invites users to rooms when they join a Space.

## Getting Started

```bash
uv sync
uv run python -m spacebot
```

## Generate Version File

Current Version: `0.3.1.896`

Generate a `.version` file at the project root from the latest git commit time:

```bash
uv run python -m spacebot.versioning
```

Optional flags:

```bash
uv run python -m spacebot.versioning --major 1 --minor 0 --project-start-date 2026-02-10 --output .version
```

## Docker Deploy

### 1) Create a `.env`

Create a `.env` file next to your `docker-compose.yml`:

```env
# Required
MATRIX_HOMESERVER=https://matrix.example.com
MATRIX_USER=@spacebot:example.com
MATRIX_PASSWORD=REPLACE_ME

# Optional (defaults shown in README)
RECONCILE_INTERVAL_CYCLES=20
LOGIN_MAX_RETRIES=5
INVITE_ACCEPTANCE_TIMEOUT_SECONDS=0
SPACEBOT_COMMAND_PREFIX=!!
SPACEBOT_COMMAND_MIN_POWER_LEVEL=50

# Recommended for persistence
SPACEBOT_DB_PATH=/data/spacebot.db
```

### 2) Create a `docker-compose.yml`

```yaml
services:
  spacebot:
    image: hellerschmid/spacebot:latest
    container_name: spacebot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./spacebot-data:/data
```

### 3) Start

```bash
docker compose up -d
```

Logs:

```bash
docker compose logs -f spacebot
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `MATRIX_HOMESERVER` | URL of your Matrix homeserver | `https://matrix.example.com` |
| `MATRIX_USER` | Bot's full Matrix user ID | `@spacebot:example.com` |
| `MATRIX_PASSWORD` | Bot account password | |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `RECONCILE_INTERVAL_CYCLES` | Number of sync cycles between full member reconciliation. Set to `0` to disable periodic reconciliation. | `20` |
| `LOGIN_MAX_RETRIES` | Maximum login attempts before giving up. Set to `0` for unlimited retries. | `5` |
| `INVITE_ACCEPTANCE_TIMEOUT_SECONDS` | Seconds to wait for a user to accept an invite before moving on. Set to `0` to wait indefinitely. | `0` |
| `SPACEBOT_DB_PATH` | Path to the SQLite database file for persistent storage. | `spacebot.db` |
| `SPACEBOT_COMMAND_PREFIX` | Prefix for bot commands in chat. | `!!` |
| `SPACEBOT_COMMAND_MIN_POWER_LEVEL` | Minimum Matrix power level required for restricted commands. | `50` |

## Bot Commands

Send these in any room the bot is in (when no rules are configured) or in any configured space/target room:

| Command | Description |
|---------|-------------|
| `!!help` | List all available commands |
| `!!status` | Show bot uptime, queue size, invite statistics |
| `!!invite <user_id> [space_id]` | Manually queue a user for invites. Omit space to queue for all spaces. |
| `!!rooms` | List configured autoinvite rules |
| `!!autoinvite add <space> <room>` | Add an autoinvite rule (space members get invited to room) |
| `!!autoinvite remove <space> <room>` | Remove an autoinvite rule |
| `!!autoinvite list` | List all autoinvite rules grouped by space |
| `!!unblock <user_id> [room_id]` | Remove a user from the blocklist. Omit room to clear all blocks. |

Command access control:

- `!!help` and `!!status` are public.
- All other commands are restricted to moderator/admin users.
- Authorization is granted when the sender has power level >= `SPACEBOT_COMMAND_MIN_POWER_LEVEL` in the current room or in any configured Space.

## Autoinvite System

Instead of hardcoding spaces and rooms in environment variables, spacebot uses a database-driven autoinvite system:

1. **Start the bot** with just the three required env vars (`MATRIX_HOMESERVER`, `MATRIX_USER`, `MATRIX_PASSWORD`)
2. **Invite the bot** to the rooms it needs to manage
3. **Configure rules** using `!!autoinvite add <space> <room>` — the bot will then monitor that space and auto-invite new members to the target room
4. **Multiple spaces** are supported — each space can have its own set of target rooms

### Blocklist

When a user **leaves or is banned** from a target room, they are automatically added to a blocklist for that room. This prevents the bot from re-inviting users who don't want to be in a room.

- Blocks are permanent until manually cleared
- Use `!!unblock <user_id>` to remove all blocks for a user
- Use `!!unblock <user_id> <room_id>` to remove a specific block

## Code Rabbit Reviews

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/hellerschmid/spacebot?utm_source=oss&utm_medium=github&utm_campaign=hellerschmid%2Fspacebot&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)
