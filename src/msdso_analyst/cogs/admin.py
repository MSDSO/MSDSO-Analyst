"""Moderator-only slash commands."""

import logging
from datetime import datetime
from socket import gethostname

import disnake
from disnake.ext import commands

log = logging.getLogger(__name__)

MSDSO_EMOTE = "<:MSDSO:773312353622032414>"
AWS_HOSTNAME = "MSDSO-AWS"

# Hides these commands from regular members by default. Server admins can adjust
# visibility under Server Settings > Integrations; the role check below still applies.
MOD_PERMISSIONS = disnake.Permissions(manage_messages=True)


def machine_type(hostname: str) -> str:
    return "remote AWS" if hostname == AWS_HOSTNAME else "local"


def is_moderator(member: disnake.abc.User, moderator_role_ids: frozenset[int]) -> bool:
    roles = getattr(member, "roles", [])
    return any(role.id in moderator_role_ids for role in roles)


async def respond(inter: disnake.ApplicationCommandInteraction, content: str, *, ephemeral: bool = True):
    """Reply to an interaction whether or not it has already been responded to or deferred."""
    if inter.response.is_done():
        await inter.followup.send(content, ephemeral=ephemeral)
    else:
        await inter.response.send_message(content, ephemeral=ephemeral)


class Admin(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        if await self.bot.is_owner(inter.author) or is_moderator(inter.author, self.bot.config.moderator_role_ids):
            return True
        raise commands.CheckFailure("Only moderators can use this command.")

    async def cog_slash_command_error(self, inter: disnake.ApplicationCommandInteraction, error: Exception):
        if isinstance(error, commands.CheckFailure):
            await respond(inter, str(error) or "You can't use this command.")
            return
        log.exception("Error in /%s", inter.application_command.name, exc_info=error)
        await respond(inter, "Something went wrong running that command.")

    @commands.slash_command(description="Show where the bot is running.", default_member_permissions=MOD_PERMISSIONS)
    async def status(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.send_message(
            f"{MSDSO_EMOTE} MSDSO Analyst is running on a {machine_type(gethostname())} machine.\n"
            f"Machine Time: {datetime.now()}\n"
            f"Welcome, {inter.author.mention}"
        )

    @commands.slash_command(
        description="Delete recent messages from this channel.", default_member_permissions=MOD_PERMISSIONS
    )
    async def purge(self, inter: disnake.ApplicationCommandInteraction, amount: commands.Range[int, 1, 100]):
        """
        Delete recent messages from this channel.

        Parameters
        ----------
        amount: How many messages to delete (1-100).
        """
        # Deleting can take longer than the 3s interaction window.
        await inter.response.defer(ephemeral=True)
        deleted = await inter.channel.purge(limit=amount)
        await inter.followup.send(f"Purged {len(deleted)} messages!", ephemeral=True)

    @commands.slash_command(description="Shut the bot down.", default_member_permissions=MOD_PERMISSIONS)
    async def shutdown(self, inter: disnake.ApplicationCommandInteraction):
        log.info("Shutdown requested by %s", inter.author)
        await inter.response.send_message("Goodbye, shutting down.")
        await self.bot.close()

    @commands.slash_command(description="Give a role to a member.", default_member_permissions=MOD_PERMISSIONS)
    async def assign(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member, role: disnake.Role):
        """
        Give a role to a member.

        Parameters
        ----------
        member: The member to give the role to.
        role: The role to give.
        """
        try:
            await member.add_roles(role, reason=f"/assign by {inter.author}")
        except disnake.Forbidden:
            await respond(inter, f"I don't have permission to assign {role.mention}. Is it above my role?")
            return
        await respond(inter, f"Gave {role.mention} to {member.mention}.")

    @commands.slash_command(description="Echo a message, for debugging.", default_member_permissions=MOD_PERMISSIONS)
    async def echo(self, inter: disnake.ApplicationCommandInteraction, string_to_echo: str):
        """
        Echo a message, for debugging.

        Parameters
        ----------
        string_to_echo: The text to send back.
        """
        await inter.response.send_message(string_to_echo)

    @commands.slash_command(description="Edit a message the bot posted.", default_member_permissions=MOD_PERMISSIONS)
    async def edit(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel,
        message_id: commands.LargeInt,
        new_message: str,
    ):
        """
        Edit a message the bot posted.

        Parameters
        ----------
        channel: The channel the message is in.
        message_id: The ID of the message to edit.
        new_message: The new content. Use \\n for line breaks.
        """
        try:
            message = await channel.fetch_message(message_id)
        except disnake.NotFound:
            await respond(inter, "Couldn't find that message in that channel.")
            return
        if message.author != self.bot.user:
            await respond(inter, "I can only edit my own messages.")
            return
        # Slash command options are single-line, so accept a literal \n for line breaks.
        await message.edit(content=new_message.replace("\\n", "\n"))
        await respond(inter, "Edited message!")

    @commands.slash_command(description="Add a reaction to a message.", default_member_permissions=MOD_PERMISSIONS)
    async def react_to_message(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel,
        message_id: commands.LargeInt,
        emoji: str,
    ):
        """
        Add a reaction to a message.

        Parameters
        ----------
        channel: The channel the message is in.
        message_id: The ID of the message to react to.
        emoji: The emoji to react with.
        """
        try:
            message = await channel.fetch_message(message_id)
        except disnake.NotFound:
            await respond(inter, "Couldn't find that message in that channel.")
            return
        try:
            await message.add_reaction(emoji)
        except disnake.HTTPException:
            await respond(inter, f"Couldn't react with `{emoji}`. Is it a valid emoji I have access to?")
            return
        await respond(inter, "Reacted!")
