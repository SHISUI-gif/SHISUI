"""夜間修行の朝レポート(src/study/report.py)を検証する。"""
import json

import pytest

from src.study import report


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "STUDY_SESSIONS_FILE", tmp_path / "sessions.json")
    yield


def test_get_unread_report_empty_when_no_sessions():
    assert report.get_unread_report() == ""


def test_get_unread_report_and_mark_read(tmp_path, monkeypatch):
    session_file = tmp_path / "sessions.json"
    monkeypatch.setattr(report, "STUDY_SESSIONS_FILE", session_file)
    sessions = [
        {
            "timestamp": "2026-07-03T02:00:00",
            "unread": True,
            "topics": [
                {"topic": "人間工学的なUI設計", "insight": "余白を意識すると良い", "memory_id": "abc"}
            ],
            "gemini_calls": 3,
        }
    ]
    session_file.write_text(json.dumps(sessions, ensure_ascii=False), encoding="utf-8")

    unread = report.get_unread_report()
    assert "人間工学的なUI設計" in unread
    assert "余白を意識すると良い" in unread

    report.mark_report_read()
    assert report.get_unread_report() == ""


def test_get_latest_session_returns_none_when_empty():
    assert report.get_latest_session() is None


def test_get_latest_session_returns_most_recent(tmp_path, monkeypatch):
    session_file = tmp_path / "sessions.json"
    monkeypatch.setattr(report, "STUDY_SESSIONS_FILE", session_file)
    sessions = [
        {"timestamp": "2026-07-01T02:00:00", "unread": False, "topics": [], "gemini_calls": 0},
        {"timestamp": "2026-07-02T02:00:00", "unread": True, "topics": [], "gemini_calls": 0},
    ]
    session_file.write_text(json.dumps(sessions, ensure_ascii=False), encoding="utf-8")

    latest = report.get_latest_session()
    assert latest["timestamp"] == "2026-07-02T02:00:00"
