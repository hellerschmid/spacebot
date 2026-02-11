from __future__ import annotations

import asyncio
import unittest

from spacebot.commands import CommandContext, dispatch, load_commands
from spacebot.config import Config
from spacebot.invites import BotState


class _FakeClient:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []
        self.rooms: dict[str, object] = {}

    async def room_send(
        self,
        room_id: str,
        event_type: str,
        content: dict[str, str],
    ) -> None:
        _ = (room_id, event_type)
        self.sent_messages.append(content["body"])


class _FakeDb:
    pass


class DispatchSecurityTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        load_commands()

    async def asyncSetUp(self) -> None:
        self.client = _FakeClient()
        self.ctx = CommandContext(
            room_id="!room:example.com",
            sender="@admin:example.com",
            event_id="$event",
            args=[],
            raw_body="",
            client=self.client,  # type: ignore[arg-type]
            config=Config(
                homeserver="https://example.com",
                bot_user="@bot:example.com",
                bot_password="secret",
                command_prefix="!!",
            ),
            db=_FakeDb(),  # type: ignore[arg-type]
            bot_state=BotState(startup_time=asyncio.get_event_loop().time()),
        )

    async def _dispatch(self, raw_body: str) -> str:
        self.ctx.raw_body = raw_body
        await dispatch(self.ctx)
        self.assertTrue(self.client.sent_messages)
        return self.client.sent_messages[-1]

    async def test_baseline_help_still_works(self) -> None:
        response = await self._dispatch("!!help")
        self.assertIn("Spacebot Commands", response)

    async def test_reject_prefix_with_double_space(self) -> None:
        response = await self._dispatch("!!  help")
        self.assertIn("Invalid command format", response)

    async def test_reject_prefix_with_tab(self) -> None:
        response = await self._dispatch("!!\thelp")
        self.assertIn("Invalid command format", response)

    async def test_reject_unicode_command_confusable(self) -> None:
        response = await self._dispatch("!!һelp")
        self.assertIn("Invalid command format", response)

    async def test_reject_null_byte_command(self) -> None:
        response = await self._dispatch("!!help\x00")
        self.assertIn("Invalid command format", response)

    async def test_unknown_command_message_remains_safe(self) -> None:
        response = await self._dispatch("!!invalid")
        self.assertIn("Unknown command", response)


if __name__ == "__main__":
    unittest.main()
