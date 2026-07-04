"""エラーログ(src/core/error_log.py)の基本的な読み書きを検証する。"""
from src.core import error_log


def test_log_error_appends_and_marks_unreviewed(monkeypatch, tmp_path):
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")

    record = error_log.log_error("some_source", ValueError("テストエラー"))

    assert record["source"] == "some_source"
    assert record["error_type"] == "ValueError"
    assert record["message"] == "テストエラー"
    assert record["reviewed"] is False

    unreviewed = error_log.get_unreviewed_errors()
    assert len(unreviewed) == 1
    assert unreviewed[0]["id"] == record["id"]


def test_mark_reviewed_excludes_from_unreviewed(monkeypatch, tmp_path):
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")

    record = error_log.log_error("some_source", ValueError("テストエラー"))
    error_log.mark_reviewed(record["id"])

    assert error_log.get_unreviewed_errors() == []


def test_multiple_errors_are_independent(monkeypatch, tmp_path):
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")

    error_log.log_error("source_a", ValueError("エラーA"))
    record_b = error_log.log_error("source_b", RuntimeError("エラーB"))
    error_log.mark_reviewed(record_b["id"])

    unreviewed = error_log.get_unreviewed_errors()
    assert len(unreviewed) == 1
    assert unreviewed[0]["source"] == "source_a"
