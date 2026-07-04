"""夜間修行・自律討論の「夜間帯にまだ実行していなければ実行する」スケジューラーを検証する。

src/memory/scheduler.pyと同じ設計思想の2つのモジュール
(src/study/scheduler.py・src/debate/scheduler.py)をまとめて検証する。

マーカーは「実行完了後」ではなく「実行開始前」に排他的(exclusive)に確保する
設計になっている。Gradio・FastAPIを同時起動した際に両方のプロセスがほぼ同時に
これらの関数を呼び、どちらも「今夜はまだ」と判定して二重実行してしまう
(実際にOllamaの同時実行数上限に引っかかってチャット応答が止まった)不具合を
踏まえた変更のため、そのトレードオフ(失敗時もマーカーは残り、その夜の
再試行はしない)も含めて検証する。

night_schedule.current_night_key()は実行時刻に依存するため、テストでは
固定の夜キーを返すようmonkeypatchし、実際に動かすタイミングに関わらず
決定的に検証できるようにしている。
"""
from src.core import night_schedule
from src.debate import scheduler as debate_scheduler
from src.study import scheduler as study_scheduler

FIXED_NIGHT_KEY = "2026-01-01"


class _FakeResult:
    def __init__(self, skipped=False, **extra):
        self.skipped = skipped
        for key, value in extra.items():
            setattr(self, key, value)


def test_maybe_run_nightly_study_runs_when_marker_missing(monkeypatch, tmp_path):
    marker = tmp_path / "last_study_date.txt"
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)

    calls = []
    monkeypatch.setattr(
        study_scheduler,
        "run_study_session",
        lambda: calls.append(1) or _FakeResult(topics_studied=[], gemini_calls=0),
    )

    study_scheduler.maybe_run_nightly_study()

    assert calls == [1]
    assert marker.read_text(encoding="utf-8").strip() == FIXED_NIGHT_KEY


def test_maybe_run_nightly_study_skips_outside_night_window(monkeypatch, tmp_path):
    marker = tmp_path / "last_study_date.txt"
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: None)

    calls = []
    monkeypatch.setattr(study_scheduler, "run_study_session", lambda: calls.append(1))

    study_scheduler.maybe_run_nightly_study()

    assert calls == []
    assert not marker.exists()


def test_maybe_run_nightly_study_skips_when_already_run_tonight(monkeypatch, tmp_path):
    marker = tmp_path / "last_study_date.txt"
    marker.write_text(FIXED_NIGHT_KEY, encoding="utf-8")
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)

    calls = []
    monkeypatch.setattr(study_scheduler, "run_study_session", lambda: calls.append(1))

    study_scheduler.maybe_run_nightly_study()

    assert calls == []


def test_maybe_run_nightly_study_replaces_stale_marker_from_previous_night(monkeypatch, tmp_path):
    marker = tmp_path / "last_study_date.txt"
    marker.write_text("2025-12-31", encoding="utf-8")
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)

    calls = []
    monkeypatch.setattr(
        study_scheduler,
        "run_study_session",
        lambda: calls.append(1) or _FakeResult(topics_studied=[], gemini_calls=0),
    )

    study_scheduler.maybe_run_nightly_study()

    assert calls == [1]
    assert marker.read_text(encoding="utf-8").strip() == FIXED_NIGHT_KEY


def test_maybe_run_nightly_study_skips_when_another_process_just_claimed_it(monkeypatch, tmp_path):
    """GradioとFastAPIがほぼ同時に起動した場合を模す: このプロセスが確認する前に
    別プロセスが既に今夜のマーカーを作成していたら、実行せずスキップする。"""
    marker = tmp_path / "last_study_date.txt"
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)
    marker.write_text(FIXED_NIGHT_KEY, encoding="utf-8")  # 別プロセスが確保済み

    calls = []
    monkeypatch.setattr(study_scheduler, "run_study_session", lambda: calls.append(1))

    study_scheduler.maybe_run_nightly_study()

    assert calls == []


def test_maybe_run_nightly_study_leaves_marker_on_failure(monkeypatch, tmp_path):
    """失敗してもマーカーは残す(その夜のうちの再試行はしない、というトレードオフ)。
    これは二重実行を防ぐため、実行前にマーカーを確保する設計上の必然的な帰結。"""
    marker = tmp_path / "last_study_date.txt"
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)

    def raise_missing_key():
        raise ValueError("GEMINI_API_KEYが設定されていません。")

    monkeypatch.setattr(study_scheduler, "run_study_session", raise_missing_key)

    study_scheduler.maybe_run_nightly_study()  # 例外を外に漏らさないこと

    assert marker.read_text(encoding="utf-8").strip() == FIXED_NIGHT_KEY


def test_maybe_run_nightly_debate_autonomous_runs_when_marker_missing(monkeypatch, tmp_path):
    marker = tmp_path / "last_autonomous_debate_date.txt"
    monkeypatch.setattr(debate_scheduler, "DEBATE_AUTONOMOUS_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)

    calls = []
    monkeypatch.setattr(
        debate_scheduler,
        "run_autonomous_debate",
        lambda: calls.append(1) or _FakeResult(topics_debated=[]),
    )

    debate_scheduler.maybe_run_nightly_debate_autonomous()

    assert calls == [1]
    assert marker.read_text(encoding="utf-8").strip() == FIXED_NIGHT_KEY


def test_maybe_run_nightly_debate_autonomous_skips_outside_night_window(monkeypatch, tmp_path):
    marker = tmp_path / "last_autonomous_debate_date.txt"
    monkeypatch.setattr(debate_scheduler, "DEBATE_AUTONOMOUS_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: None)

    calls = []
    monkeypatch.setattr(debate_scheduler, "run_autonomous_debate", lambda: calls.append(1))

    debate_scheduler.maybe_run_nightly_debate_autonomous()

    assert calls == []
    assert not marker.exists()


def test_maybe_run_nightly_debate_autonomous_skips_when_already_run_tonight(monkeypatch, tmp_path):
    marker = tmp_path / "last_autonomous_debate_date.txt"
    marker.write_text(FIXED_NIGHT_KEY, encoding="utf-8")
    monkeypatch.setattr(debate_scheduler, "DEBATE_AUTONOMOUS_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)

    calls = []
    monkeypatch.setattr(debate_scheduler, "run_autonomous_debate", lambda: calls.append(1))

    debate_scheduler.maybe_run_nightly_debate_autonomous()

    assert calls == []


def test_maybe_run_nightly_debate_autonomous_skips_when_another_process_just_claimed_it(
    monkeypatch, tmp_path
):
    marker = tmp_path / "last_autonomous_debate_date.txt"
    monkeypatch.setattr(debate_scheduler, "DEBATE_AUTONOMOUS_MARKER_FILE", marker)
    monkeypatch.setattr(night_schedule, "current_night_key", lambda: FIXED_NIGHT_KEY)
    marker.write_text(FIXED_NIGHT_KEY, encoding="utf-8")

    calls = []
    monkeypatch.setattr(debate_scheduler, "run_autonomous_debate", lambda: calls.append(1))

    debate_scheduler.maybe_run_nightly_debate_autonomous()

    assert calls == []
