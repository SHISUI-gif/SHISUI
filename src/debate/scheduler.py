"""自律討論(夜間修行とは別ジョブ)の自動トリガー。

src/memory/scheduler.py・src/study/scheduler.pyと同じ考え方: 「夜眠っている間
だけ学習している」というコンセプトに合わせ、夜間帯(既定23:00〜翌6:30、
src/core/night_schedule.py参照)の間だけ実行する。launchdの有効化
(launchctl load)は那由多さんの確認なしには行わない方針のため、これが
実際に動かす唯一の経路になる。
"""
from __future__ import annotations

from rich.console import Console

from config.settings import DEBATE_AUTONOMOUS_MARKER_FILE
from src.core import night_schedule
from src.debate.autonomous import run_autonomous_debate

console = Console()


def maybe_run_nightly_debate_autonomous() -> None:
    """今夜まだ自律討論を実行していなければ実行し、マーカーファイルを更新する。

    夜間帯(既定23:00〜翌6:30)の外であれば何もしない。
    Gradio・FastAPIを両方起動していると、ほぼ同時に両方のプロセスがこの関数を
    呼ぶため、マーカーを排他的(exclusive)に先に確保することで、先着した
    1プロセスだけが実行するようにする(src/study/scheduler.pyと同じ理由)。
    """
    night_key = night_schedule.current_night_key()
    if night_key is None:
        return

    if DEBATE_AUTONOMOUS_MARKER_FILE.exists():
        if DEBATE_AUTONOMOUS_MARKER_FILE.read_text(encoding="utf-8").strip() == night_key:
            return
        DEBATE_AUTONOMOUS_MARKER_FILE.unlink()

    try:
        with open(DEBATE_AUTONOMOUS_MARKER_FILE, "x", encoding="utf-8") as f:
            f.write(night_key)
    except FileExistsError:
        return  # 別プロセスがこの瞬間に既に確保した

    try:
        result = run_autonomous_debate()
        if not result.skipped:
            console.print(f"[dim]🗣️ 自律討論実行: {len(result.topics_debated)}トピックを討論[/dim]")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]自律討論の自動実行に失敗しました(会話は続行します): {exc}[/yellow]")
