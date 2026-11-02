import logging
from pathlib import Path

import disnake
from disnake.ext import commands

from msdso_analyst.cogs.admin import Admin
from msdso_analyst.cogs.faq import Faq
from msdso_analyst.cogs.role_panel import RolePanel
from msdso_analyst.config import ServerConfig
from msdso_analyst.faq import DEFAULT_FAQ_DIR
from msdso_analyst.storage import Storage

log = logging.getLogger(__name__)


def build_intents() -> disnake.Intents:
    # Only what we use: guilds, and members (privileged) for role changes.
    # Message content is not needed; slash commands and components don't read messages.
    intents = disnake.Intents.none()
    intents.guilds = True
    intents.members = True
    return intents


class MSDSOAnalyst(commands.InteractionBot):
    def __init__(self, config: ServerConfig, storage: Storage, faq_dir: Path | str = DEFAULT_FAQ_DIR):
        super().__init__(intents=build_intents(), test_guilds=[config.guild_id])
        self.config = config
        self.storage = storage
        self.add_cog(Admin(self))
        self.add_cog(RolePanel(self))
        self.add_cog(Faq(self, faq_dir))

    async def on_ready(self):
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
