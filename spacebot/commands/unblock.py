from __future__ import annotations

from spacebot.commands import CommandContext, register


@register(
    "unblock",
    "Remove a user from the autoinvite blocklist",
    "!!unblock <user_id> [room_id]",
)
async def cmd_unblock(ctx: CommandContext) -> str:
    if not ctx.args:
        return (
            f"Usage: {ctx.config.command_prefix}unblock <user_id> [room_id]\n"
            f"Omit room_id to clear all blocks for the user.\n"
            f"Example: {ctx.config.command_prefix}unblock @alice:matrix.org\n"
            f"Example: {ctx.config.command_prefix}unblock @alice:matrix.org !abc:matrix.org"
        )

    user_id = ctx.args[0]
    if not user_id.startswith("@") or ":" not in user_id:
        return (
            f"Invalid user ID format: {user_id}\n"
            "Must be like @user:server.com"
        )

    room_id = ctx.args[1] if len(ctx.args) > 1 else None

    if room_id:
        colon_index = room_id.find(":")
        has_valid_prefix = room_id.startswith("!") or room_id.startswith("#")
        has_server = colon_index > 0 and bool(room_id[colon_index + 1 :])
        if not (has_valid_prefix and has_server):
            return (
                f"Invalid room ID format: {room_id}\n"
                "Must be like !room_id:server or #alias:server"
            )

    removed = await ctx.db.remove_user_block(user_id, room_id)

    if removed == 0:
        if room_id:
            return f"No block found for {user_id} in {room_id}"
        return f"No blocks found for {user_id}"

    if room_id:
        return f"Unblocked {user_id} from {room_id} ({removed} block removed)"
    return f"Removed {removed} block(s) for {user_id}"
