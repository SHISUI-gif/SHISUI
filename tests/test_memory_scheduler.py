"""睡眠モードの自動トリガー(src/memory/scheduler.py)を検証する。

2026-07-28、那由多さんの要望(睡眠学習が始まったことがその場で分かるように
してほしい)を受けて追加した「開始マーカー」「開始時のactivity_log記録」を
中心に検証する。run_sleep_cycle()自体・night_schedule自体はモックする。
"""
from src.core import activity_log, night_schedule
from src.memory import scheduler
from src.memory.sleep import SleepCycleResult


def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(scheduler, "SLEEP_MARKER_FILE", tmp_path / "last_sleep_date.txt")
    monkeypatch.setattr(scheduler, "SLEEP_IN_PROGRESS_FILE", tmp_path / "sleep_in_progress.marker")
    monkeypatch.setattr(activity_log, "ACTIVITY_LOG_FILE", tmp_path / "activity_log.json")
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: "2026-07-28")


def test_maybe_run_nightly_sleep_creates_and_clears_in_progress_marker(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    seen_during_run = {}

    def fake_run_sleep_cycle():
        seen_during_run["in_progress"] = scheduler.SLEEP_IN_PROGRESS_FILE.exists()
        return SleepCycleResult(episodes_considered=0, memories_added=0, memories_superseded=0)

    monkeypatch.setattr(scheduler, "run_sleep_cycle", fake_run_sleep_cycle)

    scheduler.maybe_run_nightly_sleep()

    assert seen_during_run["in_progress"] is True
    assert not scheduler.SLEEP_IN_PROGRESS_FILE.exists()


def test_maybe_run_nightly_sleep_clears_marker_even_if_cycle_raises(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)

    def fake_run_sleep_cycle():
        raise RuntimeError("何か壊れた")

    monkeypatch.setattr(scheduler, "run_sleep_cycle", fake_run_sleep_cycle)

    scheduler.maybe_run_nightly_sleep()  # 例外を外に漏らさないこと

    assert not scheduler.SLEEP_IN_PROGRESS_FILE.exists()


def test_maybe_run_nightly_sleep_logs_start_activity(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(
        scheduler,
        "run_sleep_cycle",
        lambda: SleepCycleResult(episodes_considered=0, memories_added=0, memories_superseded=0),
    )

    scheduler.maybe_run_nightly_sleep()

    recent = activity_log.get_recent_activity()
    start_entries = [a for a in recent if a["kind"] == "sleep" and a["details"].get("phase") == "start"]
    assert len(start_entries) == 1


def test_maybe_run_nightly_sleep_skips_when_already_run_tonight(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(
        scheduler,
        "run_sleep_cycle",
        lambda: (calls.append(1), SleepCycleResult(0, 0, 0))[1],
    )

    scheduler.maybe_run_nightly_sleep()
    scheduler.maybe_run_nightly_sleep()

    assert calls == [1]
