from __future__ import annotations

from spacebot.commands import CommandContext, register
from spacebot.validation import validate_room_ref, validate_user_id


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
    user_ok, user_error = validate_user_id(user_id)
    if not user_ok:
        return (
            f"Invalid user ID format: {user_id}\n"
            f"{user_error}"
        )

    room_id = ctx.args[1] if len(ctx.args) > 1 else None

    if room_id:
        room_ok, room_error = validate_room_ref(room_id, allow_shorthand_alias=False)
        if not room_ok:
            return (
                f"Invalid room ID format: {room_id}\n"
                f"{room_error}"
            )

    removed = await ctx.db.remove_user_block(user_id, room_id)

    if removed == 0:
        if room_id:
            return f"No block found for {user_id} in {room_id}"
        return f"No blocks found for {user_id}"

    if room_id:
        return f"Unblocked {user_id} from {room_id} ({removed} block removed)"
    return f"Removed {removed} block(s) for {user_id}"
