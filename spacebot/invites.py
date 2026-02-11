from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from spacebot.utils import is_error_response

if TYPE_CHECKING:
    from nio import AsyncClient

    from spacebot.config import Config
    from spacebot.storage import Database


@dataclass
class BotState:
    """Mutable runtime state (ephemeral, not persisted)."""

    startup_time: float = 0.0
    invite_queue: asyncio.Queue[tuple[str, str]] = field(
        default_factory=asyncio.Queue
    )
    queued_users: set[tuple[str, str]] = field(default_factory=set)
    processing_users: set[tuple[str, str]] = field(default_factory=set)
    invite_accept_events: dict[tuple[str, str], asyncio.Event] = field(
        default_factory=dict
    )
    joined_members_by_room: dict[str, set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    sync_count: int = 0
    startup_reconcile_done: bool = False
    room_join_refs: dict[str, str] = field(default_factory=dict)
    cached_space_ids: set[str] = field(default_factory=set)
    cached_target_rooms: set[str] = field(default_factory=set)


async def refresh_room_caches(db: Database, state: BotState) -> None:
    """Refresh cached space and target room sets from the database."""
    state.cached_space_ids = set(await db.get_all_space_ids())
    state.cached_target_rooms = await db.get_all_target_room_ids()
    print(
        f"[cache] refreshed: {len(state.cached_space_ids)} space(s), "
        f"{len(state.cached_target_rooms)} target room(s)"
    )


async def invite_user_to_room(
    client: AsyncClient,
    db: Database,
    user_id: str,
    target_room_id: str,
    source: str,
) -> bool:
    """Invite a user to a room, retrying on rate-limit errors.

    Returns True if the invite succeeded.
    """
    attempt = 0
    while True:
        attempt += 1
        resp = await client.room_invite(target_room_id, user_id)
        if not is_error_response(resp):
            print(f"[invite:{source}] invited {user_id} -> {target_room_id}")
            await db.record_invite(user_id, target_room_id, source, "invited")
            return True

        retry_after_ms = getattr(resp, "retry_after_ms", None)
        if retry_after_ms is not None:
            print(
                f"[invite:{source}] rate-limited {user_id} -> {target_room_id} "
                f"(attempt={attempt}, retry_after_ms={retry_after_ms})"
            )
            await asyncio.sleep(max(retry_after_ms, 1) / 1000)
            continue

        error_detail = str(resp)
        print(f"[invite:{source}] failed {user_id} -> {target_room_id}: {resp}")
        await db.record_invite(
            user_id, target_room_id, source, "failed", error_detail
        )
        return False


def queue_user_for_invites(
    config: Config,
    state: BotState,
    user_id: str,
    space_room_id: str,
    source: str,
) -> None:
    """Add a user to the invite queue for a specific space."""
    if user_id == config.bot_user:
        return
    key = (user_id, space_room_id)
    if key in state.queued_users or key in state.processing_users:
        return
    state.invite_queue.put_nowait(key)
    state.queued_users.add(key)
    print(
        f"[invite-queue:{source}] queued {user_id} for space {space_room_id} "
        f"(pending={state.invite_queue.qsize()})"
    )


async def is_user_joined_in_room(
    client: AsyncClient,
    db: Database,
    state: BotState,
    user_id: str,
    room_id: str,
) -> bool:
    """Check whether a user is already joined in a room."""
    if user_id in state.joined_members_by_room.get(room_id, set()):
        return True

    joined_ids = await fetch_joined_user_ids(
        client, db, state, room_id, f"target {room_id}"
    )
    if joined_ids is None:
        return False

    state.joined_members_by_room[room_id] = set(joined_ids)
    return user_id in state.joined_members_by_room[room_id]


async def wait_for_invite_acceptance(
    config: Config,
    state: BotState,
    user_id: str,
    room_id: str,
) -> bool:
    """Wait for a user to accept an invite to a room.

    Returns True if the user accepted (or was already joined).
    """
    if user_id in state.joined_members_by_room.get(room_id, set()):
        return True

    key = (user_id, room_id)
    event = state.invite_accept_events.get(key)
    if event is None:
        event = asyncio.Event()
        state.invite_accept_events[key] = event

    timeout = config.invite_acceptance_timeout_seconds
    try:
        if timeout > 0:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
                return True
            except asyncio.TimeoutError:
                print(
                    f"[invite-queue] timed out waiting for {user_id} to accept invite "
                    f"to {room_id} (timeout={timeout}s)"
                )
                return False

        await event.wait()
        return True
    finally:
        if state.invite_accept_events.get(key) is event:
            state.invite_accept_events.pop(key, None)


async def process_invite_queue(
    client: AsyncClient,
    config: Config,
    db: Database,
    state: BotState,
) -> None:
    """Background worker that processes the invite queue serially."""
    print("[invite-queue] worker started")
    while True:
        user_id, space_room_id = await state.invite_queue.get()
        key = (user_id, space_room_id)
        state.queued_users.discard(key)
        state.processing_users.add(key)
        try:
            target_rooms = await db.get_target_rooms_for_space(space_room_id)
            if not target_rooms:
                print(
                    f"[invite-queue] no target rooms for space "
                    f"{space_room_id}, skipping {user_id}"
                )
                continue

            print(
                f"[invite-queue] processing {user_id} "
                f"(space={space_room_id}, targets={len(target_rooms)})"
            )
            for target_room_id in target_rooms:
                if not await ensure_joined_room(
                    client, state, target_room_id, f"target {target_room_id}"
                ):
                    print(
                        f"[invite-queue] stopping {user_id}: "
                        f"bot not joined to {target_room_id}"
                    )
                    break

                # Check blocklist
                if await db.is_user_blocked(user_id, target_room_id):
                    print(
                        f"[invite-queue] {user_id} is blocked from "
                        f"{target_room_id}, skipping"
                    )
                    await db.record_invite(
                        user_id, target_room_id, "queue", "skipped",
                        "user is blocked",
                    )
                    continue

                if await is_user_joined_in_room(
                    client, db, state, user_id, target_room_id
                ):
                    print(
                        f"[invite-queue] {user_id} already joined "
                        f"{target_room_id}, skipping"
                    )
                    await db.record_invite(
                        user_id, target_room_id, "queue", "already_joined"
                    )
                    continue

                invited = await invite_user_to_room(
                    client, db, user_id, target_room_id, "queue"
                )
                if not invited:
                    print(
                        f"[invite-queue] stopping {user_id} due to invite failure"
                    )
                    break

                accepted = await wait_for_invite_acceptance(
                    config, state, user_id, target_room_id
                )
                if not accepted:
                    print(
                        f"[invite-queue] stopping {user_id} until next reconcile"
                    )
                    break

            print(f"[invite-queue] done {user_id}")
        finally:
            state.processing_users.discard(key)
            state.invite_queue.task_done()


async def fetch_joined_user_ids(
    client: AsyncClient,
    db: Database,
    state: BotState,
    room_id: str,
    label: str,
) -> set[str] | None:
    """Fetch the set of joined user IDs for a room from the homeserver."""
    resp = await client.joined_members(room_id)
    if is_error_response(resp):
        print(
            f"[reconcile] failed to fetch members for {label} ({room_id}): {resp}"
        )
        return None

    user_ids: set[str] = set()

    members = getattr(resp, "members", None)
    if isinstance(members, list):
        for member in members:
            uid = getattr(member, "user_id", None)
            if uid:
                user_ids.add(uid)

    # Fallback for payloads that expose a raw "joined" mapping.
    joined = getattr(resp, "joined", None)
    if isinstance(joined, dict):
        user_ids.update(str(uid) for uid in joined.keys())

    if not user_ids:
        print(
            f"[reconcile] no joined members parsed for {label} ({room_id}) "
            f"from response type {type(resp).__name__}"
        )

    # Update the membership cache for target rooms
    if room_id in state.cached_target_rooms:
        state.joined_members_by_room[room_id] = set(user_ids)

    print(f"[reconcile] {label} joined_members={len(user_ids)}")
    return user_ids


async def ensure_joined_room(
    client: AsyncClient,
    state: BotState,
    room_id: str,
    label: str,
) -> bool:
    """Ensure the bot is joined to a room, attempting to join if not."""
    if room_id in client.rooms:
        return True

    join_ref = state.room_join_refs.get(room_id, room_id)
    print(
        f"[reconcile] bot is not joined to {label} ({room_id}); "
        f"attempting join via {join_ref}..."
    )
    join_resp = await client.join(join_ref)
    if is_error_response(join_resp):
        print(
            f"[reconcile] cannot join {label} ({room_id}) via {join_ref}: "
            f"{join_resp}"
        )
        return False

    print(f"[reconcile] joined {label} ({room_id})")
    return True


async def ensure_joined_configured_rooms(
    client: AsyncClient,
    db: Database,
    state: BotState,
    source: str,
) -> None:
    """Ensure the bot is joined to all configured rooms (spaces + targets)."""
    all_rooms = await db.get_all_configured_room_ids()
    if not all_rooms:
        print(f"[join:{source}] no configured rooms to join")
        return

    print(f"[join:{source}] ensuring bot joined {len(all_rooms)} configured room(s)")
    joined_count = 0
    for room_id in sorted(all_rooms):
        if await ensure_joined_room(client, state, room_id, room_id):
            joined_count += 1
    print(
        f"[join:{source}] room join check done "
        f"(joined_or_already_joined={joined_count}/{len(all_rooms)})"
    )


async def reconcile_existing_space_members(
    client: AsyncClient,
    config: Config,
    db: Database,
    state: BotState,
    source: str,
) -> None:
    """Scan all configured spaces and queue members who need invites."""
    space_ids = await db.get_all_space_ids()
    if not space_ids:
        print(f"[reconcile:{source}] no autoinvite rules configured, skipping")
        return

    for space_room_id in space_ids:
        if not await ensure_joined_room(
            client, state, space_room_id, f"space {space_room_id}"
        ):
            print(
                f"[reconcile:{source}] skipped space {space_room_id}: "
                f"bot not joined"
            )
            continue

        space_members = await fetch_joined_user_ids(
            client, db, state, space_room_id, f"space {space_room_id}"
        )
        if space_members is None:
            continue

        queued = 0
        for user_id in sorted(space_members):
            if user_id == config.bot_user:
                continue
            key = (user_id, space_room_id)
            if key in state.queued_users or key in state.processing_users:
                continue
            queue_user_for_invites(
                config, state, user_id, space_room_id,
                f"reconcile:{source}",
            )
            queued += 1

        print(
            f"[reconcile:{source}] space {space_room_id}: "
            f"members={len(space_members)}, queued={queued}"
        )
