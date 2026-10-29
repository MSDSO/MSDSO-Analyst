from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import disnake
import pytest

from msdso_analyst.cogs.reaction_roles import ReactionRoles
from tests.conftest import ROLE_MESSAGE_ID, VISITOR_ROLE_ID, http_error


@pytest.fixture
def role():
    return SimpleNamespace(id=VISITOR_ROLE_ID)


@pytest.fixture
def guild(bot, role):
    guild = MagicMock()
    guild.get_role = MagicMock(side_effect=lambda role_id: role if role_id == VISITOR_ROLE_ID else None)
    guild.get_member = MagicMock(return_value=None)
    guild.fetch_member = AsyncMock()
    bot.get_guild = MagicMock(return_value=guild)
    return guild


@pytest.fixture
def cog(bot, guild):
    return ReactionRoles(bot)


def make_member(bot=False):
    member = MagicMock(bot=bot)
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    return member


def make_payload(emoji="🕵️", message_id=ROLE_MESSAGE_ID, member=None, guild_id=1):
    return SimpleNamespace(
        message_id=message_id,
        emoji=disnake.PartialEmoji(name=emoji),
        member=member,
        guild_id=guild_id,
        user_id=42,
    )


class TestAdd:
    async def test_grants_role(self, cog, role):
        member = make_member()
        await cog.on_raw_reaction_add(make_payload(member=member))
        member.add_roles.assert_awaited_once()
        assert member.add_roles.call_args.args == (role,)

    async def test_ignores_unknown_emoji(self, cog):
        # Previously raised KeyError.
        member = make_member()
        await cog.on_raw_reaction_add(make_payload(emoji="🍕", member=member))
        member.add_roles.assert_not_awaited()

    async def test_ignores_other_messages(self, cog):
        member = make_member()
        await cog.on_raw_reaction_add(make_payload(message_id=1, member=member))
        member.add_roles.assert_not_awaited()

    async def test_ignores_bots(self, cog):
        member = make_member(bot=True)
        await cog.on_raw_reaction_add(make_payload(member=member))
        member.add_roles.assert_not_awaited()

    async def test_ignores_deleted_role(self, cog, guild):
        guild.get_role.side_effect = None
        guild.get_role.return_value = None
        member = make_member()
        await cog.on_raw_reaction_add(make_payload(member=member))
        member.add_roles.assert_not_awaited()


class TestRemove:
    async def test_removes_role_using_cache(self, cog, guild, role):
        member = make_member()
        guild.get_member.return_value = member
        await cog.on_raw_reaction_remove(make_payload())
        member.remove_roles.assert_awaited_once()
        assert member.remove_roles.call_args.args == (role,)
        guild.fetch_member.assert_not_awaited()

    async def test_falls_back_to_fetch(self, cog, guild):
        member = make_member()
        guild.fetch_member.return_value = member
        await cog.on_raw_reaction_remove(make_payload())
        guild.fetch_member.assert_awaited_once_with(42)
        member.remove_roles.assert_awaited_once()

    async def test_member_left_server(self, cog, guild):
        guild.fetch_member.side_effect = http_error(disnake.NotFound, 404)
        await cog.on_raw_reaction_remove(make_payload())  # does not raise

    async def test_ignores_unknown_emoji(self, cog, guild):
        await cog.on_raw_reaction_remove(make_payload(emoji="🍕"))
        guild.get_member.assert_not_called()
