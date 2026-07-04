"""夜間修行・自律討論の「アプリ起動時に1日1回」スケジューラーを検証する。

src/memory/scheduler.pyと同じ設計思想の2つのモジュール
(src/study/scheduler.py・src/debate/scheduler.py)をまとめて検証する。

マーカーは「実行完了後」ではなく「実行開始前」に排他的(exclusive)に確保する
設計になっている。Gradio・FastAPIを同時起動した際に両方のプロセスがほぼ同時に
これらの関数を呼び、どちらも「今日はまだ」と判定して二重実行してしまう
(実際にOllamaの同時実行数上限に引っかかってチャット応答が止まった)不具合を
踏まえた変更のため、そのトレードオフ(失敗時もマーカーは残り、その日は
再試行しない)も含めて検証する。
"""
from datetime import date, timedelta

from src.debate import scheduler as debate_scheduler
from src.study import scheduler as study_scheduler


class _FakeResult:
    def __init__(self, skipped=False, **extra):
        self.skipped = skipped
        for key, value in extra.items():
            setattr(self, key, value)


def test_maybe_run_daily_study_runs_when_marker_missing(monkeypatch, tmp_path):
    marker = tmp_path / "last_study_date.txt"
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)

    calls = []
    monkeypatch.setattr(
        study_scheduler,
        "run_study_session",
        lambda: calls.append(1) or _FakeResult(topics_studied=[], gemini_calls=0),
    )

    study_scheduler.maybe_run_daily_study()

    assert calls == [1]
    assert marker.read_text(encoding="utf-8").strip() == date.today().isoformat()


def test_maybe_run_daily_study_skips_when_already_run_today(monkeypatch, tmp_path):
    marker = tmp_path / "last_study_date.txt"
    marker.write_text(date.today().isoformat(), encoding="utf-8")
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)

    calls = []
    monkeypatch.setattr(study_scheduler, "run_study_session", lambda: calls.append(1))

    study_scheduler.maybe_run_daily_study()

    assert calls == []


def test_maybe_run_daily_study_replaces_stale_marker_from_previous_day(monkeypatch, tmp_path):
    marker = tmp_path / "last_study_date.txt"
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    marker.write_text(yesterday, encoding="utf-8")
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)

    calls = []
    monkeypatch.setattr(
        study_scheduler,
        "run_study_session",
        lambda: calls.append(1) or _FakeResult(topics_studied=[], gemini_calls=0),
    )

    study_scheduler.maybe_run_daily_study()

    assert calls == [1]
    assert marker.read_text(encoding="utf-8").strip() == date.today().isoformat()


def test_maybe_run_daily_study_skips_when_another_process_just_claimed_it(monkeypatch, tmp_path):
    """GradioとFastAPIがほぼ同時に起動した場合を模す: このプロセスが確認する前に
    別プロセスが既に今日のマーカーを作成していたら、実行せずスキップする。"""
    marker = tmp_path / "last_study_date.txt"
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)
    marker.write_text(date.today().isoformat(), encoding="utf-8")  # 別プロセスが確保済み

    calls = []
    monkeypatch.setattr(study_scheduler, "run_study_session", lambda: calls.append(1))

    study_scheduler.maybe_run_daily_study()

    assert calls == []


def test_maybe_run_daily_study_leaves_marker_on_failure(monkeypatch, tmp_path):
    """失敗してもマーカーは残す(その日のうちの再試行はしない、というトレードオフ)。
    これは二重実行を防ぐため、実行前にマーカーを確保する設計上の必然的な帰結。"""
    marker = tmp_path / "last_study_date.txt"
    monkeypatch.setattr(study_scheduler, "STUDY_MARKER_FILE", marker)

    def raise_missing_key():
        raise ValueError("GEMINI_API_KEYが設定されていません。")

    monkeypatch.setattr(study_scheduler, "run_study_session", raise_missing_key)

    study_scheduler.maybe_run_daily_study()  # 例外を外に漏らさないこと

    assert marker.read_text(encoding="utf-8").strip() == date.today().isoformat()


def test_maybe_run_daily_debate_autonomous_runs_when_marker_missing(monkeypatch, tmp_path):
    marker = tmp_path / "last_autonomous_debate_date.txt"
    monkeypatch.setattr(debate_scheduler, "DEBATE_AUTONOMOUS_MARKER_FILE", marker)

    calls = []
    monkeypatch.setattr(
        debate_scheduler,
        "run_autonomous_debate",
        lambda: calls.append(1) or _FakeResult(topics_debated=[]),
    )

    debate_scheduler.maybe_run_daily_debate_autonomous()

    assert calls == [1]
    assert marker.read_text(encoding="utf-8").strip() == date.today().isoformat()


def test_maybe_run_daily_debate_autonomous_skips_when_already_run_today(monkeypatch, tmp_path):
    marker = tmp_path / "last_autonomous_debate_date.txt"
    marker.write_text(date.today().isoformat(), encoding="utf-8")
    monkeypatch.setattr(debate_scheduler, "DEBATE_AUTONOMOUS_MARKER_FILE", marker)

    calls = []
    monkeypatch.setattr(debate_scheduler, "run_autonomous_debate", lambda: calls.append(1))

    debate_scheduler.maybe_run_daily_debate_autonomous()

    assert calls == []


def test_maybe_run_daily_debate_autonomous_skips_when_another_process_just_claimed_it(
    monkeypatch, tmp_path
):
    marker = tmp_path / "last_autonomous_debate_date.txt"
    monkeypatch.setattr(debate_scheduler, "DEBATE_AUTONOMOUS_MARKER_FILE", marker)
    marker.write_text(date.today().isoformat(), encoding="utf-8")

    calls = []
    monkeypatch.setattr(debate_scheduler, "run_autonomous_debate", lambda: calls.append(1))

    debate_scheduler.maybe_run_daily_debate_autonomous()

    assert calls == []
