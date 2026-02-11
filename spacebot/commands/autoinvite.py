from __future__ import annotations

from spacebot.commands import CommandContext, register, send_notice
from spacebot.invites import (
    ensure_joined_configured_rooms,
    ensure_joined_room,
    refresh_room_caches,
)
from spacebot.utils import is_error_response, resolve_room_ref


@register(
    "autoinvite",
    "Manage autoinvite rules (add/remove/list)",
    "!!autoinvite <add|remove|list> [space] [room]",
)
async def cmd_autoinvite(ctx: CommandContext) -> str:
    if not ctx.args:
        return (
            f"Usage:\n"
            f"  {ctx.config.command_prefix}autoinvite add <space> <room>\n"
            f"  {ctx.config.command_prefix}autoinvite remove <space> <room>\n"
            f"  {ctx.config.command_prefix}autoinvite list"
        )

    subcommand = ctx.args[0].lower()

    if subcommand == "add":
        return await _handle_add(ctx)
    elif subcommand == "remove":
        return await _handle_remove(ctx)
    elif subcommand == "list":
        return await _handle_list(ctx)
    else:
        return (
            f"Unknown subcommand: {subcommand}\n"
            f"Use add, remove, or list."
        )


def _server_name(ctx: CommandContext) -> str | None:
    """Extract the server name from the bot's user ID."""
    bot_user = ctx.config.bot_user
    if ":" in bot_user:
        return bot_user.split(":", 1)[1]
    return None


def _expand_ref(ref: str, server_name: str | None) -> str:
    """Expand a shorthand alias (#foo) to a full alias (#foo:server).

    Returns the ref unchanged if it already contains a server component.
    """
    if ref.startswith("#") and ":" not in ref and server_name:
        return f"{ref}:{server_name}"
    return ref


async def _handle_add(ctx: CommandContext) -> str:
    if len(ctx.args) < 3:
        return (
            f"Usage: {ctx.config.command_prefix}autoinvite add <space> <room>\n"
            f"Example: {ctx.config.command_prefix}autoinvite add "
            f"#myspace #general"
        )

    sn = _server_name(ctx)
    space_ref = _expand_ref(ctx.args[1], sn)
    target_ref = _expand_ref(ctx.args[2], sn)

    # Resolve space reference
    space_id = await resolve_room_ref(ctx.client, space_ref, "space", server_name=sn)
    if not space_id:
        return f"Could not resolve space: {space_ref}"

    # Resolve target room reference
    target_id = await resolve_room_ref(ctx.client, target_ref, "target room", server_name=sn)
    if not target_id:
        return f"Could not resolve target room: {target_ref}"

    # Store the rule
    created = await ctx.db.add_autoinvite_rule(
        space_id, target_id, added_by=ctx.sender
    )
    if not created:
        return (
            f"Rule already exists: {space_id} -> {target_id}"
        )

    # Store join refs for alias resolution (full alias, not shorthand)
    if space_id != space_ref:
        ctx.bot_state.room_join_refs[space_id] = space_ref
    if target_id != target_ref:
        ctx.bot_state.room_join_refs[target_id] = target_ref

    # Refresh caches and join rooms
    await refresh_room_caches(ctx.db, ctx.bot_state)
    await ensure_joined_room(ctx.client, ctx.bot_state, space_id, "space")
    await ensure_joined_room(ctx.client, ctx.bot_state, target_id, "target")

    # Get display names
    space_name = await _room_label(ctx, space_id)
    target_name = await _room_label(ctx, target_id)

    return (
        f"Added autoinvite rule:\n"
        f"  Space: {space_name}\n"
        f"  Target: {target_name}\n"
        f"Users joining the space will now be invited to the target room."
    )


async def _handle_remove(ctx: CommandContext) -> str:
    if len(ctx.args) < 3:
        return (
            f"Usage: {ctx.config.command_prefix}autoinvite remove <space> <room>\n"
            f"Example: {ctx.config.command_prefix}autoinvite remove "
            f"#myspace #general"
        )

    sn = _server_name(ctx)
    space_ref = _expand_ref(ctx.args[1], sn)
    target_ref = _expand_ref(ctx.args[2], sn)

    # Resolve references
    space_id = await resolve_room_ref(ctx.client, space_ref, "space", server_name=sn)
    if not space_id:
        return f"Could not resolve space: {space_ref}"

    target_id = await resolve_room_ref(ctx.client, target_ref, "target room", server_name=sn)
    if not target_id:
        return f"Could not resolve target room: {target_ref}"

    removed = await ctx.db.remove_autoinvite_rule(space_id, target_id)
    if not removed:
        return f"No matching rule found for {space_id} -> {target_id}"

    # Refresh caches
    await refresh_room_caches(ctx.db, ctx.bot_state)

    return f"Removed autoinvite rule: {space_id} -> {target_id}"


async def _handle_list(ctx: CommandContext) -> str:
    rules = await ctx.db.get_autoinvite_rules()
    if not rules:
        return (
            "No autoinvite rules configured.\n"
            f"Use {ctx.config.command_prefix}autoinvite add <space> <room> "
            f"to create one."
        )

    # Group rules by space
    spaces: dict[str, list[tuple[str, str | None, str]]] = {}
    for space_id, target_id, added_by, created_at in rules:
        spaces.setdefault(space_id, []).append(
            (target_id, added_by, created_at)
        )

    lines = [f"Autoinvite Rules ({len(rules)} total):", ""]

    for space_id, targets in spaces.items():
        lines.append(f"  Space: {await _room_label(ctx, space_id)}")
        lines.append(f"  Target rooms ({len(targets)}):")
        for target_id, added_by, created_at in targets:
            target_name = await _room_label(ctx, target_id)
            who = f" (added by {added_by})" if added_by else ""
            lines.append(f"    - {target_name}{who}")
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
