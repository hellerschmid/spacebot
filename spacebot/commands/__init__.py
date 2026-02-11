from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable

from spacebot.authz import is_authorized_for_commands

if TYPE_CHECKING:
    from nio import AsyncClient

    from spacebot.config import Config
    from spacebot.invites import BotState
    from spacebot.storage import Database


@dataclass
class CommandContext:
    """Context object passed to every command handler."""

    room_id: str
    sender: str
    event_id: str
    args: list[str]
    raw_body: str
    client: AsyncClient
    config: Config
    db: Database
    bot_state: BotState


@dataclass
class Command:
    """A registered bot command."""

    name: str
    description: str
    usage: str
    handler: Callable[[CommandContext], Awaitable[str | None]]
    admin_only: bool = False
    public: bool = False


# Command registry
_commands: dict[str, Command] = {}


def register(
    name: str,
    description: str,
    usage: str,
    admin_only: bool = False,
    public: bool = False,
) -> Callable:
    """Decorator to register a command handler function."""

    def decorator(
        func: Callable[[CommandContext], Awaitable[str | None]],
    ) -> Callable[[CommandContext], Awaitable[str | None]]:
        _commands[name] = Command(
            name=name,
            description=description,
            usage=usage,
            handler=func,
            admin_only=admin_only,
            public=public,
        )
        return func

    return decorator


def get_all_commands() -> dict[str, Command]:
    """Return a copy of the command registry."""
    return dict(_commands)


async def send_notice(client: AsyncClient, room_id: str, text: str) -> None:
    """Send a response as m.notice (bot convention to prevent loops)."""
    await client.room_send(
        room_id,
        "m.room.message",
        {"msgtype": "m.notice", "body": text},
    )


async def dispatch(ctx: CommandContext) -> None:
    """Parse a command message and invoke the appropriate handler."""
    prefix = ctx.config.command_prefix
    body = ctx.raw_body.strip()

    if not body.startswith(prefix):
        return

    remainder = body[len(prefix):]
    parts = remainder.split(maxsplit=1)
    command_name = parts[0].lower() if parts else ""

    try:
        ctx.args = shlex.split(parts[1]) if len(parts) > 1 else []
    except ValueError:
        # Fall back to simple split if shlex fails (unmatched quotes, etc.)
        ctx.args = parts[1].split() if len(parts) > 1 else []

    cmd = _commands.get(command_name)
    if cmd is None:
        response = f"Unknown command: {prefix}{command_name}. Try {prefix}help"
        await send_notice(ctx.client, ctx.room_id, response)
        return

    if not cmd.public:
        if not await is_authorized_for_commands(ctx):
            await send_notice(
                ctx.client,
                ctx.room_id,
                (
                    "Not authorized. Moderator/admin required "
                    f"(power level >= {ctx.config.command_min_power_level})."
                ),
            )
            return

    try:
        response = await cmd.handler(ctx)
        if response:
            await send_notice(ctx.client, ctx.room_id, response)
    except Exception as exc:
        print(f"[commands] error in {prefix}{command_name}: {exc!r}")
        await send_notice(
            ctx.client,
            ctx.room_id,
            f"Error executing {prefix}{command_name}: {exc}",
        )


def load_commands() -> None:
    """Import all command modules to trigger their @register decorators."""
    import spacebot.commands.autoinvite  # noqa: F401
    import spacebot.commands.help  # noqa: F401
    import spacebot.commands.invite  # noqa: F401
    import spacebot.commands.rooms  # noqa: F401
    import spacebot.commands.status  # noqa: F401
    import spacebot.commands.unblock  # noqa: F401
