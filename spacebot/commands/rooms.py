from __future__ import annotations

from spacebot.commands import CommandContext, register
from spacebot.utils import is_error_response


@register("rooms", "List configured autoinvite rooms", "!!rooms")
async def cmd_rooms(ctx: CommandContext) -> str:
    rules = await ctx.db.get_autoinvite_rules()
    if not rules:
        return (
            "No autoinvite rules configured.\n"
            f"Use {ctx.config.command_prefix}autoinvite add <space> <room> "
            f"to create one."
        )

    # Group rules by space
    spaces: dict[str, list[str]] = {}
    for space_id, target_id, _added_by, _created_at in rules:
        spaces.setdefault(space_id, []).append(target_id)

    lines = [f"Configured Rooms ({len(rules)} rule(s)):", ""]

    for space_id, target_ids in spaces.items():
        lines.append(f"  Space: {await _room_label(ctx, space_id)}")
        lines.append(f"  Auto-invite rooms ({len(target_ids)}):")
        for target_id in target_ids:
            lines.append(f"    - {await _room_label(ctx, target_id)}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _room_display_name(ctx: CommandContext, room_id: str) -> str:
    """Get a friendly display name for a room."""
    room = ctx.client.rooms.get(room_id)
    if room is None:
        return room_id

    # Prefer explicit room metadata over computed display names such as
    # "Empty Room", which matrix-nio can synthesize for unnamed rooms.
    name = getattr(room, "name", None)
    if name:
        return name

    alias = getattr(room, "canonical_alias", None)
    if alias:
        return alias

    # If this room was configured via alias, show that as a friendlier label.
    join_ref = ctx.bot_state.room_join_refs.get(room_id)
    if join_ref and join_ref.startswith("#"):
        return join_ref

    display_name = getattr(room, "display_name", None)
    if display_name and display_name != room_id:
        return display_name

    return room_id


async def _room_label(ctx: CommandContext, room_id: str) -> str:
    """Build a user-facing label as '<room name>, <room alias>' when possible."""
    room = ctx.client.rooms.get(room_id)

    name = getattr(room, "name", None) if room else None
    alias = getattr(room, "canonical_alias", None) if room else None

    # If this room was configured via alias, prefer that alias as a fallback.
    if not alias:
        join_ref = ctx.bot_state.room_join_refs.get(room_id)
        if join_ref and join_ref.startswith("#"):
            alias = join_ref

    # If metadata is missing in cache, ask the homeserver for state events.
    if not name:
        name_resp = await ctx.client.room_get_state_event(room_id, "m.room.name")
        if not is_error_response(name_resp):
            content = getattr(name_resp, "content", None)
            if isinstance(content, dict):
                name = content.get("name") or name
            elif isinstance(name_resp, dict):
                name = name_resp.get("name") or name

    if not alias:
        alias_resp = await ctx.client.room_get_state_event(
            room_id, "m.room.canonical_alias"
        )
        if not is_error_response(alias_resp):
            content = getattr(alias_resp, "content", None)
            if isinstance(content, dict):
                alias = content.get("alias") or alias
            elif isinstance(alias_resp, dict):
                alias = alias_resp.get("alias") or alias

    if name and alias:
        return f"{name}, {alias}"
    if name:
        return name
    if alias:
        return alias

    display_name = _room_display_name(ctx, room_id)
    if display_name != room_id and display_name != "Empty Room":
        return display_name
    return room_id
