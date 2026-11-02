from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import disnake
import pytest
from disnake.ext import commands

from msdso_analyst.cogs.admin import Admin, assign_refusal, machine_type
from msdso_analyst.cogs.common import is_moderator
from tests.conftest import MOD_ROLE_ID, http_error, last_reply


@pytest.fixture
def cog(bot):
    return Admin(bot)


def make_channel(message=None, error=None):
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message, side_effect=error)
    return channel


def test_machine_type():
    assert machine_type("MSDSO-AWS") == "remote AWS"
    assert machine_type("my-laptop") == "local"


def test_is_moderator():
    mod_ids = frozenset({MOD_ROLE_ID})
    assert is_moderator(SimpleNamespace(roles=[SimpleNamespace(id=MOD_ROLE_ID)]), mod_ids)
    assert not is_moderator(SimpleNamespace(roles=[SimpleNamespace(id=1)]), mod_ids)
    # A plain User (e.g. in DMs) has no roles.
    assert not is_moderator(SimpleNamespace(), mod_ids)


class TestCheck:
    async def test_moderator_allowed(self, cog, inter):
        inter.author.roles = [SimpleNamespace(id=MOD_ROLE_ID)]
        assert await cog.cog_slash_command_check(inter)

    async def test_owner_allowed(self, cog, bot, inter):
        bot.is_owner.return_value = True
        assert await cog.cog_slash_command_check(inter)

    async def test_regular_member_rejected(self, cog, inter):
        with pytest.raises(commands.CheckFailure):
            await cog.cog_slash_command_check(inter)

    async def test_check_failure_replies_ephemerally(self, cog, inter):
        await cog.cog_slash_command_error(inter, commands.CheckFailure("Only moderators can use this command."))
        inter.response.send_message.assert_awaited_once_with("Only moderators can use this command.", ephemeral=True)

    async def test_unexpected_error_uses_followup_if_already_responded(self, cog, inter):
        await inter.response.defer()
        await cog.cog_slash_command_error(inter, RuntimeError("boom"))
        assert "went wrong" in last_reply(inter)
        inter.followup.send.assert_awaited_once()


async def test_status_mentions_caller(cog, inter, monkeypatch):
    monkeypatch.setattr("msdso_analyst.cogs.admin.gethostname", lambda: "MSDSO-AWS")
    await Admin.status.callback(cog, inter)
    content = last_reply(inter)
    assert "remote AWS" in content
    assert "<@42>" in content


async def test_purge_defers_then_reports(cog, inter):
    inter.channel.purge = AsyncMock(return_value=[object()] * 3)
    await Admin.purge.callback(cog, inter, amount=3)
    inter.response.defer.assert_awaited_once_with(ephemeral=True)
    inter.channel.purge.assert_awaited_once_with(limit=3)
    inter.followup.send.assert_awaited_once_with("Purged 3 messages!", ephemeral=True)


async def test_shutdown_responds_then_closes(cog, bot, inter):
    await Admin.shutdown.callback(cog, inter)
    inter.response.send_message.assert_awaited_once()
    bot.close.assert_awaited_once()


class FakeRole:
    def __init__(self, role_id, position, managed=False, default=False):
        self.id = role_id
        self.position = position
        self.managed = managed
        self.mention = f"<@&{role_id}>"
        self._default = default

    def is_default(self):
        return self._default

    def __ge__(self, other):
        return self.position >= other.position


MODERATOR = FakeRole(MOD_ROLE_ID, position=5)
VISITOR = FakeRole(5, position=1)
ADMINISTRATOR = FakeRole(6, position=9)


class TestAssignRefusal:
    def test_role_below_author_allowed(self):
        assert assign_refusal(VISITOR, SimpleNamespace(top_role=MODERATOR), privileged=False) is None

    @pytest.mark.parametrize("role", [ADMINISTRATOR, MODERATOR])
    def test_role_at_or_above_author_refused(self, role):
        assert "below your highest role" in assign_refusal(role, SimpleNamespace(top_role=MODERATOR), privileged=False)

    def test_privileged_author_not_limited_by_order(self):
        assert assign_refusal(ADMINISTRATOR, SimpleNamespace(top_role=MODERATOR), privileged=True) is None

    @pytest.mark.parametrize("role", [FakeRole(7, 1, managed=True), FakeRole(1, 0, default=True)])
    def test_managed_and_everyone_refused_even_for_owner(self, role):
        assert "managed" in assign_refusal(role, SimpleNamespace(top_role=MODERATOR), privileged=True)


