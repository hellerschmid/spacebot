from __future__ import annotations

from typing import TYPE_CHECKING

from nio import AsyncClient, InviteMemberEvent, RoomMemberEvent, RoomMessageText

from spacebot.commands import CommandContext, dispatch
from spacebot.invites import (
    BotState,
    ensure_joined_configured_rooms,
    queue_user_for_invites,
)
from spacebot.utils import is_error_response

if TYPE_CHECKING:
    from spacebot.config import Config
    from spacebot.storage import Database


def create_callbacks(
    client: AsyncClient,
    config: Config,
    db: Database,
    state: BotState,
) -> None:
    """Register all event callbacks on the nio client."""

    async def on_member_event(room, event: RoomMemberEvent) -> None:
        user_id = event.state_key

        # Track joins/leaves in target rooms for the membership cache
        if room.room_id in state.cached_target_rooms and user_id:
            if event.membership == "join":
                state.joined_members_by_room[room.room_id].add(user_id)
                waiter = state.invite_accept_events.get(
                    (user_id, room.room_id)
                )
                if waiter:
                    waiter.set()
            elif event.membership in {"leave", "ban"}:
                state.joined_members_by_room[room.room_id].discard(user_id)

                # Add to blocklist so user is not auto-reinvited
                if user_id != config.bot_user:
                    reason = event.membership  # 'leave' or 'ban'
                    await db.add_user_block(user_id, room.room_id, reason)
                    print(
                        f"[blocklist] blocked {user_id} from "
                        f"{room.room_id} (reason={reason})"
                    )

        # Only queue invites for monitored space rooms
        if room.room_id not in state.cached_space_ids:
            return

        # Deduplicate
        if await db.is_event_seen(event.event_id):
            return
        await db.mark_event_seen(
            event.event_id,
            "member",
            room.room_id,
            event.state_key,
            event.server_timestamp,
        )

        # Only act on joins
        if event.membership != "join":
            return

        if user_id == config.bot_user:
            return

        print(
            f"[space] {user_id} joined space {room.room_id} "
            f"-> queued for invites"
        )
        queue_user_for_invites(
            config, state, user_id, room.room_id, "join-event"
        )

    async def on_invite_event(room, event: InviteMemberEvent) -> None:
        # Only auto-accept invites where this bot is the target
        if event.state_key != config.bot_user:
            return

        event_id = getattr(event, "event_id", None)
        if event_id and await db.is_event_seen(event_id):
            return
        if event_id:
            await db.mark_event_seen(
                event_id,
                "invite",
                room.room_id,
                getattr(event, "sender", None),
                getattr(event, "server_timestamp", 0),
            )

        room_id = room.room_id
        inviter = getattr(event, "sender", "unknown")
        print(f"[invite] invited by {inviter} to {room_id} -> joining...")
        join_resp = await client.join(room_id)
        if is_error_response(join_resp):
            print(f"[invite] join failed for {room_id}: {join_resp}")
        else:
            print(f"[invite] joined {room_id}")
            if room_id in state.cached_space_ids:
                await ensure_joined_configured_rooms(
                    client, db, state, "space-invite"
                )

    async def on_message_event(room, event: RoomMessageText) -> None:
        # Ignore our own messages
        if event.sender == config.bot_user:
            return

        # Only process command messages
        if not event.body.startswith(config.command_prefix):
            return

        # Ignore messages from before this bot session (initial sync replay)
        if event.server_timestamp < state.startup_time * 1000:
            return

        # Deduplicate
        if await db.is_event_seen(event.event_id):
            return
        await db.mark_event_seen(
            event.event_id,
            "message",
            room.room_id,
            event.sender,
            event.server_timestamp,
        )

        ctx = CommandContext(
            room_id=room.room_id,
            sender=event.sender,
            event_id=event.event_id,
            args=[],
            raw_body=event.body,
            client=client,
            config=config,
            db=db,
            bot_state=state,
        )
        await dispatch(ctx)

    # Register all callbacks
    client.add_event_callback(on_member_event, RoomMemberEvent)
    client.add_event_callback(on_invite_event, InviteMemberEvent)
    client.add_event_callback(on_message_event, RoomMessageText)
    print("[connect] callback registered for RoomMemberEvent")
    print("[connect] callback registered for InviteMemberEvent")
    print("[connect] callback registered for RoomMessageText")
