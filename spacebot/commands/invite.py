from __future__ import annotations

from spacebot.commands import CommandContext, register
from spacebot.invites import queue_user_for_invites


@register(
    "invite",
    "Manually invite a user to target rooms",
    "!!invite <user_id> [space_id]",
)
async def cmd_invite(ctx: CommandContext) -> str:
    if not ctx.args:
        return (
            f"Usage: {ctx.config.command_prefix}invite <user_id> [space_id]\n"
            f"Omit space_id to queue for all configured spaces.\n"
            f"Example: {ctx.config.command_prefix}invite @alice:matrix.org\n"
            f"Example: {ctx.config.command_prefix}invite @alice:matrix.org !space:matrix.org"
        )

    user_id = ctx.args[0]
    if not user_id.startswith("@") or ":" not in user_id:
        return (
            f"Invalid user ID format: {user_id}\n"
            "Must be like @user:server.com"
        )

    # Optional space filter
    space_filter = ctx.args[1] if len(ctx.args) > 1 else None

    if space_filter:
        # Queue for a specific space
        target_rooms = await ctx.db.get_target_rooms_for_space(space_filter)
        if not target_rooms:
            return f"No autoinvite rules found for space {space_filter}"
        queue_user_for_invites(
            ctx.config,
            ctx.bot_state,
            user_id,
            space_filter,
            f"manual:{ctx.sender}",
        )
        return (
            f"Queued {user_id} for invites to "
            f"{len(target_rooms)} room(s) in space {space_filter}."
        )

    # Queue for all configured spaces
    space_ids = await ctx.db.get_all_space_ids()
    if not space_ids:
        return (
            "No autoinvite rules configured.\n"
            f"Use {ctx.config.command_prefix}autoinvite add <space> <room> "
            f"to create one."
        )

    queued_count = 0
    for space_id in space_ids:
        queue_user_for_invites(
            ctx.config,
            ctx.bot_state,
            user_id,
            space_id,
            f"manual:{ctx.sender}",
        )
        queued_count += 1

    return (
        f"Queued {user_id} for invites across "
        f"{queued_count} space(s)."
    )
