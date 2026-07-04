"""睡眠・自律学習・自律討論を「夜眠っている間」だけ動かす夜間帯判定を検証する。

既定の夜間帯は23:00〜翌6:30。境界値(開始・終了ちょうど)と、日付をまたぐ
ケース(深夜0時台〜早朝)を中心に検証する。
"""
from datetime import datetime

from src.core import night_schedule


def _dt(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute)


def test_is_within_night_window_true_at_23_00():
    now = _dt(2026, 3, 5, 23, 0)
    assert night_schedule.is_within_night_window(now) is True


def test_is_within_night_window_true_just_before_end():
    now = _dt(2026, 3, 6, 6, 30)
    assert night_schedule.is_within_night_window(now) is True


def test_is_within_night_window_false_just_after_end():
    now = _dt(2026, 3, 6, 6, 31)
    assert night_schedule.is_within_night_window(now) is False


def test_is_within_night_window_false_during_daytime():
    now = _dt(2026, 3, 5, 14, 0)
    assert night_schedule.is_within_night_window(now) is False


def test_is_within_night_window_false_just_before_start():
    now = _dt(2026, 3, 5, 22, 59)
    assert night_schedule.is_within_night_window(now) is False


def test_current_night_key_during_late_evening_is_todays_date():
    now = _dt(2026, 3, 5, 23, 30)
    assert night_schedule.current_night_key(now) == "2026-03-05"


def test_current_night_key_after_midnight_is_previous_days_date():
    now = _dt(2026, 3, 6, 2, 0)
    assert night_schedule.current_night_key(now) == "2026-03-05"


def test_current_night_key_none_outside_window():
    now = _dt(2026, 3, 6, 12, 0)
    assert night_schedule.current_night_key(now) is None


def test_current_night_key_none_right_after_end():
    now = _dt(2026, 3, 6, 6, 31)
    assert night_schedule.current_night_key(now) is None
