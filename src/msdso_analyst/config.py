"""Loads the bot token from the environment and server IDs from a TOML file."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config/server.toml")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class ServerConfig:
    guild_id: int
    moderator_role_ids: frozenset[int]
    reaction_role_message_ids: frozenset[int]
    reaction_roles: dict[str, int]

    def role_for_reaction(self, message_id: int, emoji_name: str | None) -> int | None:
        """Role ID granted by reacting with ``emoji_name`` on ``message_id``, or None if not a role reaction."""
        if message_id not in self.reaction_role_message_ids or emoji_name is None:
            return None
        return self.reaction_roles.get(emoji_name)


def load_server_config(path: Path | str = DEFAULT_CONFIG_PATH) -> ServerConfig:
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"Server config not found: {path}") from e

    try:
        return ServerConfig(
            guild_id=int(raw["guild_id"]),
            moderator_role_ids=frozenset(int(i) for i in raw.get("moderator_role_ids", [])),
            reaction_role_message_ids=frozenset(int(i) for i in raw.get("reaction_role_message_ids", [])),
            reaction_roles={str(k): int(v) for k, v in raw.get("reaction_roles", {}).items()},
        )
    except KeyError as e:
        raise ConfigError(f"Missing required key {e} in {path}") from e


def load_token() -> str:
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        raise ConfigError("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    return token
