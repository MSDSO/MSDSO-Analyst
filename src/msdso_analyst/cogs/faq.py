"""Publishes the FAQ Markdown files in the repo to their Discord channels."""

import logging
from pathlib import Path

import disnake
from disnake.ext import commands

from msdso_analyst.cogs.common import MOD_PERMISSIONS, ModeratorCog
from msdso_analyst.config import ConfigError
from msdso_analyst.faq import DEFAULT_FAQ_DIR, FaqEntry, load_faq

log = logging.getLogger(__name__)

NO_MENTIONS = disnake.AllowedMentions.none()


class Faq(ModeratorCog):
    def __init__(self, bot: commands.InteractionBot, faq_dir: Path | str = DEFAULT_FAQ_DIR):
        super().__init__(bot)
        self.faq_dir = faq_dir

    async def _channel(self, channel_id: int) -> disnake.abc.Messageable:
        return self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)

    async def publish_entry(self, entry: FaqEntry) -> str:
        """Edit the entry's message to match its file, or post it if it has none. Returns a one-line summary."""
        channel = await self._channel(entry.channel_id)
        # A message we posted ourselves takes precedence over the one named in the file.
        stored = self.bot.storage.faq_message(entry.slug)
        message_id = stored[1] if stored and stored[0] == entry.channel_id else entry.message_id

        if message_id is not None:
            try:
                message = await channel.fetch_message(message_id)
            except disnake.NotFound:
                message = None
            if message is not None:
                if message.author.id != self.bot.user.id:
                    return f"`{entry.slug}`: message {message_id} wasn't posted by me, so I can't edit it."
                if message.content == entry.content:
                    return f"`{entry.slug}`: already up to date."
                await message.edit(content=entry.content, allowed_mentions=NO_MENTIONS)
                return f"`{entry.slug}`: updated {message.jump_url}"

        message = await channel.send(entry.content, allowed_mentions=NO_MENTIONS)
        self.bot.storage.set_faq_message(entry.slug, entry.channel_id, message.id)
        return f"`{entry.slug}`: posted {message.jump_url} (message ID `{message.id}`)"

    @commands.slash_command(default_member_permissions=MOD_PERMISSIONS)
    async def faq(self, inter: disnake.ApplicationCommandInteraction):
        pass

    @faq.sub_command(description="Post or update FAQ messages from the repo's faq/ files.")
    async def publish(self, inter: disnake.ApplicationCommandInteraction, name: str | None = None):
        """
        Post or update FAQ messages from the repo's faq/ files.

        Parameters
        ----------
        name: The FAQ file to publish. Leave empty to publish all of them.
        """
        await inter.response.defer(ephemeral=True)
        try:
            entries = load_faq(self.faq_dir)
        except ConfigError as e:
            await inter.followup.send(f"Couldn't load the FAQ files: {e}", ephemeral=True)
            return
        if name is not None:
            if name not in entries:
                await inter.followup.send(f"There's no FAQ file named `{name}`.", ephemeral=True)
                return
            entries = {name: entries[name]}

        lines = []
        for entry in entries.values():
            try:
                lines.append(await self.publish_entry(entry))
            except disnake.HTTPException as e:
                log.warning("Publishing FAQ %s failed: %s", entry.slug, e)
                lines.append(f"`{entry.slug}`: failed ({e.text or e.status}).")
        await inter.followup.send("\n".join(lines) or "There are no FAQ files.", ephemeral=True)

    @publish.autocomplete("name")
    async def _faq_names(self, inter: disnake.ApplicationCommandInteraction, current: str) -> list[str]:
        try:
            names = load_faq(self.faq_dir)
        except ConfigError:
            return []
        return [n for n in names if current.lower() in n.lower()][:25]
