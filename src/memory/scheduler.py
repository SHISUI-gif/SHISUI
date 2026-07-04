"""睡眠モードの自動トリガー。

真のOSアイドル検知はプラットフォーム依存で複雑なため、「1日の終わりに実行」を
「1日に1回、チャット/音声会話の起動時にまだ実行していなければ実行する」という
形で近似する。マーカーファイルに最後に実行した日付を保存し、日付が変わっていたら
睡眠サイクルを走らせる。失敗しても会話の起動自体はブロックしない。
"""
from __future__ import annotations

from datetime import date

from rich.console import Console

from config.settings import SLEEP_MARKER_FILE
from src.memory.sleep import run_sleep_cycle

console = Console()


def maybe_run_daily_sleep() -> None:
    """今日まだ睡眠モードを実行していなければ実行し、マーカーファイルを更新する。

    Gradio・FastAPIを両方起動していると、ほぼ同時に両方のプロセスがこの関数を
    呼ぶため、マーカーを排他的(exclusive)に先に確保することで、先着した
    1プロセスだけが実行するようにする。
    """
    today = date.today().isoformat()

    if SLEEP_MARKER_FILE.exists():
        if SLEEP_MARKER_FILE.read_text(encoding="utf-8").strip() == today:
            return
        SLEEP_MARKER_FILE.unlink()

    try:
        with open(SLEEP_MARKER_FILE, "x", encoding="utf-8") as f:
            f.write(today)
    except FileExistsError:
        return  # 別プロセスがこの瞬間に既に確保した

    try:
        result = run_sleep_cycle()
        if result.episodes_considered:
            console.print(
                f"[dim]💤 睡眠モード実行: エピソード{result.episodes_considered}件を統合、"
                f"新規/更新メモリ{result.memories_added}件[/dim]"
            )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]睡眠モードの自動実行に失敗しました(会話は続行します): {exc}[/yellow]")
