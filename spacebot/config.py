from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Bot configuration loaded from environment variables."""

    homeserver: str
    bot_user: str
    bot_password: str
    reconcile_interval_cycles: int = 20
    login_max_retries: int = 5
    invite_acceptance_timeout_seconds: int = 0
    db_path: str = "spacebot.db"
    command_prefix: str = "!!"
    command_min_power_level: int = 50

    @classmethod
    def from_env(cls) -> Config:
        """Create a Config from environment variables."""
        return cls(
            homeserver=os.environ["MATRIX_HOMESERVER"],
            bot_user=os.environ["MATRIX_USER"],
            bot_password=os.environ["MATRIX_PASSWORD"],
            reconcile_interval_cycles=int(
                os.environ.get("RECONCILE_INTERVAL_CYCLES", "20")
            ),
            login_max_retries=int(os.environ.get("LOGIN_MAX_RETRIES", "5")),
            invite_acceptance_timeout_seconds=int(
                os.environ.get("INVITE_ACCEPTANCE_TIMEOUT_SECONDS", "0")
            ),
            db_path=os.environ.get("SPACEBOT_DB_PATH", "spacebot.db"),
            command_prefix=os.environ.get("SPACEBOT_COMMAND_PREFIX", "!!"),
            command_min_power_level=int(
                os.environ.get("SPACEBOT_COMMAND_MIN_POWER_LEVEL", "50")
            ),
        )

    def print_config(self) -> None:
        """Log the configuration at startup."""
        print(f"[config] homeserver={self.homeserver}")
        print(f"[config] bot_user={self.bot_user}")
        print(f"[config] reconcile_interval_cycles={self.reconcile_interval_cycles}")
        print(f"[config] login_max_retries={self.login_max_retries}")
        print(
            f"[config] invite_acceptance_timeout_seconds="
            f"{self.invite_acceptance_timeout_seconds}"
        )
        print(f"[config] db_path={self.db_path}")
        print(f"[config] command_prefix={self.command_prefix}")
        print(f"[config] command_min_power_level={self.command_min_power_level}")