class TestAssign:
    @pytest.fixture
    def moderator(self, inter):
        inter.author.top_role = MODERATOR
        inter.author.roles = [MODERATOR]
        inter.guild.owner_id = 1
        return inter

    @pytest.fixture
    def member(self):
        member = MagicMock(mention="<@7>")
        member.add_roles = AsyncMock()
        return member

    async def test_assigns_role(self, cog, moderator, member):
        await Admin.assign.callback(cog, moderator, member=member, role=VISITOR)
        member.add_roles.assert_awaited_once()
        assert member.add_roles.call_args.args == (VISITOR,)
        assert last_reply(moderator) == "Gave <@&5> to <@7>."

    async def test_moderator_cannot_grant_administrator(self, cog, moderator, member):
        await Admin.assign.callback(cog, moderator, member=member, role=ADMINISTRATOR)
        member.add_roles.assert_not_awaited()
        assert "below your highest role" in last_reply(moderator)

    async def test_moderator_cannot_grant_own_role(self, cog, moderator, member):
        await Admin.assign.callback(cog, moderator, member=member, role=MODERATOR)
        member.add_roles.assert_not_awaited()

    async def test_server_owner_can_grant_any_role(self, cog, moderator, member):
        moderator.guild.owner_id = moderator.author.id
        await Admin.assign.callback(cog, moderator, member=member, role=ADMINISTRATOR)
        member.add_roles.assert_awaited_once()

    async def test_bot_owner_can_grant_any_role(self, cog, bot, moderator, member):
        bot.is_owner.return_value = True
        await Admin.assign.callback(cog, moderator, member=member, role=ADMINISTRATOR)
        member.add_roles.assert_awaited_once()

    async def test_reports_missing_permission(self, cog, moderator, member):
        member.add_roles.side_effect = http_error(disnake.Forbidden, 403)
        await Admin.assign.callback(cog, moderator, member=member, role=VISITOR)
        assert "don't have permission" in last_reply(moderator)


class TestEdit:
    async def test_edits_own_message_with_newlines(self, cog, bot, inter):
        message = MagicMock(author=bot.user)
        message.edit = AsyncMock()
        channel = make_channel(message)
        await Admin.edit.callback(cog, inter, channel=channel, message_id=10, new_message="line 1\\nline 2")
        channel.fetch_message.assert_awaited_once_with(10)
        message.edit.assert_awaited_once_with(content="line 1\nline 2")
        assert last_reply(inter) == "Edited message!"

    async def test_refuses_other_users_messages(self, cog, inter):
        message = MagicMock(author=SimpleNamespace(id=1))
        message.edit = AsyncMock()
        await Admin.edit.callback(cog, inter, channel=make_channel(message), message_id=10, new_message="x")
        message.edit.assert_not_awaited()
        assert "only edit my own" in last_reply(inter)

    async def test_message_not_found(self, cog, inter):
        channel = make_channel(error=http_error(disnake.NotFound, 404))
        await Admin.edit.callback(cog, inter, channel=channel, message_id=10, new_message="x")
        assert "Couldn't find" in last_reply(inter)


class TestReact:
    async def test_reacts(self, cog, inter):
        message = MagicMock()
        message.add_reaction = AsyncMock()
        await Admin.react_to_message.callback(cog, inter, channel=make_channel(message), message_id=10, emoji="👀")
        message.add_reaction.assert_awaited_once_with("👀")
        assert last_reply(inter) == "Reacted!"

    async def test_invalid_emoji(self, cog, inter):
        message = MagicMock()
        message.add_reaction = AsyncMock(side_effect=http_error(disnake.HTTPException, 400))
        await Admin.react_to_message.callback(cog, inter, channel=make_channel(message), message_id=10, emoji="nope")
        assert "Couldn't react" in last_reply(inter)


def test_all_commands_are_moderator_gated():
    for command in Admin(MagicMock()).get_slash_commands():
        assert command.default_member_permissions == disnake.Permissions(manage_messages=True), command.name
