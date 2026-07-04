"""ユーザーからの能動的な要望・フィードバック(src/core/user_feedback.py)を検証する。

feedback_log.py(会話中の訂正の自動検知)とは別物であることを踏まえ、
送信・一覧・既読化の基本動作のみを検証する。
"""
from src.core import user_feedback


def test_submit_feedback_appends_and_marks_unreviewed(monkeypatch, tmp_path):
    monkeypatch.setattr(user_feedback, "USER_FEEDBACK_FILE", tmp_path / "user_feedback.json")

    record = user_feedback.submit_feedback(1, "那由多", "PDFも読み込めるようにしてほしい")

    assert record["user_id"] == 1
    assert record["user_name"] == "那由多"
    assert record["content"] == "PDFも読み込めるようにしてほしい"
    assert record["reviewed"] is False
    assert record["id"]
    assert record["timestamp"]


def test_get_all_feedback_returns_newest_first(monkeypatch, tmp_path):
    monkeypatch.setattr(user_feedback, "USER_FEEDBACK_FILE", tmp_path / "user_feedback.json")

    first = user_feedback.submit_feedback(1, "那由多", "1件目")
    second = user_feedback.submit_feedback(2, "友達", "2件目")

    all_feedback = user_feedback.get_all_feedback()

    assert [r["id"] for r in all_feedback] == [second["id"], first["id"]]


def test_get_all_feedback_returns_empty_list_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setattr(user_feedback, "USER_FEEDBACK_FILE", tmp_path / "user_feedback.json")

    assert user_feedback.get_all_feedback() == []


def test_mark_reviewed_updates_only_matching_record(monkeypatch, tmp_path):
    monkeypatch.setattr(user_feedback, "USER_FEEDBACK_FILE", tmp_path / "user_feedback.json")

    first = user_feedback.submit_feedback(1, "那由多", "1件目")
    second = user_feedback.submit_feedback(2, "友達", "2件目")

    user_feedback.mark_reviewed(first["id"])

    all_feedback = {r["id"]: r for r in user_feedback.get_all_feedback()}
    assert all_feedback[first["id"]]["reviewed"] is True
    assert all_feedback[second["id"]]["reviewed"] is False
