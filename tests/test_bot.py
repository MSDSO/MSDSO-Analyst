from msdso_analyst.bot import MSDSOAnalyst, build_intents


def test_intents_are_minimal():
    intents = build_intents()
    assert intents.guilds
    assert intents.members
    assert not intents.guild_reactions
    assert not intents.message_content
    assert not intents.presences


async def test_bot_loads_cogs(config, storage):
    bot = MSDSOAnalyst(config, storage)
    try:
        assert set(bot.cogs) == {"Admin", "RolePanel", "Faq"}
        names = {c.name for c in bot.slash_commands}
        assert names == {"status", "purge", "shutdown", "assign", "echo", "edit", "react_to_message", "roles", "faq"}
        roles = bot.get_slash_command("roles")
        assert set(roles.children) == {"post", "list", "new-group", "delete-group", "add", "remove"}
        assert set(bot.get_slash_command("faq").children) == {"publish"}
    finally:
        await bot.close()
