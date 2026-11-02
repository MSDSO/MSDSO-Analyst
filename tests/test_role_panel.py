from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import disnake
import pytest

from msdso_analyst.cogs.role_panel import (
    PANEL_SETTING,
    PICK_PREFIX,
    SET_PREFIX,
    RolePanel,
    panel_components,
    parse_colour,
    parse_custom_id,
    resolve_emoji,
    role_select,
    unsafe_reason,
)
from msdso_analyst.storage import GroupRole
from tests.conftest import http_error, last_reply


class FakeRole:
    def __init__(self, role_id, name="role", position=1, permissions=None, managed=False, default=False):
        self.id = role_id
        self.name = name
        self.position = position
        self.permissions = permissions or disnake.Permissions.none()
        self.managed = managed
        self.mention = f"<@&{role_id}>"
        self._default = default

    def is_default(self):
        return self._default

    def __ge__(self, other):
        return self.position >= other.position


SPRING = FakeRole(1, "Spring 2025")
FALL = FakeRole(2, "Fall 2025")
NLP = FakeRole(3, "NLP")
BOT_TOP_ROLE = FakeRole(99, position=10)


@pytest.fixture
def guild():
    roles = {r.id: r for r in (SPRING, FALL, NLP)}
    msdso_emoji = SimpleNamespace(name="MSDSO", id=773312353622032414)
    return SimpleNamespace(
        get_role=roles.get,
        emojis=[msdso_emoji],
        me=SimpleNamespace(top_role=BOT_TOP_ROLE),
    )


@pytest.fixture
def member():
    member = MagicMock(roles=[])
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    return member


@pytest.fixture
def cohort(storage):
    group_id = storage.create_group("Cohort", "When you started", 1)
    storage.add_role(group_id, SPRING.id, "1️⃣")
    storage.add_role(group_id, FALL.id, "2️⃣")
    return storage.role_group(group_id)


@pytest.fixture
def classes(storage):
    group_id = storage.create_group("Classes")
    storage.add_role(group_id, NLP.id, "🗣️")
    return storage.role_group(group_id)


@pytest.fixture
def cog(bot):
    return RolePanel(bot)


@pytest.fixture
def component_inter(inter, guild, member):
    inter.guild = guild
    inter.author = member
    inter.response.edit_message = AsyncMock()
    inter.edit_original_message = AsyncMock()
    return inter


def test_parse_custom_id():
    assert parse_custom_id("roles:pick:12", PICK_PREFIX) == 12
    assert parse_custom_id("roles:pick:12", SET_PREFIX) is None
    assert parse_custom_id("roles:pick:abc", PICK_PREFIX) is None
    assert parse_custom_id("something-else", PICK_PREFIX) is None


def test_resolve_emoji(guild):
    assert resolve_emoji(guild, "👀") == "👀"
    assert resolve_emoji(guild, "MSDSO").id == 773312353622032414
    assert resolve_emoji(guild, "<:MSAI:1195071638371323984>").id == 1195071638371323984
    assert resolve_emoji(guild, "<:MSAI:123>") is None
    assert resolve_emoji(guild, "NotAnEmoji") is None
    assert resolve_emoji(guild, None) is None


def test_parse_colour():
    assert parse_colour("#1abc9c").value == 0x1ABC9C
    assert parse_colour(" 1ABC9C ").value == 0x1ABC9C
    assert parse_colour("#fff") is None
    assert parse_colour("zzzzzz") is None


def test_unsafe_reason(guild):
    assert unsafe_reason(SPRING, guild.me) is None
    assert "moderator permissions" in unsafe_reason(
        FakeRole(5, permissions=disnake.Permissions(administrator=True)), guild.me
    )
    assert "moderator permissions" in unsafe_reason(
        FakeRole(5, permissions=disnake.Permissions(manage_roles=True)), guild.me
    )
    assert "managed" in unsafe_reason(FakeRole(5, managed=True), guild.me)
    assert "managed" in unsafe_reason(FakeRole(5, default=True), guild.me)
    assert "above my highest role" in unsafe_reason(FakeRole(5, position=10), guild.me)


