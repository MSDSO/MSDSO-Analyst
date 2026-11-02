import sqlite3

import pytest

from msdso_analyst.config import RoleGroupSeed
from msdso_analyst.storage import GroupRole, Storage


def test_groups_keep_creation_order(storage):
    storage.create_group("Cohort", "When you started", 1)
    storage.create_group("Classes")
    assert [g.name for g in storage.role_groups()] == ["Cohort", "Classes"]
    cohort = storage.role_group_by_name("cohort")  # case-insensitive
    assert (cohort.description, cohort.max_choices, cohort.roles) == ("When you started", 1, ())


def test_duplicate_group_name(storage):
    storage.create_group("Cohort")
    with pytest.raises(sqlite3.IntegrityError):
        storage.create_group("COHORT")


def test_add_role_moves_between_groups(storage):
    a = storage.create_group("A")
    b = storage.create_group("B")
    storage.add_role(a, 10, "🔟")
    storage.add_role(a, 11)
    storage.add_role(b, 10, "1️⃣")
    assert storage.role_group(a).roles == (GroupRole(11, None),)
    assert storage.role_group(b).roles == (GroupRole(10, "1️⃣"),)


def test_remove_role(storage):
    group_id = storage.create_group("A")
    storage.add_role(group_id, 10)
    assert storage.remove_role(10)
    assert not storage.remove_role(10)
    assert storage.role_group(group_id).roles == ()


def test_delete_group_removes_its_roles(storage):
    group_id = storage.create_group("A")
    storage.add_role(group_id, 10)
    storage.delete_group(group_id)
    assert storage.role_group(group_id) is None
    # The role is free to join another group.
    other = storage.create_group("B")
    storage.add_role(other, 10)
    assert storage.role_group(other).roles == (GroupRole(10, None),)


def test_seed_only_when_empty(storage):
    seeds = [RoleGroupSeed("Cohort", "", 1, ((1, "1️⃣"), (2, None)))]
    assert storage.seed_role_groups(seeds)
    assert not storage.seed_role_groups([RoleGroupSeed("Other", "", 0, ())])
    (group,) = storage.role_groups()
    assert group.roles == (GroupRole(1, "1️⃣"), GroupRole(2, None))


def test_settings_and_faq_messages(storage):
    assert storage.get_setting("k") is None
    storage.set_setting("k", "a")
    storage.set_setting("k", "b")
    assert storage.get_setting("k") == "b"

    assert storage.faq_message("x") is None
    storage.set_faq_message("x", 1, 2)
    storage.set_faq_message("x", 1, 3)
    assert storage.faq_message("x") == (1, 3)


def test_persists_to_disk(tmp_path):
    path = tmp_path / "data" / "bot.db"
    storage = Storage(path)
    storage.create_group("A")
    storage.close()
    reopened = Storage(path)
    assert [g.name for g in reopened.role_groups()] == ["A"]
    reopened.close()
