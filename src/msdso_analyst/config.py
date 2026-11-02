"""Loads the bot token from the environment and server IDs from a TOML file."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config/server.toml")
DEFAULT_DB_PATH = Path("data/msdso.db")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class RoleGroupSeed:
    """A role group to create the first time the bot starts with an empty database."""

    name: str
    description: str
    max_choices: int
    roles: tuple[tuple[int, str | None], ...]  # (role ID, emoji)


@dataclass(frozen=True)
class ServerConfig:
    guild_id: int
    moderator_role_ids: frozenset[int]
    role_group_seeds: tuple[RoleGroupSeed, ...] = ()


def _parse_role_group(raw: dict) -> RoleGroupSeed:
    return RoleGroupSeed(
        name=str(raw["name"]),
        description=str(raw.get("description", "")),
        max_choices=int(raw.get("max_choices", 0)),
        roles=tuple((int(r["id"]), r.get("emoji")) for r in raw.get("roles", [])),
    )


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
            role_group_seeds=tuple(_parse_role_group(g) for g in raw.get("role_groups", [])),
        )
    except KeyError as e:
        raise ConfigError(f"Missing required key {e} in {path}") from e


def load_token() -> str:
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        raise ConfigError("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    return token
