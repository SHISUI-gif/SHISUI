"""志粋の自律活動ログ(src/core/activity_log.py)を検証する。"""
from src.core import activity_log


def test_log_activity_records_kind_and_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(activity_log, "ACTIVITY_LOG_FILE", tmp_path / "activity_log.json")

    record = activity_log.log_activity(kind="sleep", summary="テスト活動", details={"x": 1})

    assert record["kind"] == "sleep"
    assert record["summary"] == "テスト活動"
    assert record["details"] == {"x": 1}
    assert "timestamp" in record


def test_get_recent_activity_returns_newest_first(monkeypatch, tmp_path):
    monkeypatch.setattr(activity_log, "ACTIVITY_LOG_FILE", tmp_path / "activity_log.json")

    activity_log.log_activity(kind="sleep", summary="1件目")
    activity_log.log_activity(kind="study", summary="2件目")
    activity_log.log_activity(kind="debate", summary="3件目")

    recent = activity_log.get_recent_activity()

    assert [r["summary"] for r in recent] == ["3件目", "2件目", "1件目"]


def test_get_recent_activity_respects_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(activity_log, "ACTIVITY_LOG_FILE", tmp_path / "activity_log.json")

    for i in range(5):
        activity_log.log_activity(kind="sleep", summary=f"件{i}")

    assert len(activity_log.get_recent_activity(limit=2)) == 2


def test_get_recent_activity_empty_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setattr(activity_log, "ACTIVITY_LOG_FILE", tmp_path / "activity_log.json")

    assert activity_log.get_recent_activity() == []
