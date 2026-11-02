"""SQLite storage for state the bot manages at runtime: role groups, the role panel, and posted FAQ messages."""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from msdso_analyst.config import RoleGroupSeed

SCHEMA = """
CREATE TABLE IF NOT EXISTS role_groups (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT NOT NULL DEFAULT '',
    max_choices INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS group_roles (
    role_id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL REFERENCES role_groups(id) ON DELETE CASCADE,
    emoji TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS faq_messages (
    slug TEXT PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL
);
"""


@dataclass(frozen=True)
class GroupRole:
    role_id: int
    emoji: str | None


@dataclass(frozen=True)
class RoleGroup:
    id: int
    name: str
    description: str
    max_choices: int  # 0 = any number
    roles: tuple[GroupRole, ...]


class Storage:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)

    def close(self):
        self._db.close()

    # Role groups

    def role_groups(self) -> list[RoleGroup]:
        rows = self._db.execute("SELECT id, name, description, max_choices FROM role_groups ORDER BY id").fetchall()
        return [self._group(*row) for row in rows]

    def role_group(self, group_id: int) -> RoleGroup | None:
        row = self._db.execute(
            "SELECT id, name, description, max_choices FROM role_groups WHERE id = ?", (group_id,)
        ).fetchone()
        return self._group(*row) if row else None

    def role_group_by_name(self, name: str) -> RoleGroup | None:
        row = self._db.execute(
            "SELECT id, name, description, max_choices FROM role_groups WHERE name = ?", (name,)
        ).fetchone()
        return self._group(*row) if row else None

    def _group(self, group_id: int, name: str, description: str, max_choices: int) -> RoleGroup:
        roles = self._db.execute(
            "SELECT role_id, emoji FROM group_roles WHERE group_id = ? ORDER BY rowid", (group_id,)
        ).fetchall()
        return RoleGroup(group_id, name, description, max_choices, tuple(GroupRole(*r) for r in roles))

    def create_group(self, name: str, description: str = "", max_choices: int = 0) -> int:
        """Create a role group and return its ID. Raises sqlite3.IntegrityError if the name is taken."""
        with self._db:
            cur = self._db.execute(
                "INSERT INTO role_groups (name, description, max_choices) VALUES (?, ?, ?)",
                (name, description, max_choices),
            )
        return cur.lastrowid

    def delete_group(self, group_id: int):
        with self._db:
            self._db.execute("DELETE FROM role_groups WHERE id = ?", (group_id,))

    def add_role(self, group_id: int, role_id: int, emoji: str | None = None):
        """Add a role to a group, moving it if it's already in another group."""
        with self._db:
            self._db.execute("DELETE FROM group_roles WHERE role_id = ?", (role_id,))
            self._db.execute(
                "INSERT INTO group_roles (role_id, group_id, emoji) VALUES (?, ?, ?)", (role_id, group_id, emoji)
            )

    def remove_role(self, role_id: int) -> bool:
        with self._db:
            cur = self._db.execute("DELETE FROM group_roles WHERE role_id = ?", (role_id,))
        return cur.rowcount > 0

    def seed_role_groups(self, seeds: Iterable[RoleGroupSeed]) -> bool:
        """Create the given groups if there are none yet. Returns whether anything was seeded."""
        if self._db.execute("SELECT 1 FROM role_groups LIMIT 1").fetchone():
            return False
        seeds = list(seeds)
        for seed in seeds:
            group_id = self.create_group(seed.name, seed.description, seed.max_choices)
            for role_id, emoji in seed.roles:
                self.add_role(group_id, role_id, emoji)
        return bool(seeds)

    # Settings

    def get_setting(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str):
        with self._db:
            self._db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # FAQ messages

    def faq_message(self, slug: str) -> tuple[int, int] | None:
        """(channel ID, message ID) of the message last published for this FAQ entry."""
        row = self._db.execute("SELECT channel_id, message_id FROM faq_messages WHERE slug = ?", (slug,)).fetchone()
        return (row[0], row[1]) if row else None

    def set_faq_message(self, slug: str, channel_id: int, message_id: int):
        with self._db:
            self._db.execute(
                "INSERT INTO faq_messages (slug, channel_id, message_id) VALUES (?, ?, ?) "
                "ON CONFLICT(slug) DO UPDATE SET channel_id = excluded.channel_id, message_id = excluded.message_id",
                (slug, channel_id, message_id),
            )
