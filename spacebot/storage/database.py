from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite

SCHEMA_VERSION = 2

SCHEMA_V1_SQL = """\
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    room_id TEXT NOT NULL,
    sender TEXT,
    timestamp INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_seen_events_room ON seen_events(room_id);
CREATE INDEX IF NOT EXISTS idx_seen_events_timestamp ON seen_events(timestamp);

CREATE TABLE IF NOT EXISTS invite_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    room_id TEXT NOT NULL,
    source TEXT NOT NULL,
    result TEXT NOT NULL,
    error_detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_invite_history_user ON invite_history(user_id);
CREATE INDEX IF NOT EXISTS idx_invite_history_room ON invite_history(room_id);
CREATE INDEX IF NOT EXISTS idx_invite_history_created ON invite_history(created_at);

CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

MIGRATION_V2_SQL = """\
CREATE TABLE IF NOT EXISTS autoinvite_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    space_room_id TEXT NOT NULL,
    target_room_id TEXT NOT NULL,
    added_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(space_room_id, target_room_id)
);
CREATE INDEX IF NOT EXISTS idx_autoinvite_space ON autoinvite_rules(space_room_id);

CREATE TABLE IF NOT EXISTS user_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    room_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, room_id)
);
CREATE INDEX IF NOT EXISTS idx_user_blocks_user ON user_blocks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_blocks_room ON user_blocks(room_id);
"""


@dataclass
class InviteStats:
    """Aggregate invite statistics."""

    total: int = 0
    invited: int = 0
    failed: int = 0
    already_joined: int = 0
    skipped: int = 0


class Database:
    """Async SQLite persistence layer for spacebot."""

    def __init__(self, db_path: str = "spacebot.db") -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open the database connection and initialise the schema."""
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        # Apply base schema (v1 tables)
        await self._conn.executescript(SCHEMA_V1_SQL)

        # Check current schema version
        async with self._conn.execute(
            "SELECT version FROM schema_version LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            # Fresh database — apply all migrations
            await self._conn.executescript(MIGRATION_V2_SQL)
            await self._conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
        elif row[0] < 2:
            # Migrate from v1 to v2
            await self._conn.executescript(MIGRATION_V2_SQL)
            await self._conn.execute(
                "UPDATE schema_version SET version = ?", (SCHEMA_VERSION,)
            )

        await self._conn.commit()
        print(f"[db] connected to {self._db_path} (schema v{SCHEMA_VERSION})")

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            print("[db] connection closed")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    # ── Seen events ──────────────────────────────────────────────────────

    async def is_event_seen(self, event_id: str) -> bool:
        """Check whether an event has already been processed."""
        async with self.conn.execute(
            "SELECT 1 FROM seen_events WHERE event_id = ?", (event_id,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def mark_event_seen(
        self,
        event_id: str,
        event_type: str,
        room_id: str,
        sender: str | None,
        timestamp: int,
    ) -> None:
        """Record that an event has been processed."""
        await self.conn.execute(
            "INSERT OR IGNORE INTO seen_events "
            "(event_id, event_type, room_id, sender, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, event_type, room_id, sender, timestamp),
        )
        await self.conn.commit()

    async def cleanup_old_events(self, days: int = 7) -> int:
        """Delete seen events older than the specified number of days.

        Returns the number of rows deleted.
        """
        cutoff = datetime.now(timezone.utc).timestamp() * 1000 - (
            days * 86400 * 1000
        )
        cursor = await self.conn.execute(
            "DELETE FROM seen_events WHERE timestamp < ?", (int(cutoff),)
        )
        await self.conn.commit()
        deleted = cursor.rowcount
        if deleted:
            print(f"[db] cleaned up {deleted} seen events older than {days} days")
        return deleted

    # ── Invite history ───────────────────────────────────────────────────

    async def record_invite(
        self,
        user_id: str,
        room_id: str,
        source: str,
        result: str,
        error_detail: str | None = None,
    ) -> None:
        """Record an invite action in the audit trail."""
        await self.conn.execute(
            "INSERT INTO invite_history "
            "(user_id, room_id, source, result, error_detail) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, room_id, source, result, error_detail),
        )
        await self.conn.commit()

    async def get_invite_stats(self) -> InviteStats:
        """Get aggregate invite statistics."""
        stats = InviteStats()
        async with self.conn.execute(
            "SELECT result, COUNT(*) FROM invite_history GROUP BY result"
        ) as cursor:
            async for row in cursor:
                result, count = row
                stats.total += count
                if result == "invited":
                    stats.invited += count
                elif result == "failed":
                    stats.failed += count
                elif result == "already_joined":
                    stats.already_joined += count
                elif result == "skipped":
                    stats.skipped += count
        return stats

    async def get_invite_history(
        self,
        user_id: str | None = None,
        room_id: str | None = None,
        limit: int = 50,
    ) -> list[tuple[str, str, str, str, str | None, str]]:
        """Fetch recent invite history records.

        Returns list of (user_id, room_id, source, result, error_detail, created_at).
        """
        conditions: list[str] = []
        params: list[str | int] = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if room_id is not None:
            conditions.append("room_id = ?")
            params.append(room_id)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        async with self.conn.execute(
            f"SELECT user_id, room_id, source, result, error_detail, created_at "
            f"FROM invite_history{where} "
            f"ORDER BY created_at DESC LIMIT ?",
            params,
        ) as cursor:
            return [row async for row in cursor]

    # ── Bot state (key-value) ────────────────────────────────────────────

    async def get_state(self, key: str) -> str | None:
        """Retrieve a bot state value by key."""
        async with self.conn.execute(
            "SELECT value FROM bot_state WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else None

    async def set_state(self, key: str, value: str) -> None:
        """Set a bot state value (upsert)."""
        await self.conn.execute(
            "INSERT INTO bot_state (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, value),
        )
        await self.conn.commit()

    # ── Sync token shortcuts ─────────────────────────────────────────────

    async def get_next_batch(self) -> str | None:
        """Get the last persisted sync token."""
        return await self.get_state("next_batch")

    async def set_next_batch(self, token: str) -> None:
        """Persist the sync token."""
        await self.set_state("next_batch", token)

    # ── Autoinvite rules ─────────────────────────────────────────────────

    async def add_autoinvite_rule(
        self,
        space_room_id: str,
        target_room_id: str,
        added_by: str | None = None,
    ) -> bool:
        """Add an autoinvite rule. Returns True if a new rule was created."""
        cursor = await self.conn.execute(
            "INSERT OR IGNORE INTO autoinvite_rules "
            "(space_room_id, target_room_id, added_by) "
            "VALUES (?, ?, ?)",
            (space_room_id, target_room_id, added_by),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def remove_autoinvite_rule(
        self, space_room_id: str, target_room_id: str
    ) -> bool:
        """Remove an autoinvite rule. Returns True if a rule was deleted."""
        cursor = await self.conn.execute(
            "DELETE FROM autoinvite_rules "
            "WHERE space_room_id = ? AND target_room_id = ?",
            (space_room_id, target_room_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_autoinvite_rules(
        self,
    ) -> list[tuple[str, str, str | None, str]]:
        """Get all autoinvite rules.

        Returns list of (space_room_id, target_room_id, added_by, created_at).
        """
        async with self.conn.execute(
            "SELECT space_room_id, target_room_id, added_by, created_at "
            "FROM autoinvite_rules ORDER BY space_room_id, target_room_id"
        ) as cursor:
            return [row async for row in cursor]

    async def get_target_rooms_for_space(
        self, space_room_id: str
    ) -> list[str]:
        """Get target room IDs for a specific space."""
        async with self.conn.execute(
            "SELECT target_room_id FROM autoinvite_rules "
            "WHERE space_room_id = ?",
            (space_room_id,),
        ) as cursor:
            return [row[0] async for row in cursor]

    async def get_all_space_ids(self) -> list[str]:
        """Get all distinct configured space room IDs."""
        async with self.conn.execute(
            "SELECT DISTINCT space_room_id FROM autoinvite_rules"
        ) as cursor:
            return [row[0] async for row in cursor]

    async def get_all_target_room_ids(self) -> set[str]:
        """Get all distinct configured target room IDs."""
        async with self.conn.execute(
            "SELECT DISTINCT target_room_id FROM autoinvite_rules"
        ) as cursor:
            return {row[0] async for row in cursor}

    async def get_all_configured_room_ids(self) -> set[str]:
        """Get the union of all space IDs and target room IDs."""
        spaces = set(await self.get_all_space_ids())
        targets = await self.get_all_target_room_ids()
        return spaces | targets

    # ── User blocks ──────────────────────────────────────────────────────

    async def add_user_block(
        self, user_id: str, room_id: str, reason: str
    ) -> bool:
        """Block a user from automatic re-invitation to a room."""
        await self.conn.execute(
            "INSERT INTO user_blocks (user_id, room_id, reason) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, room_id) DO UPDATE SET "
            "reason = excluded.reason, "
            "created_at = datetime('now')",
            (user_id, room_id, reason),
        )
        await self.conn.commit()
        return True

    async def remove_user_block(
        self, user_id: str, room_id: str | None = None
    ) -> int:
        """Remove block(s) for a user.

        If room_id is None, removes all blocks for the user.
        Returns the number of blocks removed.
        """
        if room_id is not None:
            cursor = await self.conn.execute(
                "DELETE FROM user_blocks WHERE user_id = ? AND room_id = ?",
                (user_id, room_id),
            )
        else:
            cursor = await self.conn.execute(
                "DELETE FROM user_blocks WHERE user_id = ?",
                (user_id,),
            )
        await self.conn.commit()
        return cursor.rowcount

    async def is_user_blocked(self, user_id: str, room_id: str) -> bool:
        """Check whether a user is blocked from a room."""
        async with self.conn.execute(
            "SELECT 1 FROM user_blocks WHERE user_id = ? AND room_id = ?",
            (user_id, room_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_user_blocks(
        self, user_id: str | None = None
    ) -> list[tuple[str, str, str, str]]:
        """Get block records.

        Returns list of (user_id, room_id, reason, created_at).
        """
        if user_id is not None:
            query = (
                "SELECT user_id, room_id, reason, created_at "
                "FROM user_blocks WHERE user_id = ? "
                "ORDER BY created_at DESC"
            )
            params: tuple = (user_id,)
        else:
            query = (
                "SELECT user_id, room_id, reason, created_at "
                "FROM user_blocks ORDER BY created_at DESC"
            )
            params = ()

        async with self.conn.execute(query, params) as cursor:
            return [row async for row in cursor]