def test_panel_skips_empty_groups(storage, cohort):
    storage.create_group("Empty")
    buttons = panel_components(storage.role_groups())
    assert [b.label for b in buttons] == ["Cohort"]
    assert buttons[0].custom_id == f"{PICK_PREFIX}{cohort.id}"


def test_select_preselects_current_roles(cohort, guild, member):
    member.roles = [FALL]
    select = role_select(cohort, guild, member)
    assert select.custom_id == f"{SET_PREFIX}{cohort.id}"
    assert (select.min_values, select.max_values) == (0, 1)
    assert [(o.label, o.default) for o in select.options] == [("Spring 2025", False), ("Fall 2025", True)]


def test_select_skips_deleted_roles(storage, cohort, guild, member):
    storage.add_role(cohort.id, 12345)
    select = role_select(storage.role_group(cohort.id), guild, member)
    assert len(select.options) == 2


def test_select_without_limit_allows_all(classes, guild, member):
    assert role_select(classes, guild, member).max_values == 1  # only one role in the group
    assert role_select(classes, guild, member).placeholder == "Pick one"


class TestButton:
    async def test_opens_private_dropdown(self, cog, cohort, component_inter):
        component_inter.component = SimpleNamespace(custom_id=f"{PICK_PREFIX}{cohort.id}")
        await cog.on_button_click(component_inter)
        kwargs = component_inter.response.send_message.call_args.kwargs
        assert kwargs["ephemeral"] is True
        assert kwargs["components"].custom_id == f"{SET_PREFIX}{cohort.id}"

    async def test_ignores_other_buttons(self, cog, component_inter):
        component_inter.component = SimpleNamespace(custom_id="something-else")
        await cog.on_button_click(component_inter)
        component_inter.response.send_message.assert_not_awaited()

    async def test_deleted_group(self, cog, component_inter):
        component_inter.component = SimpleNamespace(custom_id=f"{PICK_PREFIX}404")
        await cog.on_button_click(component_inter)
        assert "doesn't have any roles" in last_reply(component_inter)


class TestDropdown:
    def pick(self, inter, group, *roles):
        inter.component = SimpleNamespace(custom_id=f"{SET_PREFIX}{group.id}")
        inter.values = [str(r.id) for r in roles]

    async def test_swaps_roles_to_match_selection(self, cog, cohort, component_inter, member):
        member.roles = [SPRING, NLP]
        self.pick(component_inter, cohort, FALL)
        await cog.on_dropdown(component_inter)
        member.add_roles.assert_awaited_once()
        assert member.add_roles.call_args.args == (FALL,)
        assert member.remove_roles.call_args.args == (SPRING,)  # NLP is in another group, so it's untouched
        content = component_inter.edit_original_message.call_args.kwargs["content"]
        assert content == "Added <@&2>\nRemoved <@&1>"

    async def test_clearing_selection_removes_group_roles(self, cog, cohort, component_inter, member):
        member.roles = [SPRING]
        self.pick(component_inter, cohort)
        await cog.on_dropdown(component_inter)
        member.add_roles.assert_not_awaited()
        assert member.remove_roles.call_args.args == (SPRING,)

    async def test_no_changes(self, cog, cohort, component_inter, member):
        member.roles = [SPRING]
        self.pick(component_inter, cohort, SPRING)
        await cog.on_dropdown(component_inter)
        member.add_roles.assert_not_awaited()
        member.remove_roles.assert_not_awaited()
        assert component_inter.edit_original_message.call_args.kwargs["content"] == "No changes."

    async def test_ignores_roles_outside_group(self, cog, cohort, component_inter, member):
        self.pick(component_inter, cohort, NLP)  # A forged value for a role in another group.
        await cog.on_dropdown(component_inter)
        member.add_roles.assert_not_awaited()

    async def test_enforces_max_choices(self, cog, cohort, component_inter, member):
        self.pick(component_inter, cohort, SPRING, FALL)
        await cog.on_dropdown(component_inter)
        member.add_roles.assert_not_awaited()
        assert "at most 1" in component_inter.response.edit_message.call_args.kwargs["content"]

    async def test_missing_permissions(self, cog, cohort, component_inter, member):
        member.add_roles.side_effect = http_error(disnake.Forbidden, 403)
        self.pick(component_inter, cohort, SPRING)
        await cog.on_dropdown(component_inter)
        assert "don't have permission" in component_inter.edit_original_message.call_args.kwargs["content"]


