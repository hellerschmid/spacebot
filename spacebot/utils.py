from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nio import AsyncClient


def is_error_response(resp: object) -> bool:
    """Check whether a matrix-nio response object represents an error."""
    status_code = getattr(resp, "status_code", None)
    if isinstance(status_code, int):
        return status_code >= 400
    if isinstance(status_code, str):
        return True
    if getattr(resp, "errcode", None):
        return True
    return type(resp).__name__.endswith("Error")


def summarize_sync_activity(sync_resp: object) -> str:
    """Build a compact summary of server activity for a sync cycle."""
    rooms = getattr(sync_resp, "rooms", None)
    if rooms is None:
        return "no rooms payload"

    joined_rooms = getattr(rooms, "join", {}) or {}
    invited_rooms = getattr(rooms, "invite", {}) or {}
    left_rooms = getattr(rooms, "leave", {}) or {}

    event_types: Counter[str] = Counter()

    for room_info in joined_rooms.values():
        timeline = getattr(room_info, "timeline", None)
        events = getattr(timeline, "events", []) or []
        for event in events:
            source = getattr(event, "source", {}) or {}
            event_type = source.get("type", type(event).__name__)
            event_types[event_type] += 1

    if not event_types:
        return (
            f"joined_rooms={len(joined_rooms)} "
            f"invited_rooms={len(invited_rooms)} "
            f"left_rooms={len(left_rooms)} "
            "events=none"
        )

    top_types = ", ".join(
        f"{event_type}={count}"
        for event_type, count in event_types.most_common(8)
    )
    return (
        f"joined_rooms={len(joined_rooms)} "
        f"invited_rooms={len(invited_rooms)} "
        f"left_rooms={len(left_rooms)} "
        f"events: {top_types}"
    )


async def resolve_room_ref(
    client: AsyncClient,
    room_ref: str,
    label: str,
    server_name: str | None = None,
) -> str | None:
    """Resolve a room reference (ID, alias, or shorthand) to a room ID.

    Supports three formats:
      - ``!room_id:server``  — returned as-is
      - ``#alias:server``    — resolved via the homeserver
      - ``#alias`` (shorthand) — expanded to ``#alias:server_name``,
        then resolved.  Requires *server_name* to be provided.
    """
    if room_ref.startswith("!"):
        return room_ref

    if room_ref.startswith("#"):
        # Expand shorthand alias (no ':') using the bot's server name
        if ":" not in room_ref:
            if not server_name:
                print(
                    f"[config] shorthand alias {room_ref} cannot be expanded "
                    f"(no server name available). Use #alias:server instead."
                )
                return None
            expanded = f"{room_ref}:{server_name}"
            print(f"[config] expanded {room_ref} -> {expanded}")
            room_ref = expanded

        print(f"[config] resolving {label} alias {room_ref}...")
        resolve_resp = await client.room_resolve_alias(room_ref)
        if is_error_response(resolve_resp):
            print(
                f"[config] failed to resolve alias {room_ref}: {resolve_resp}"
            )
            return None
        resolved_room_id = getattr(resolve_resp, "room_id", None)
        if not resolved_room_id:
            print(
                f"[config] alias resolved without room_id for "
                f"{room_ref}: {resolve_resp}"
            )
            return None
        print(f"[config] resolved {room_ref} -> {resolved_room_id}")
        return resolved_room_id

    if room_ref.startswith("@"):
        print(
            f"[config] invalid {label}: {room_ref}. "
            "This looks like a user ID; "
            "use !room_id:server, #alias:server, or #alias."
        )
        return None

    print(
        f"[config] invalid {label}: {room_ref}. "
        "Use !room_id:server, #alias:server, or #alias."
    )
    return None
