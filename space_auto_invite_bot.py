import os
import asyncio
from typing import Set

from nio import AsyncClient, RoomMemberEvent

HOMESERVER = os.environ["MATRIX_HOMESERVER"]          # e.g. https://matrix.yourdomain.com
BOT_USER = os.environ["MATRIX_USER"]                 # e.g. @spacebot:yourdomain.com
BOT_PASSWORD = os.environ["MATRIX_PASSWORD"]
SPACE_ROOM_ID = os.environ["SPACE_ROOM_ID"]          # !xxxxx:yourdomain.com
AUTO_INVITE_ROOMS = [r.strip() for r in os.environ["AUTO_INVITE_ROOMS"].split(",") if r.strip()]

# matrix-nio callbacks can sometimes fire duplicates; track event IDs we processed.
# (Persisting this is optional; in-memory is fine for most small communities.)
SEEN_EVENT_IDS: Set[str] = set()


async def on_member_event(room, event: RoomMemberEvent) -> None:
    # Only act on the Space room
    if room.room_id != SPACE_ROOM_ID:
        return

    # Deduplicate
    if event.event_id in SEEN_EVENT_IDS:
        return
    SEEN_EVENT_IDS.add(event.event_id)

    # We only care when someone JOINs the space
    if event.membership != "join":
        return

    user_id = event.state_key  # the user whose membership changed
    if user_id == BOT_USER:
        return

    print(f"[space] {user_id} joined {SPACE_ROOM_ID} -> inviting to {AUTO_INVITE_ROOMS}")

    for target_room_id in AUTO_INVITE_ROOMS:
        resp = await client.room_invite(target_room_id, user_id)
        if hasattr(resp, "transport_response") and resp.transport_response:
            # in case you want status codes, etc.
            pass
        if getattr(resp, "status_code", 200) >= 400:
            print(f"  invite failed: {user_id} -> {target_room_id}: {resp}")
        else:
            print(f"  invited: {user_id} -> {target_room_id}")


async def main() -> None:
    global client
    client = AsyncClient(HOMESERVER, BOT_USER)

    # Login (stores an access token in memory)
    login_resp = await client.login(BOT_PASSWORD)
    if getattr(login_resp, "status_code", 200) >= 400:
        raise RuntimeError(f"Login failed: {login_resp}")

    # Listen for membership changes (join/leave/invite/ban) in synced rooms
    client.add_event_callback(on_member_event, RoomMemberEvent)

    # Sync loop
    while True:
        await client.sync(timeout=30_000)  # 30s long poll


if __name__ == "__main__":
    asyncio.run(main())
