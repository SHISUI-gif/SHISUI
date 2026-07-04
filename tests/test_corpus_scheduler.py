"""青空文庫全体クロールの「夜間帯にまだ実行していなければ実行する」スケジューラーを検証する。

night_schedule.current_night_key()は実行時刻に依存するため、
tests/test_daily_schedulers.pyと同じく固定の夜キーを返すようmonkeypatchする。
"""
from src.core import night_schedule
from src.corpus import scheduler as corpus_scheduler

FIXED_NIGHT_KEY = "2026-01-01"


class _FakeResult:
    def __init__(self, complete=False, ingested_this_run=0, **extra):
        self.complete = complete
        self.ingested_this_run = ingested_this_run
        for key, value in extra.items():
            setattr(self, key, value)


def test_maybe_run_nightly_archive_crawl_runs_when_marker_missing(monkeypatch, tmp_path):
    marker = tmp_path / "last_archive_crawl_date.txt"
    monkeypatch.setattr(corpus_scheduler, "AOZORA_ARCHIVE_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)

    calls = []
    monkeypatch.setattr(
        corpus_scheduler,
        "run_daily_archive_crawl",
        lambda: calls.append(1) or _FakeResult(),
    )

    corpus_scheduler.maybe_run_nightly_archive_crawl()

    assert calls == [1]
    assert marker.read_text(encoding="utf-8").strip() == FIXED_NIGHT_KEY


def test_maybe_run_nightly_archive_crawl_skips_outside_night_window(monkeypatch, tmp_path):
    marker = tmp_path / "last_archive_crawl_date.txt"
    monkeypatch.setattr(corpus_scheduler, "AOZORA_ARCHIVE_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: None)

    calls = []
    monkeypatch.setattr(corpus_scheduler, "run_daily_archive_crawl", lambda: calls.append(1))

    corpus_scheduler.maybe_run_nightly_archive_crawl()

    assert calls == []
    assert not marker.exists()


def test_maybe_run_nightly_archive_crawl_skips_when_already_run_tonight(monkeypatch, tmp_path):
    marker = tmp_path / "last_archive_crawl_date.txt"
    marker.write_text(FIXED_NIGHT_KEY, encoding="utf-8")
    monkeypatch.setattr(corpus_scheduler, "AOZORA_ARCHIVE_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)

    calls = []
    monkeypatch.setattr(corpus_scheduler, "run_daily_archive_crawl", lambda: calls.append(1))

    corpus_scheduler.maybe_run_nightly_archive_crawl()

    assert calls == []


def test_maybe_run_nightly_archive_crawl_skips_when_another_process_just_claimed_it(
    monkeypatch, tmp_path
):
    marker = tmp_path / "last_archive_crawl_date.txt"
    monkeypatch.setattr(corpus_scheduler, "AOZORA_ARCHIVE_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)
    marker.write_text(FIXED_NIGHT_KEY, encoding="utf-8")

    calls = []
    monkeypatch.setattr(corpus_scheduler, "run_daily_archive_crawl", lambda: calls.append(1))

    corpus_scheduler.maybe_run_nightly_archive_crawl()

    assert calls == []
