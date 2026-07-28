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


def test_get_selected_slug_is_none_before_any_selection(monkeypatch, tmp_path):
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    assert avatar.get_selected_slug(1) is None


def test_select_item_requires_unlocked_first(monkeypatch, tmp_path):
    """着せ替え機能: 未解除のアイテムは選べない(他人になりすまして
    未解除の見た目を先取りされないための安全策)。"""
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    assert avatar.select_item(1, "chef_hat") is False
    assert avatar.get_selected_slug(1) is None


def test_select_item_succeeds_for_unlocked_item(monkeypatch, tmp_path):
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    avatar.unlock_item(1, "chef_hat")
    avatar.unlock_item(1, "bookish_glasses")

    assert avatar.select_item(1, "chef_hat") is True
    assert avatar.get_selected_slug(1) == "chef_hat"


def test_select_item_can_change_selection(monkeypatch, tmp_path):
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    avatar.unlock_item(1, "chef_hat")
    avatar.unlock_item(1, "bookish_glasses")
    avatar.select_item(1, "chef_hat")

    avatar.select_item(1, "bookish_glasses")

    assert avatar.get_selected_slug(1) == "bookish_glasses"


def test_selections_are_scoped_per_user(monkeypatch, tmp_path):
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    avatar.unlock_item(1, "chef_hat")
    avatar.select_item(1, "chef_hat")

    assert avatar.get_selected_slug(2) is None
