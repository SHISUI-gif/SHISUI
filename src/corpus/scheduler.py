"""青空文庫全体クロールの自動トリガー。

src/memory/scheduler.pyと同じ考え方: 夜間帯(既定23:00〜翌6:30、
src/core/night_schedule.py参照)の間だけ実行する。1回の実行では
`settings.aozora_archive_daily_limit`件だけ進めるため、毎晩少しずつ
青空文庫全体を読み進めることになる。失敗しても会話の起動はブロックしない。
"""
from __future__ import annotations

from rich.console import Console

from config.settings import AOZORA_ARCHIVE_MARKER_FILE
from src.core import night_schedule
from src.corpus.full_archive import run_daily_archive_crawl

console = Console()


def maybe_run_nightly_archive_crawl() -> None:
    """今夜まだ青空文庫全体クロールを実行していなければ実行し、マーカーファイルを更新する。

    夜間帯(既定23:00〜翌6:30)の外であれば何もしない。
    Gradio・FastAPIを両方起動していると、ほぼ同時に両方のプロセスがこの関数を
    呼ぶため、マーカーを排他的(exclusive)に先に確保することで、先着した
    1プロセスだけが実行するようにする。
    """
    night_key = night_schedule.current_night_key()
    if night_key is None:
        return

    if AOZORA_ARCHIVE_MARKER_FILE.exists():
        if AOZORA_ARCHIVE_MARKER_FILE.read_text(encoding="utf-8").strip() == night_key:
            return
        AOZORA_ARCHIVE_MARKER_FILE.unlink()

    try:
        with open(AOZORA_ARCHIVE_MARKER_FILE, "x", encoding="utf-8") as f:
            f.write(night_key)
    except FileExistsError:
        return  # 別プロセスがこの瞬間に既に確保した

    try:
        result = run_daily_archive_crawl()
        if result.complete:
            console.print("[dim]📚 青空文庫全体クロール: 全作品の取り込みが完了しました[/dim]")
        elif result.ingested_this_run:
            console.print(
                f"[dim]📚 青空文庫全体クロール: 本日{result.ingested_this_run}件取り込み"
                f"(累計{result.total_ingested}件、現在の作家: {result.current_author})[/dim]"
            )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]青空文庫全体クロールの自動実行に失敗しました(会話は続行します): {exc}[/yellow]")
