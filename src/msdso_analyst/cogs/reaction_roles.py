"""Grants and removes roles when members react to the role messages in #roles."""

import logging

import disnake
from disnake.ext import commands

log = logging.getLogger(__name__)


class ReactionRoles(commands.Cog):
    def __init__(self, bot: commands.InteractionBot):
        self.bot = bot

    def _resolve(self, payload: disnake.RawReactionActionEvent) -> tuple[disnake.Guild, disnake.Role] | None:
        role_id = self.bot.config.role_for_reaction(payload.message_id, payload.emoji.name)
        if role_id is None or payload.guild_id is None:
            return None
        guild = self.bot.get_guild(payload.guild_id)
        role = guild.get_role(role_id) if guild else None
        if role is None:
            log.warning("Role %s for reaction %s not found", role_id, payload.emoji)
            return None
        return guild, role

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: disnake.RawReactionActionEvent):
        resolved = self._resolve(payload)
        if resolved is None or payload.member is None or payload.member.bot:
            return
        _, role = resolved
        await payload.member.add_roles(role, reason="Reaction role")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: disnake.RawReactionActionEvent):
        resolved = self._resolve(payload)
        if resolved is None:
            return
        guild, role = resolved
        member = guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except disnake.NotFound:
                return  # They left the server.
        await member.remove_roles(role, reason="Reaction role removed")
