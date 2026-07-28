"""夜間修行(Autonomous Study Loop)の自動トリガー。

src/memory/scheduler.pyと同じ考え方: 「夜眠っている間だけ学習している」という
コンセプトに合わせ、夜間帯(既定23:00〜翌6:30、src/core/night_schedule.py参照)の
間だけ実行する。launchdの有効化(launchctl load)は那由多さんの確認なしには
行わない方針のため、これがGEMINI_API_KEY設定済み環境で夜間修行を実際に動かす
唯一の経路になる。
"""
from __future__ import annotations

from rich.console import Console

from config.settings import EXTERNAL_DIALOGUE_MARKER_FILE, STUDY_MARKER_FILE
from src.core import night_schedule
from src.study.external_dialogue import run_external_dialogue_session
from src.study.study_session import run_study_session

console = Console()


def maybe_run_nightly_study() -> None:
    """今夜まだ夜間修行を実行していなければ実行し、マーカーファイルを更新する。

    夜間帯(既定23:00〜翌6:30)の外であれば何もしない。
    Gradio(shisui_app.py)とFastAPI(src/api/main.py)を両方起動していると、
    ほぼ同時に両方のプロセスがこの関数を呼ぶため、「マーカーを確認してから
    実行し、完了後に書き込む」だけでは間に合わず二重実行してしまう
    (実際に両方が同時に夜間修行を始め、Ollamaの同時実行数上限に引っかかって
    チャット応答が止まった)。マーカーを排他的(exclusive)に先に確保することで、
    先着した1プロセスだけが実行するようにする。
    """
    night_key = night_schedule.current_night_key()
    if night_key is None:
        return

    if STUDY_MARKER_FILE.exists():
        if STUDY_MARKER_FILE.read_text(encoding="utf-8").strip() == night_key:
            return
        STUDY_MARKER_FILE.unlink()

    try:
        with open(STUDY_MARKER_FILE, "x", encoding="utf-8") as f:
            f.write(night_key)
    except FileExistsError:
        return  # 別プロセスがこの瞬間に既に確保した

    try:
        result = run_study_session()
        if not result.skipped:
            console.print(
                f"[dim]📚 夜間修行実行: {len(result.topics_studied)}トピックを学習、"
                f"Gemini呼び出し{result.gemini_calls}回[/dim]"
            )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]夜間修行の自動実行に失敗しました(会話は続行します): {exc}[/yellow]")


def maybe_run_nightly_external_dialogue() -> None:
    """今夜まだ夜間対話(先輩AI、OpenRouter無料枠)を実行していなければ実行する。

    夜間修行(Gemini)とは別マーカー・別ジョブとして独立に動く。
    OPENROUTER_API_KEY未設定ならrun_external_dialogue_session()側で静かに
    スキップされる(こちらでは判定しない、study.scheduler全体の設計を統一するため)。
    マーカーの排他確保はmaybe_run_nightly_studyと同じ理由・同じ仕組み。
    """
    night_key = night_schedule.current_night_key()
    if night_key is None:
        return

    if EXTERNAL_DIALOGUE_MARKER_FILE.exists():
        if EXTERNAL_DIALOGUE_MARKER_FILE.read_text(encoding="utf-8").strip() == night_key:
            return
        EXTERNAL_DIALOGUE_MARKER_FILE.unlink()

    try:
        with open(EXTERNAL_DIALOGUE_MARKER_FILE, "x", encoding="utf-8") as f:
            f.write(night_key)
    except FileExistsError:
        return  # 別プロセスがこの瞬間に既に確保した

    try:
        result = run_external_dialogue_session()
        if not result.skipped:
            console.print(
                f"[dim]🌐 夜間対話実行: {len(result.topics_discussed)}トピックについて先輩AIと話した[/dim]"
            )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]夜間対話の自動実行に失敗しました(会話は続行します): {exc}[/yellow]")
