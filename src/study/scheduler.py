"""夜間修行(Autonomous Study Loop)の自動トリガー。

src/memory/scheduler.pyと全く同じ考え方: 真のOSアイドル検知やlaunchdでの
スケジューリングの代わりに、「1日に1回、アプリ起動時にまだ実行していなければ
実行する」という形で近似する。launchdの有効化(launchctl load)は那由多さんの
確認なしには行わない方針のため、これがGEMINI_API_KEY設定済み環境で夜間修行を
実際に動かす唯一の経路になる。
"""
from __future__ import annotations

from datetime import date

from rich.console import Console

from config.settings import STUDY_MARKER_FILE
from src.study.study_session import run_study_session

console = Console()


def maybe_run_daily_study() -> None:
    """今日まだ夜間修行を実行していなければ実行し、マーカーファイルを更新する。

    Gradio(shisui_app.py)とFastAPI(src/api/main.py)を両方起動していると、
    ほぼ同時に両方のプロセスがこの関数を呼ぶため、「マーカーを確認してから
    実行し、完了後に書き込む」だけでは間に合わず二重実行してしまう
    (実際に両方が同時に夜間修行を始め、Ollamaの同時実行数上限に引っかかって
    チャット応答が止まった)。マーカーを排他的(exclusive)に先に確保することで、
    先着した1プロセスだけが実行するようにする。
    """
    today = date.today().isoformat()

    if STUDY_MARKER_FILE.exists():
        if STUDY_MARKER_FILE.read_text(encoding="utf-8").strip() == today:
            return
        STUDY_MARKER_FILE.unlink()

    try:
        with open(STUDY_MARKER_FILE, "x", encoding="utf-8") as f:
            f.write(today)
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
