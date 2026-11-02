"""Self-assignable roles via a panel of buttons, one per role group.

Clicking a group's button opens a private dropdown pre-filled with the member's current roles in that group;
submitting it adds and removes roles to match. Buttons and dropdowns are matched by custom ID, so the panel keeps
working across restarts without registering persistent views.
"""

import logging
import re
import sqlite3

import disnake
from disnake.ext import commands

from msdso_analyst.cogs.common import MOD_PERMISSIONS, ModeratorCog, respond
from msdso_analyst.storage import RoleGroup

log = logging.getLogger(__name__)

PICK_PREFIX = "roles:pick:"
SET_PREFIX = "roles:set:"
PANEL_SETTING = "role_panel"  # "<channel id>:<message id>"
MAX_OPTIONS = 25  # Discord's limit for a dropdown, and for buttons on a message.
PANEL_HEADER = "**Pick your roles**\nClick a button to choose roles from that list. You can change them any time."

# Roles with any of these can't be self-assigned, so a mistaken /roles add can't hand out moderator powers.
DANGEROUS_PERMISSIONS = disnake.Permissions(
    administrator=True,
    manage_guild=True,
    manage_roles=True,
    manage_channels=True,
    manage_messages=True,
    manage_webhooks=True,
    manage_nicknames=True,
    kick_members=True,
    ban_members=True,
    moderate_members=True,
    mention_everyone=True,
)

CUSTOM_EMOJI = re.compile(r"<a?:\w+:\d{17,19}>")


def parse_custom_id(custom_id: str, prefix: str) -> int | None:
    if not custom_id.startswith(prefix):
        return None
    try:
        return int(custom_id.removeprefix(prefix))
    except ValueError:
        return None


def resolve_emoji(guild: disnake.Guild, emoji: str | None) -> disnake.PartialEmoji | disnake.Emoji | str | None:
    """Turn a stored emoji (Unicode, ``<:name:id>``, or a custom emoji's bare name) into something Discord accepts."""
    if not emoji:
        return None
    if CUSTOM_EMOJI.fullmatch(emoji):
        return disnake.PartialEmoji.from_str(emoji)
    custom = disnake.utils.get(guild.emojis, name=emoji)
    if custom is not None:
        return custom
    # A bare word that isn't one of the server's emoji would be rejected by Discord.
    return None if emoji.isascii() else emoji


def unsafe_reason(role: disnake.Role, bot_member: disnake.Member) -> str | None:
    """Why ``role`` can't be self-assignable, or None if it can."""
    if role.is_default() or role.managed:
        return f"{role.mention} is managed by Discord or an integration."
    if role.permissions.value & DANGEROUS_PERMISSIONS.value:
        return f"{role.mention} has moderator permissions, so members can't assign it to themselves."
    if role >= bot_member.top_role:
        return f"{role.mention} is above my highest role. Move my role above it in Server Settings > Roles."
    return None


def panel_components(groups: list[RoleGroup]) -> list[disnake.ui.Button]:
    return [
        disnake.ui.Button(label=g.name, style=disnake.ButtonStyle.primary, custom_id=f"{PICK_PREFIX}{g.id}")
        for g in groups
        if g.roles
    ][:MAX_OPTIONS]


def panel_content(groups: list[RoleGroup]) -> str:
    lines = [PANEL_HEADER, ""]
    lines += [f"**{g.name}**: {g.description}" if g.description else f"**{g.name}**" for g in groups if g.roles]
    return "\n".join(lines)


def role_select(group: RoleGroup, guild: disnake.Guild, member: disnake.Member) -> disnake.ui.StringSelect | None:
    """A dropdown of the group's roles with the member's current ones selected, or None if none of them exist."""
    member_role_ids = {r.id for r in member.roles}
    options = []
    for group_role in group.roles:
        role = guild.get_role(group_role.role_id)
        if role is None:
            log.warning("Role %s in group %r no longer exists", group_role.role_id, group.name)
            continue
        options.append(
            disnake.SelectOption(
                label=role.name,
                value=str(role.id),
                emoji=resolve_emoji(guild, group_role.emoji),
                default=role.id in member_role_ids,
            )
        )
    if not options:
        return None
    max_values = min(group.max_choices or len(options), len(options))
    return disnake.ui.StringSelect(
        custom_id=f"{SET_PREFIX}{group.id}",
        placeholder="Pick one" if max_values == 1 else "Pick any that apply",
        min_values=0,
        max_values=max_values,
        options=options,
    )


