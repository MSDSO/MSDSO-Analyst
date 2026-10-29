from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import disnake
import pytest

from msdso_analyst.config import ServerConfig

MOD_ROLE_ID = 111
ROLE_MESSAGE_ID = 222
VISITOR_ROLE_ID = 333


@pytest.fixture
def config() -> ServerConfig:
    return ServerConfig(
        guild_id=1,
        moderator_role_ids=frozenset({MOD_ROLE_ID}),
        reaction_role_message_ids=frozenset({ROLE_MESSAGE_ID}),
        reaction_roles={"🕵️": VISITOR_ROLE_ID},
    )


@pytest.fixture
def bot(config):
    bot = MagicMock()
    bot.config = config
    bot.user = SimpleNamespace(id=999, name="MSDSO Analyst")
    bot.is_owner = AsyncMock(return_value=False)
    bot.close = AsyncMock()
    return bot


@pytest.fixture
def inter():
    inter = MagicMock()
    inter.author = SimpleNamespace(id=42, mention="<@42>", roles=[])
    done = False

    def is_done():
        return done

    async def send_message(*args, **kwargs):
        nonlocal done
        done = True

    async def defer(*args, **kwargs):
        nonlocal done
        done = True

    inter.response.is_done = MagicMock(side_effect=is_done)
    inter.response.send_message = AsyncMock(side_effect=send_message)
    inter.response.defer = AsyncMock(side_effect=defer)
    inter.followup.send = AsyncMock()
    return inter


def http_error(cls: type[disnake.HTTPException], status: int):
    return cls(MagicMock(status=status, reason="error"), "error")


def last_reply(inter) -> str:
    """Content of the most recent reply, whether sent as the initial response or a followup."""
    calls = inter.response.send_message.call_args_list + inter.followup.send.call_args_list
    return calls[-1].args[0]
