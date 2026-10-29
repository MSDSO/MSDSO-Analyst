from msdso_analyst.bot import MSDSOAnalyst, build_intents


def test_intents_are_minimal():
    intents = build_intents()
    assert intents.guilds
    assert intents.guild_reactions
    assert intents.members
    assert not intents.message_content
    assert not intents.presences


async def test_bot_loads_cogs(config):
    bot = MSDSOAnalyst(config)
    try:
        assert set(bot.cogs) == {"Admin", "ReactionRoles"}
        names = {c.name for c in bot.slash_commands}
        assert names == {"status", "purge", "shutdown", "assign", "echo", "edit", "react_to_message"}
    finally:
        await bot.close()
