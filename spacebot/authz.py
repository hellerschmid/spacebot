from __future__ import annotations

from typing import TYPE_CHECKING

from spacebot.utils import is_error_response

if TYPE_CHECKING:
    from nio import AsyncClient

    from spacebot.commands import CommandContext


def _extract_power_from_content(content: object, user_id: str) -> int | None:
    """Extract the user's power level from a power-level state content dict."""
    if not isinstance(content, dict):
        return None

    users = content.get("users", {})
    users_default = content.get("users_default", 0)

    if not isinstance(users, dict):
        users = {}

    try:
        if user_id in users:
            return int(users[user_id])
        return int(users_default)
    except (TypeError, ValueError):
        return None


def _extract_power_from_room_cache(client: AsyncClient, room_id: str, user_id: str) -> int | None:
    """Read power level from matrix-nio room cache if available."""
    room = client.rooms.get(room_id)
    if room is None:
        return None

    power_levels = getattr(room, "power_levels", None)
    if power_levels is None:
        return None

    users = getattr(power_levels, "users", None)
    if isinstance(users, dict) and user_id in users:
        try:
            return int(users[user_id])
        except (TypeError, ValueError):
            return None

    defaults = getattr(power_levels, "defaults", None)
    users_default = getattr(defaults, "users_default", 0)
    try:
        return int(users_default)
    except (TypeError, ValueError):
        return None


async def get_user_power_level(
    client: AsyncClient, room_id: str, user_id: str
) -> int | None:
    """Get a user's power level for a room, using cache first and API fallback."""
    cached_level = _extract_power_from_room_cache(client, room_id, user_id)
    if cached_level is not None:
        return cached_level

    response = await client.room_get_state_event(room_id, "m.room.power_levels")
    if is_error_response(response):
        return None

    content = getattr(response, "content", None)
    parsed = _extract_power_from_content(content, user_id)
    if parsed is not None:
        return parsed

    # Fallback for homeservers/clients that flatten response attributes.
    return _extract_power_from_content(response, user_id)


async def is_authorized_for_commands(ctx: CommandContext) -> bool:
    """Check if sender is moderator/admin in current room or configured spaces."""
    rooms_to_check = {ctx.room_id}
    rooms_to_check.update(await ctx.db.get_all_space_ids())

    min_level = ctx.config.command_min_power_level

    for room_id in rooms_to_check:
        level = await get_user_power_level(ctx.client, room_id, ctx.sender)
        if level is not None and level >= min_level:
            return True

    return False
