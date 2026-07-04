"""育つアバターの解除状態(src/memory/avatar.py)を検証する。"""
from src.memory import avatar


def test_unlock_item_returns_true_on_first_unlock(monkeypatch, tmp_path):
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    assert avatar.unlock_item(1, "bookish_glasses") is True
    assert avatar.get_unlocked_slugs(1) == ["bookish_glasses"]


def test_unlock_item_returns_false_when_already_unlocked(monkeypatch, tmp_path):
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    avatar.unlock_item(1, "bookish_glasses")
    result = avatar.unlock_item(1, "bookish_glasses")

    assert result is False
    assert avatar.get_unlocked_slugs(1) == ["bookish_glasses"]


def test_get_unlocked_slugs_is_empty_for_new_user(monkeypatch, tmp_path):
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    assert avatar.get_unlocked_slugs(999) == []


def test_unlocks_are_scoped_per_user(monkeypatch, tmp_path):
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    avatar.unlock_item(1, "chef_hat")

    assert avatar.get_unlocked_slugs(1) == ["chef_hat"]
    assert avatar.get_unlocked_slugs(2) == []
