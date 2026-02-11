from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from spacebot.commands import CommandContext
from spacebot.commands.autoinvite import _handle_add
from spacebot.config import Config
from spacebot.invites import BotState


class _FakeClient:
    def __init__(self) -> None:
        self.rooms: dict[str, object] = {}


class _FakeDb:
    def __init__(self) -> None:
        self.add_autoinvite_rule = AsyncMock()


class AutoinviteAddValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_when_space_is_not_accessible(self) -> None:
        db = _FakeDb()
        ctx = CommandContext(
            room_id="!ops:example.com",
            sender="@admin:example.com",
            event_id="$event",
            args=["add", "!space:example.com", "!room:example.com"],
            raw_body="!!autoinvite add !space:example.com !room:example.com",
            client=_FakeClient(),  # type: ignore[arg-type]
            config=Config(
                homeserver="https://example.com",
                bot_user="@bot:example.com",
                bot_password="secret",
            ),
            db=db,  # type: ignore[arg-type]
            bot_state=BotState(),
        )

        with (
            patch(
                "spacebot.commands.autoinvite.resolve_room_ref",
                new=AsyncMock(side_effect=["!space:example.com", "!room:example.com"]),
            ),
            patch(
                "spacebot.commands.autoinvite.ensure_joined_room",
                new=AsyncMock(return_value=False),
            ),
        ):
            response = await _handle_add(ctx)

        self.assertIn("Could not access space", response)
        db.add_autoinvite_rule.assert_not_called()


if __name__ == "__main__":
    unittest.main()
