from __future__ import annotations

import asyncio
import time

from nio import AsyncClient

from spacebot.callbacks import create_callbacks
from spacebot.commands import load_commands
from spacebot.config import Config
from spacebot.invites import (
    BotState,
    ensure_joined_configured_rooms,
    process_invite_queue,
    reconcile_existing_space_members,
    refresh_room_caches,
)
from spacebot.storage import Database
from spacebot.utils import is_error_response, resolve_room_ref, summarize_sync_activity


async def login_with_retry(
    client: AsyncClient, config: Config
) -> object:
    """Log in to the homeserver, retrying on rate-limit errors."""
    attempt = 0
    while True:
        attempt += 1
        print(f"[connect] logging in... attempt={attempt}")
        login_resp = await client.login(config.bot_password)
        print(f"[connect] login response type={type(login_resp).__name__}")
        if not is_error_response(login_resp):
            return login_resp

        retry_after_ms = getattr(login_resp, "retry_after_ms", None)
        if retry_after_ms is not None:
            max_retries = (
                "unlimited"
                if config.login_max_retries <= 0
                else str(config.login_max_retries)
            )
            print(
                f"[connect] login rate-limited "
                f"(retry_after_ms={retry_after_ms}, max_retries={max_retries})"
            )
            if config.login_max_retries <= 0 or attempt < config.login_max_retries:
                continue

        raise RuntimeError(
            f"Login failed after {attempt} attempt(s): {login_resp}"
        )


def _extract_server_name(bot_user: str) -> str | None:
    """Extract the server name from a Matrix user ID (e.g. @bot:server -> server)."""
    if ":" in bot_user:
        return bot_user.split(":", 1)[1]
    return None


async def load_autoinvite_rules(
    client: AsyncClient,
    config: Config,
    db: Database,
    state: BotState,
) -> None:
    """Load autoinvite rules from DB and resolve any aliases."""
    rules = await db.get_autoinvite_rules()
    if not rules:
        print("[startup] no autoinvite rules configured yet")
        print(
            "[startup] use !!autoinvite add <space> <room> to set up rules"
        )
        return

    print(f"[startup] loaded {len(rules)} autoinvite rule(s) from database")
    server_name = _extract_server_name(config.bot_user)
    seen_refs: set[str] = set()

    for space_ref, target_ref, _added_by, _created_at in rules:
        for ref, label in [
            (space_ref, "space"),
            (target_ref, "target"),
        ]:
            if ref in seen_refs:
                continue
            seen_refs.add(ref)

            # Resolve aliases to room IDs
            resolved = await resolve_room_ref(
                client, ref, label, server_name=server_name
            )
            if resolved and resolved != ref:
                state.room_join_refs[resolved] = ref

    await refresh_room_caches(db, state)


async def main() -> None:
    """Main entry point for the spacebot."""
    print("[startup] Space auto-invite bot starting")

    config = Config.from_env()
    config.print_config()

    # Initialise persistence
    db = Database(config.db_path)
    await db.connect()

    # Create runtime state
    state = BotState(startup_time=time.time())

    # Load command handlers
    load_commands()

    # Create Matrix client and log in
    print("[connect] creating Matrix client")
    client = AsyncClient(config.homeserver, config.bot_user)

    try:
        login_resp = await login_with_retry(client, config)
        print(
            "[connect] login successful "
            f"(user_id={getattr(login_resp, 'user_id', config.bot_user)}, "
            f"device_id={getattr(login_resp, 'device_id', 'unknown')})"
        )

        # Load autoinvite rules from database and resolve aliases
        await load_autoinvite_rules(client, config, db, state)

        # Join all configured rooms (spaces + targets)
        await ensure_joined_configured_rooms(client, db, state, "startup")

        # Register event callbacks
        create_callbacks(client, config, db, state)

        # Start invite queue worker
        invite_worker_task = asyncio.create_task(
            process_invite_queue(client, config, db, state)
        )

        # Restore sync token for incremental sync
        last_next_batch = await db.get_next_batch()
        if last_next_batch:
            print(f"[sync] resuming from saved sync token: {last_next_batch[:20]}...")
        else:
            print("[sync] no saved sync token, starting fresh")

        # Sync loop
        print("[sync] entering long-poll sync loop")
        while True:
            try:
                sync_resp = await client.sync(
                    timeout=30_000, since=last_next_batch
                )
                state.sync_count += 1

                if is_error_response(sync_resp):
                    print(
                        f"[sync] cycle={state.sync_count} failed: {sync_resp}"
                    )
                else:
                    last_next_batch = sync_resp.next_batch
                    await db.set_next_batch(last_next_batch)

                    print(
                        f"[sync] cycle={state.sync_count} ok "
                        f"(next_batch={last_next_batch[:20] if last_next_batch else 'n/a'}...)"
                    )
                    print(
                        f"[sync-events] {summarize_sync_activity(sync_resp)}"
                    )

                    if not state.startup_reconcile_done:
                        await reconcile_existing_space_members(
                            client, config, db, state, "startup"
                        )
                        state.startup_reconcile_done = True
                    elif (
                        config.reconcile_interval_cycles > 0
                        and state.sync_count
                        % config.reconcile_interval_cycles
                        == 0
                    ):
                        await reconcile_existing_space_members(
                            client,
                            config,
                            db,
                            state,
                            f"periodic-{state.sync_count}",
                        )

                    # Periodic cleanup of old seen events
                    if state.sync_count % 100 == 0:
                        await db.cleanup_old_events(days=7)

            except Exception as exc:
                print(f"[sync] exception in sync loop: {exc!r}")
                await asyncio.sleep(3)

    finally:
        await db.close()
        await client.close()
        print("[shutdown] bot stopped")
