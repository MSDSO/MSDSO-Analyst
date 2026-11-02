"""Shared pieces for cogs whose slash commands are moderator-only."""

import logging

import disnake
from disnake.ext import commands

log = logging.getLogger(__name__)

# Hides these commands from regular members by default. Server admins can adjust
# visibility under Server Settings > Integrations; the role check below still applies.
MOD_PERMISSIONS = disnake.Permissions(manage_messages=True)


def is_moderator(member: disnake.abc.User, moderator_role_ids: frozenset[int]) -> bool:
    roles = getattr(member, "roles", [])
    return any(role.id in moderator_role_ids for role in roles)


async def respond(inter: disnake.Interaction, content: str, *, ephemeral: bool = True):
    """Reply to an interaction whether or not it has already been responded to or deferred."""
    if inter.response.is_done():
        await inter.followup.send(content, ephemeral=ephemeral)
    else:
        await inter.response.send_message(content, ephemeral=ephemeral)


class ModeratorCog(commands.Cog):
    """A cog whose slash commands only the bot owner and moderators can run."""

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
        log.exception("Error in /%s", inter.application_command.qualified_name, exc_info=error)
        await respond(inter, "Something went wrong running that command.")
