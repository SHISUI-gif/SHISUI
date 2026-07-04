"""睡眠・自律学習・自律討論を「夜眠っている間」だけ動かすための夜間帯判定。

3つのスケジューラ(src/memory/scheduler.py・src/study/scheduler.py・
src/debate/scheduler.py)で同じ判定ロジックを重複させないよう、ここに集約する。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from config.settings import settings


def is_within_night_window(now: datetime | None = None) -> bool:
    """現在時刻が夜間帯(既定23:00〜翌6:30)内かどうかを返す。"""
    return current_night_key(now) is not None


def current_night_key(now: datetime | None = None) -> str | None:
    """今が夜間帯内なら、その「夜」を表す日付文字列(夜が始まった日の日付)を返す。

    夜間帯は日付をまたぐため(例: 23:00〜翌6:30)、日付が変わった直後の時刻でも
    同じ「夜」として扱えるよう、夜が始まった側の日付をキーにする。
    範囲外なら None を返す。
    """
    now = now or datetime.now()
    start = now.replace(
        hour=settings.night_mode_start_hour, minute=0, second=0, microsecond=0
    )

    if now >= start:
        # 23:00〜23:59台: 今日の夜として扱う
        return now.date().isoformat()

    end = now.replace(
        hour=settings.night_mode_end_hour,
        minute=settings.night_mode_end_minute,
        second=0,
        microsecond=0,
    )
    if now <= end:
        # 0:00〜6:30台: 前日の夜の続きとして扱う
        previous_day = now.date() - timedelta(days=1)
        return previous_day.isoformat()

    return None
