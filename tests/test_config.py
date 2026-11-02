from pathlib import Path

import pytest

from msdso_analyst.config import DEFAULT_CONFIG_PATH, ConfigError, load_server_config, load_token

REPO_ROOT = Path(__file__).parent.parent


def test_repo_config_loads():
    config = load_server_config(REPO_ROOT / DEFAULT_CONFIG_PATH)
    assert config.guild_id == 766782085041881120
    assert config.moderator_role_ids
    assert len(config.reaction_role_message_ids) == 3
    assert config.reaction_roles["MSDSO"] == 773281658555990023
    assert config.reaction_roles["👀"] == 773281343823675422


def test_role_for_reaction(config):
    assert config.role_for_reaction(222, "🕵️") == 333


def test_role_for_reaction_ignores_other_messages(config):
    assert config.role_for_reaction(12345, "🕵️") is None


def test_role_for_reaction_ignores_unknown_emoji(config):
    assert config.role_for_reaction(222, "🍕") is None
    assert config.role_for_reaction(222, None) is None


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_server_config(tmp_path / "nope.toml")


def test_missing_guild_id(tmp_path):
    path = tmp_path / "server.toml"
    path.write_text("moderator_role_ids = [1]\n")
    with pytest.raises(ConfigError, match="guild_id"):
        load_server_config(path)


def test_optional_sections_default_empty(tmp_path):
    path = tmp_path / "server.toml"
    path.write_text("guild_id = 5\n")
    config = load_server_config(path)
    assert config.reaction_roles == {}
    assert config.role_for_reaction(1, "👀") is None


def test_load_token(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", " abc ")
    assert load_token() == "abc"


def test_load_token_missing(monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="DISCORD_TOKEN"):
        load_token()
