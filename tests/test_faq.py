from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import disnake
import pytest

from msdso_analyst.cogs.faq import Faq
from msdso_analyst.config import ConfigError
from msdso_analyst.faq import DEFAULT_FAQ_DIR, MAX_MESSAGE_LENGTH, FaqEntry, load_faq, parse_faq
from tests.conftest import http_error

REPO_ROOT = Path(__file__).parent.parent
CHANNEL_ID = 500


def test_repo_faq_files_are_valid():
    entries = load_faq(REPO_ROOT / DEFAULT_FAQ_DIR)
    assert "program-information" in entries
    assert all(e.message_id for e in entries.values())
    assert all(len(e.content) <= MAX_MESSAGE_LENGTH for e in entries.values())


def test_parse():
    entry = parse_faq("x", "+++\nchannel_id = 1\nmessage_id = 2\n+++\n\n**Hello**\n\nworld\n")
    assert entry == FaqEntry("x", 1, 2, "**Hello**\n\nworld")


def test_parse_without_message_id():
    assert parse_faq("x", "+++\nchannel_id = 1\n+++\nhi").message_id is None


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("hi", "front matter"),
        ("+++\nchannel_id = 1\nhi", "closing"),
        ("+++\nmessage_id = 2\n+++\nhi", "bad front matter"),
        ("+++\nchannel_id = = 1\n+++\nhi", "bad front matter"),
        ("+++\nchannel_id = 1\n+++\n   \n", "no content"),
        ("+++\nchannel_id = 1\n+++\n" + "a" * (MAX_MESSAGE_LENGTH + 1), "limit"),
    ],
)
def test_parse_errors(text, error):
    with pytest.raises(ConfigError, match=error):
        parse_faq("x", text)


@pytest.fixture
def faq_dir(tmp_path):
    return tmp_path


def write_faq(faq_dir, slug, content, message_id=None):
    meta = f"channel_id = {CHANNEL_ID}\n" + (f"message_id = {message_id}\n" if message_id else "")
    (faq_dir / f"{slug}.md").write_text(f"+++\n{meta}+++\n{content}\n")


def make_message(message_id, content="old", author_id=999):
    message = MagicMock(id=message_id, content=content, jump_url=f"https://discord.com/x/{message_id}")
    message.author = SimpleNamespace(id=author_id)
    message.edit = AsyncMock()
    return message


@pytest.fixture
def channel(bot):
    channel = MagicMock(id=CHANNEL_ID)
    channel.fetch_message = AsyncMock()
    channel.send = AsyncMock(return_value=make_message(777))
    bot.get_channel = MagicMock(return_value=channel)
    return channel


@pytest.fixture
def cog(bot, faq_dir, channel):
    return Faq(bot, faq_dir)


def reply(inter) -> str:
    return inter.followup.send.call_args.args[0]


async def test_edits_existing_message(cog, inter, faq_dir, channel):
    write_faq(faq_dir, "intro", "new", message_id=123)
    message = make_message(123)
    channel.fetch_message.return_value = message
    await Faq.publish.callback(cog, inter, name="intro")
    channel.fetch_message.assert_awaited_once_with(123)
    message.edit.assert_awaited_once()
    assert message.edit.call_args.kwargs["content"] == "new"
    assert "updated" in reply(inter)


async def test_skips_unchanged_message(cog, inter, faq_dir, channel):
    write_faq(faq_dir, "intro", "same", message_id=123)
    message = make_message(123, content="same")
    channel.fetch_message.return_value = message
    await Faq.publish.callback(cog, inter, name="intro")
    message.edit.assert_not_awaited()
    assert "up to date" in reply(inter)


async def test_refuses_other_authors_message(cog, inter, faq_dir, channel):
    write_faq(faq_dir, "intro", "new", message_id=123)
    message = make_message(123, author_id=1)
    channel.fetch_message.return_value = message
    await Faq.publish.callback(cog, inter, name="intro")
    message.edit.assert_not_awaited()
    assert "wasn't posted by me" in reply(inter)


async def test_posts_and_remembers_new_message(cog, inter, faq_dir, channel, storage):
    write_faq(faq_dir, "intro", "hello")
    await Faq.publish.callback(cog, inter, name="intro")
    channel.send.assert_awaited_once()
    assert channel.send.call_args.args == ("hello",)
    assert storage.faq_message("intro") == (CHANNEL_ID, 777)

    # The next publish edits the message it posted instead of posting again.
    channel.fetch_message.return_value = make_message(777, content="hello")
    await Faq.publish.callback(cog, inter, name="intro")
    channel.fetch_message.assert_awaited_once_with(777)
    channel.send.assert_awaited_once()


async def test_reposts_deleted_message(cog, inter, faq_dir, channel, storage):
    write_faq(faq_dir, "intro", "hello", message_id=123)
    channel.fetch_message.side_effect = http_error(disnake.NotFound, 404)
    await Faq.publish.callback(cog, inter, name="intro")
    channel.send.assert_awaited_once()
    assert storage.faq_message("intro") == (CHANNEL_ID, 777)


async def test_publishes_all_and_reports_failures(cog, inter, faq_dir, channel):
    write_faq(faq_dir, "a", "one")
    write_faq(faq_dir, "b", "two")
    channel.send.side_effect = [make_message(1), http_error(disnake.Forbidden, 403)]
    await Faq.publish.callback(cog, inter, name=None)
    lines = reply(inter).splitlines()
    assert lines[0].startswith("`a`: posted")
    assert lines[1].startswith("`b`: failed")


async def test_unknown_name(cog, inter, faq_dir, channel):
    write_faq(faq_dir, "a", "one")
    await Faq.publish.callback(cog, inter, name="nope")
    assert "no FAQ file" in reply(inter)
    channel.send.assert_not_awaited()


async def test_reports_invalid_files(cog, inter, faq_dir, channel):
    (faq_dir / "bad.md").write_text("no front matter")
    await Faq.publish.callback(cog, inter, name=None)
    assert "Couldn't load" in reply(inter)
    channel.send.assert_not_awaited()


async def test_autocomplete(cog, inter, faq_dir):
    write_faq(faq_dir, "registration-1", "x")
    write_faq(faq_dir, "program-information", "x")
    assert await cog._faq_names(inter, "REG") == ["registration-1"]