def make_message(message_id):
    message = MagicMock(id=message_id, jump_url=f"https://discord.com/x/{message_id}")
    message.edit = AsyncMock()
    return message


@pytest.fixture
def panel_channel(bot):
    channel = MagicMock(id=700)
    channel.send = AsyncMock(return_value=make_message(800))
    channel.fetch_message = AsyncMock(return_value=make_message(800))
    bot.get_channel = MagicMock(return_value=channel)
    old_message = MagicMock(delete=AsyncMock())
    bot.get_partial_messageable = MagicMock(
        return_value=MagicMock(get_partial_message=MagicMock(return_value=old_message))
    )
    return channel


class TestCommands:
    @pytest.fixture
    def cmd_inter(self, inter, guild):
        inter.guild = guild
        return inter

    async def test_post_replaces_old_panel(self, cog, cohort, cmd_inter, panel_channel, storage, bot):
        storage.set_setting(PANEL_SETTING, "1:2")
        await RolePanel.post.callback(cog, cmd_inter, channel=panel_channel)
        content = panel_channel.send.call_args.args[0]
        assert "**Cohort**: When you started" in content
        assert storage.get_setting(PANEL_SETTING) == "700:800"
        bot.get_partial_messageable.assert_called_once_with(1)
        assert "Posted" in last_reply(cmd_inter)

    async def test_post_without_roles(self, cog, cmd_inter, panel_channel):
        await RolePanel.post.callback(cog, cmd_inter, channel=panel_channel)
        panel_channel.send.assert_not_awaited()
        assert "no role groups" in last_reply(cmd_inter)

    async def test_add_role_refreshes_panel(self, cog, cohort, cmd_inter, panel_channel, storage):
        storage.set_setting(PANEL_SETTING, "700:800")
        new_role = FakeRole(4, "Spring 2026")
        await RolePanel.add.callback(cog, cmd_inter, group="cohort", role=new_role, emoji="3️⃣")
        assert storage.role_group(cohort.id).roles[-1].role_id == 4
        panel_channel.fetch_message.return_value.edit.assert_awaited_once()
        assert "Added <@&4> to **Cohort**" in last_reply(cmd_inter)

    async def test_add_refuses_dangerous_role(self, cog, cohort, cmd_inter, storage):
        admin = FakeRole(5, permissions=disnake.Permissions(administrator=True))
        await RolePanel.add.callback(cog, cmd_inter, group="Cohort", role=admin, emoji=None)
        assert len(storage.role_group(cohort.id).roles) == 2
        assert "moderator permissions" in last_reply(cmd_inter)

    async def test_add_refuses_bad_emoji(self, cog, cohort, cmd_inter, storage):
        await RolePanel.add.callback(cog, cmd_inter, group="Cohort", role=FakeRole(4), emoji="nope")
        assert len(storage.role_group(cohort.id).roles) == 2

    @pytest.fixture
    def creatable_guild(self, cmd_inter):
        cmd_inter.guild.roles = [SPRING, FALL, NLP]
        cmd_inter.guild.create_role = AsyncMock(return_value=FakeRole(4, "Fall 2026 Cohort"))
        return cmd_inter.guild

    async def test_create_role(self, cog, cohort, cmd_inter, creatable_guild, panel_channel, storage):
        storage.set_setting(PANEL_SETTING, "700:800")
        await RolePanel.create.callback(
            cog, cmd_inter, group="Cohort", name="Fall 2026 Cohort", emoji="🔟", colour="#1abc9c"
        )
        kwargs = creatable_guild.create_role.call_args.kwargs
        assert kwargs["name"] == "Fall 2026 Cohort"
        assert kwargs["permissions"] == disnake.Permissions.none()
        assert kwargs["colour"].value == 0x1ABC9C
        assert kwargs["mentionable"] is False
        assert storage.role_group(cohort.id).roles[-1] == GroupRole(4, "🔟")
        panel_channel.fetch_message.return_value.edit.assert_awaited_once()
        assert "Created <@&4> and added it to **Cohort**" in last_reply(cmd_inter)

    async def test_create_without_colour(self, cog, cohort, cmd_inter, creatable_guild):
        await RolePanel.create.callback(cog, cmd_inter, group="Cohort", name="New", emoji=None, colour=None)
        assert creatable_guild.create_role.call_args.kwargs["colour"] == disnake.Colour.default()

    @pytest.mark.parametrize(
        ("kwargs", "error"),
        [
            ({"group": "Nope"}, "no group named"),
            ({"name": "Fall 2025"}, "already exists"),
            ({"emoji": "nope"}, "isn't an emoji"),
            ({"colour": "teal"}, "isn't a hex colour"),
        ],
    )
    async def test_create_validates_before_creating(self, cog, cohort, cmd_inter, creatable_guild, kwargs, error):
        args = {"group": "Cohort", "name": "New", "emoji": None, "colour": None, **kwargs}
        await RolePanel.create.callback(cog, cmd_inter, **args)
        creatable_guild.create_role.assert_not_awaited()
        assert error in last_reply(cmd_inter)

    async def test_create_respects_option_limit(self, cog, cmd_inter, creatable_guild, storage):
        group_id = storage.create_group("Big")
        for i in range(25):
            storage.add_role(group_id, 1000 + i)
        await RolePanel.create.callback(cog, cmd_inter, group="Big", name="New", emoji=None, colour=None)
        creatable_guild.create_role.assert_not_awaited()
        assert "limit" in last_reply(cmd_inter)

    async def test_create_without_permission(self, cog, cohort, cmd_inter, creatable_guild, storage):
        creatable_guild.create_role.side_effect = http_error(disnake.Forbidden, 403)
        await RolePanel.create.callback(cog, cmd_inter, group="Cohort", name="New", emoji=None, colour=None)
        assert len(storage.role_group(cohort.id).roles) == 2
        assert "Manage Roles" in last_reply(cmd_inter)

    async def test_add_unknown_group(self, cog, cmd_inter):
        await RolePanel.add.callback(cog, cmd_inter, group="Nope", role=FakeRole(4), emoji=None)
        assert "no group named" in last_reply(cmd_inter)

    async def test_add_enforces_option_limit(self, cog, cmd_inter, storage):
        group_id = storage.create_group("Big")
        for i in range(25):
            storage.add_role(group_id, 1000 + i)
        await RolePanel.add.callback(cog, cmd_inter, group="Big", role=FakeRole(4), emoji=None)
        assert "limit" in last_reply(cmd_inter)

    async def test_new_group_rejects_duplicate(self, cog, cohort, cmd_inter):
        await RolePanel.new_group.callback(cog, cmd_inter, name="cohort", max_choices=0, description="")
        assert "already a group" in last_reply(cmd_inter)

    async def test_delete_group(self, cog, cohort, cmd_inter, storage):
        await RolePanel.delete_group.callback(cog, cmd_inter, group="Cohort")
        assert storage.role_groups() == []

    async def test_remove_role(self, cog, cohort, cmd_inter, storage):
        await RolePanel.remove.callback(cog, cmd_inter, role=SPRING)
        assert [r.role_id for r in storage.role_group(cohort.id).roles] == [FALL.id]
        await RolePanel.remove.callback(cog, cmd_inter, role=SPRING)
        assert "isn't on the panel" in last_reply(cmd_inter)

    async def test_list(self, cog, cohort, classes, cmd_inter):
        await RolePanel.list_groups.callback(cog, cmd_inter)
        content = last_reply(cmd_inter)
        assert "**Cohort** (up to 1): 1️⃣ <@&1>, 2️⃣ <@&2>" in content
        assert "**Classes** (any number)" in content

    async def test_group_autocomplete(self, cog, cohort, classes, cmd_inter):
        assert await cog._group_names(cmd_inter, "co") == ["Cohort"]
