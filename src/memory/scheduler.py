"""睡眠モードの自動トリガー。

「夜眠っている間だけ学習している」というコンセプトに合わせ、夜間帯
(既定23:00〜翌6:30、src/core/night_schedule.py参照)の間だけ実行する。
マーカーファイルにその夜のキーを保存し、まだ実行していない夜であれば
睡眠サイクルを走らせる。失敗しても会話の起動自体はブロックしない。
"""
from __future__ import annotations

from rich.console import Console

from config.settings import SLEEP_MARKER_FILE
from src.core import activity_log, night_schedule
from src.memory.sleep import run_sleep_cycle

console = Console()


def maybe_run_nightly_sleep() -> None:
    """今夜まだ睡眠モードを実行していなければ実行し、マーカーファイルを更新する。

    夜間帯(既定23:00〜翌6:30)の外であれば何もしない。
    Gradio・FastAPIを両方起動していると、ほぼ同時に両方のプロセスがこの関数を
    呼ぶため、マーカーを排他的(exclusive)に先に確保することで、先着した
    1プロセスだけが実行するようにする。
    """
    night_key = night_schedule.current_night_key()
    if night_key is None:
        return

    if SLEEP_MARKER_FILE.exists():
        if SLEEP_MARKER_FILE.read_text(encoding="utf-8").strip() == night_key:
            return
        SLEEP_MARKER_FILE.unlink()

    try:
        with open(SLEEP_MARKER_FILE, "x", encoding="utf-8") as f:
            f.write(night_key)
    except FileExistsError:
        return  # 別プロセスがこの瞬間に既に確保した

    try:
        result = run_sleep_cycle()
        if result.episodes_considered:
            console.print(
                f"[dim]💤 睡眠モード実行: エピソード{result.episodes_considered}件を統合、"
                f"新規/更新メモリ{result.memories_added}件[/dim]"
            )
            learned_texts = [
                item.get("text", "").strip()
                for item in result.raw_extractions
                if item.get("text", "").strip()
            ]
            summary = f"睡眠モード: 新規/更新メモリ{result.memories_added}件"
            if learned_texts:
                preview = "、".join(learned_texts[:3])
                summary += f"(学んだこと: {preview})"
            if result.items_unlocked:
                summary += f"、アバターアイテム{result.items_unlocked}件解除"
            activity_log.log_activity(
                kind="sleep",
                summary=summary,
                details={
                    "episodes_considered": result.episodes_considered,
                    "memories_added": result.memories_added,
                    "memories_superseded": result.memories_superseded,
                    "items_unlocked": result.items_unlocked,
                    "learned": learned_texts,
                },
            )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]睡眠モードの自動実行に失敗しました(会話は続行します): {exc}[/yellow]")
