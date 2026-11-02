from pathlib import Path

import pytest

from msdso_analyst.config import DEFAULT_CONFIG_PATH, ConfigError, load_server_config, load_token

REPO_ROOT = Path(__file__).parent.parent


def test_repo_config_loads():
    config = load_server_config(REPO_ROOT / DEFAULT_CONFIG_PATH)
    assert config.guild_id == 766782085041881120
    assert config.moderator_role_ids
    groups = {g.name: g for g in config.role_group_seeds}
    assert set(groups) == {"General", "Cohort", "Classes"}
    assert groups["Cohort"].max_choices == 1
    assert (773281658555990023, "MSDSO") in groups["General"].roles
    role_ids = [role_id for g in config.role_group_seeds for role_id, _ in g.roles]
    assert len(role_ids) == len(set(role_ids)) == 24


def test_role_group_defaults(tmp_path):
    path = tmp_path / "server.toml"
    path.write_text('guild_id = 5\n[[role_groups]]\nname = "Cohort"\nroles = [{ id = 7 }]\n')
    (group,) = load_server_config(path).role_group_seeds
    assert group.description == ""
    assert group.max_choices == 0
    assert group.roles == ((7, None),)


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
    assert config.moderator_role_ids == frozenset()
    assert config.role_group_seeds == ()


def test_load_token(monkeypatch):
    monkeypatch.setenv("DISCORD_TOKEN", " abc ")
    assert load_token() == "abc"


def test_load_token_missing(monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="DISCORD_TOKEN"):
        load_token()
