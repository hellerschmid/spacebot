from __future__ import annotations

import re

MAX_COMMAND_NAME_LEN = 32
MAX_ARGUMENT_COUNT = 8
MAX_ARGUMENT_LENGTH = 255
MAX_ID_LENGTH = 255

_COMMAND_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
_MATRIX_LOCALPART_RE = re.compile(r"^[A-Za-z0-9._=\-]+$")
_MATRIX_DOMAIN_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$"
)


def is_strict_ascii(text: str, *, allow_space: bool = False) -> bool:
    """Return True when text only contains allowed strict ASCII chars."""
    for ch in text:
        code = ord(ch)
        if allow_space and code == 0x20:
            continue
        if code < 0x21 or code > 0x7E:
            return False
    return True


def validate_message_payload(payload: str) -> tuple[bool, str | None]:
    """Validate raw command payload text (after command prefix)."""
    if payload == "":
        return False, "Missing command name."
    if not is_strict_ascii(payload, allow_space=True):
        return False, "Command contains unsupported characters."
    return True, None


def validate_command_name(name: str) -> tuple[bool, str | None]:
    """Validate a parsed command token."""
    if not name:
        return False, "Missing command name."
    if len(name) > MAX_COMMAND_NAME_LEN:
        return False, "Command name is too long."
    if not _COMMAND_NAME_RE.fullmatch(name):
        return False, "Invalid command name."
    return True, None


def validate_args(args: list[str]) -> tuple[bool, str | None]:
    """Validate command argument count and characters."""
    if len(args) > MAX_ARGUMENT_COUNT:
        return False, "Too many command arguments."

    for arg in args:
        if arg == "":
            return False, "Arguments cannot be empty."
        if len(arg) > MAX_ARGUMENT_LENGTH:
            return False, "Argument is too long."
        if not is_strict_ascii(arg, allow_space=False):
            return False, "Argument contains unsupported characters."
    return True, None


def _split_matrix_id(raw: str) -> tuple[str, str] | None:
    """Split '@local:server' style IDs into local/server components."""
    if ":" not in raw:
        return None
    local, server = raw[1:].split(":", 1)
    if not local or not server:
        return None
    return local, server


def _validate_matrix_parts(local: str, server: str) -> bool:
    return bool(
        _MATRIX_LOCALPART_RE.fullmatch(local)
        and _MATRIX_DOMAIN_RE.fullmatch(server)
    )


def validate_user_id(user_id: str) -> tuple[bool, str | None]:
    """Validate strict Matrix user IDs like '@alice:example.com'."""
    if not user_id.startswith("@"):
        return False, "Must start with @."
    if len(user_id) > MAX_ID_LENGTH:
        return False, "User ID is too long."
    if not is_strict_ascii(user_id, allow_space=False):
        return False, "User ID contains unsupported characters."
    parts = _split_matrix_id(user_id)
    if parts is None:
        return False, "Must be like @user:server.com."
    if not _validate_matrix_parts(*parts):
        return False, "Must be like @user:server.com."
    return True, None


def validate_room_id(room_id: str) -> tuple[bool, str | None]:
    """Validate strict Matrix room IDs like '!opaque:example.com'."""
    if not room_id.startswith("!"):
        return False, "Must start with !."
    if len(room_id) > MAX_ID_LENGTH:
        return False, "Room ID is too long."
    if not is_strict_ascii(room_id, allow_space=False):
        return False, "Room ID contains unsupported characters."
    parts = _split_matrix_id(room_id.replace("!", "@", 1))
    if parts is None:
        return False, "Must be like !room:server.com."
    if not _validate_matrix_parts(*parts):
        return False, "Must be like !room:server.com."
    return True, None


def validate_room_alias(alias: str) -> tuple[bool, str | None]:
    """Validate strict Matrix room aliases like '#name:example.com'."""
    if not alias.startswith("#"):
        return False, "Must start with #."
    if len(alias) > MAX_ID_LENGTH:
        return False, "Alias is too long."
    if not is_strict_ascii(alias, allow_space=False):
        return False, "Alias contains unsupported characters."
    parts = _split_matrix_id(alias.replace("#", "@", 1))
    if parts is None:
        return False, "Must be like #alias:server.com."
    if not _validate_matrix_parts(*parts):
        return False, "Must be like #alias:server.com."
    return True, None


def validate_room_ref(
    room_ref: str,
    *,
    allow_shorthand_alias: bool = False,
) -> tuple[bool, str | None]:
    """Validate a room reference accepted by command handlers."""
    if allow_shorthand_alias and room_ref.startswith("#") and ":" not in room_ref:
        if len(room_ref) > MAX_ID_LENGTH:
            return False, "Alias is too long."
        if not is_strict_ascii(room_ref, allow_space=False):
            return False, "Alias contains unsupported characters."
        if not _MATRIX_LOCALPART_RE.fullmatch(room_ref[1:]):
            return False, "Must be like #alias or #alias:server.com."
        return True, None

    if room_ref.startswith("!"):
        return validate_room_id(room_ref)
    if room_ref.startswith("#"):
        return validate_room_alias(room_ref)
    return False, "Must be a room ID (!room:server) or alias (#alias:server)."
