import logging

import disnake
from disnake.ext import commands

from msdso_analyst.cogs.admin import Admin
from msdso_analyst.cogs.reaction_roles import ReactionRoles
from msdso_analyst.config import ServerConfig

log = logging.getLogger(__name__)


def build_intents() -> disnake.Intents:
    # Only what we use: guilds, raw reaction events, and members (privileged) for role changes.
    # Message content is not needed; slash commands don't read messages.
    intents = disnake.Intents.none()
    intents.guilds = True
    intents.guild_reactions = True
    intents.members = True
    return intents


class MSDSOAnalyst(commands.InteractionBot):
    def __init__(self, config: ServerConfig):
        super().__init__(intents=build_intents(), test_guilds=[config.guild_id])
        self.config = config
        self.add_cog(Admin(self))
        self.add_cog(ReactionRoles(self))

    async def on_ready(self):
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