class RolePanel(ModeratorCog):
    @property
    def storage(self):
        return self.bot.storage

    # Member-facing: the panel buttons and the dropdowns they open.

    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        group_id = parse_custom_id(inter.component.custom_id, PICK_PREFIX)
        if group_id is None:
            return
        group = self.storage.role_group(group_id)
        select = role_select(group, inter.guild, inter.author) if group else None
        if select is None:
            await respond(inter, "That list doesn't have any roles right now.")
            return
        await inter.response.send_message(f"**{group.name}**", components=select, ephemeral=True)

    @commands.Cog.listener()
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        group_id = parse_custom_id(inter.component.custom_id, SET_PREFIX)
        if group_id is None:
            return
        group = self.storage.role_group(group_id)
        if group is None:
            await inter.response.edit_message(content="That list no longer exists.", components=[])
            return

        chosen = {int(v) for v in inter.values}
        if group.max_choices and len(chosen) > group.max_choices:
            await inter.response.edit_message(content=f"You can pick at most {group.max_choices}.", components=[])
            return
        member_role_ids = {r.id for r in inter.author.roles}
        group_roles = [r for gr in group.roles if (r := inter.guild.get_role(gr.role_id)) is not None]
        to_add = [r for r in group_roles if r.id in chosen and r.id not in member_role_ids]
        to_remove = [r for r in group_roles if r.id not in chosen and r.id in member_role_ids]

        await inter.response.defer()
        try:
            if to_add:
                await inter.author.add_roles(*to_add, reason="Role panel")
            if to_remove:
                await inter.author.remove_roles(*to_remove, reason="Role panel")
        except disnake.Forbidden:
            log.warning("Missing permission to update %s roles in group %r", inter.author, group.name)
            await inter.edit_original_message(
                content="I don't have permission to change those roles. Please let a moderator know.", components=[]
            )
            return

        changes = [f"Added {r.mention}" for r in to_add] + [f"Removed {r.mention}" for r in to_remove]
        await inter.edit_original_message(content="\n".join(changes) or "No changes.", components=[])

    # Moderator commands.

    async def refresh_panel(self) -> bool:
        """Re-render the posted panel after groups change. Returns whether there was a panel to update."""
        location = self.storage.get_setting(PANEL_SETTING)
        if location is None:
            return False
        channel_id, message_id = (int(x) for x in location.split(":"))
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
        except disnake.NotFound:
            return False
        groups = self.storage.role_groups()
        await message.edit(content=panel_content(groups), components=panel_components(groups))
        return True

    @commands.slash_command(default_member_permissions=MOD_PERMISSIONS)
    async def roles(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @roles.sub_command(description="Post the role panel in a channel, replacing the old one.")
    async def post(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        """
        Post the role panel in a channel, replacing the old one.

        Parameters
        ----------
        channel: Where to post the panel.
        """
        groups = self.storage.role_groups()
        if not panel_components(groups):
            await respond(inter, "There are no role groups with roles yet. Add some with `/roles add`.")
            return
        await inter.response.defer(ephemeral=True)
        message = await channel.send(panel_content(groups), components=panel_components(groups))

        old = self.storage.get_setting(PANEL_SETTING)
        self.storage.set_setting(PANEL_SETTING, f"{channel.id}:{message.id}")
        if old is not None:
            old_channel_id, old_message_id = (int(x) for x in old.split(":"))
            try:
                await self.bot.get_partial_messageable(old_channel_id).get_partial_message(old_message_id).delete()
            except disnake.HTTPException:
                pass  # Already deleted, or the channel is gone.
        await inter.followup.send(f"Posted the role panel: {message.jump_url}", ephemeral=True)

    @roles.sub_command(name="list", description="Show the role groups and their roles.")
    async def list_groups(self, inter: disnake.ApplicationCommandInteraction):
        groups = self.storage.role_groups()
        if not groups:
            await respond(inter, "There are no role groups yet. Create one with `/roles new-group`.")
            return
        sections = []
        for g in groups:
            limit = "any number" if g.max_choices == 0 else f"up to {g.max_choices}"
            roles = [f"{gr.emoji or ''} <@&{gr.role_id}>".strip() for gr in g.roles] or ["(no roles)"]
            sections.append(f"**{g.name}** ({limit}): " + ", ".join(roles))
        await inter.response.send_message(
            "\n".join(sections), ephemeral=True, allowed_mentions=disnake.AllowedMentions.none()
        )

    @roles.sub_command(name="new-group", description="Create a role group (a button on the panel).")
    async def new_group(
        self,
        inter: disnake.ApplicationCommandInteraction,
        name: commands.String[str, 1, 80],
        max_choices: commands.Range[int, 0, 25] = 0,
        description: commands.String[str, 0, 200] = "",
    ):
        """
        Create a role group (a button on the panel).

        Parameters
        ----------
        name: The button label, e.g. "Cohort".
        max_choices: How many roles in this group a member can hold at once. 0 means any number.
        description: A line of text shown on the panel for this group.
        """
        try:
            self.storage.create_group(name, description, max_choices)
        except sqlite3.IntegrityError:
            await respond(inter, f"There's already a group named **{name}**.")
            return
        await respond(inter, f"Created **{name}**. Add roles to it with `/roles add`.")

    @roles.sub_command(name="delete-group", description="Delete a role group. Members keep their roles.")
    async def delete_group(self, inter: disnake.ApplicationCommandInteraction, group: str):
        """
        Delete a role group. Members keep their roles.

        Parameters
        ----------
        group: The group to delete.
        """
        found = self.storage.role_group_by_name(group)
        if found is None:
            await respond(inter, f"There's no group named **{group}**.")
            return
        self.storage.delete_group(found.id)
        await self.refresh_panel()
        await respond(inter, f"Deleted **{found.name}**.")

    @roles.sub_command(description="Make a role self-assignable from a group on the panel.")
    async def add(
        self,
        inter: disnake.ApplicationCommandInteraction,
        group: str,
        role: disnake.Role,
        emoji: str | None = None,
    ):
        """
        Make a role self-assignable from a group on the panel.

        Parameters
        ----------
        group: The group to add it to.
        role: The role members can pick.
        emoji: Optional emoji shown next to it.
        """
        found = self.storage.role_group_by_name(group)
        if found is None:
            await respond(inter, f"There's no group named **{group}**. Create it with `/roles new-group`.")
            return
        if reason := unsafe_reason(role, inter.guild.me):
            await respond(inter, reason)
            return
        if emoji is not None and resolve_emoji(inter.guild, emoji) is None:
            await respond(inter, f"`{emoji}` isn't an emoji I can use.")
            return
        already_here = any(gr.role_id == role.id for gr in found.roles)
        if not already_here and len(found.roles) >= MAX_OPTIONS:
            await respond(inter, f"**{found.name}** already has {MAX_OPTIONS} roles, Discord's limit for one list.")
            return
        self.storage.add_role(found.id, role.id, emoji)
        await self.refresh_panel()
        await respond(inter, f"Added {role.mention} to **{found.name}**.")

    @roles.sub_command(description="Stop offering a role on the panel. Members who have it keep it.")
    async def remove(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        """
        Stop offering a role on the panel. Members who have it keep it.

        Parameters
        ----------
        role: The role to remove from the panel.
        """
        if not self.storage.remove_role(role.id):
            await respond(inter, f"{role.mention} isn't on the panel.")
            return
        await self.refresh_panel()
        await respond(inter, f"Removed {role.mention} from the panel.")

    @add.autocomplete("group")
    @delete_group.autocomplete("group")
    async def _group_names(self, inter: disnake.ApplicationCommandInteraction, current: str) -> list[str]:
        names = [g.name for g in self.storage.role_groups()]
        return [n for n in names if current.lower() in n.lower()][:25]
