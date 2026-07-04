"""睡眠モード・夜間修行・自律討論など、志粋の自律活動の記録。

error_log.py/feedback_log.pyと同じJSONファイル追記方式。特定の友達に
紐づくものではなく「志粋自身の自律活動」なので、ログインユーザーを問わず
同じ内容を返す(neocortex.SYSTEM_USER_IDと同じ考え方)。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from config.settings import ACTIVITY_LOG_FILE

ActivityKind = Literal["sleep", "study", "debate"]


def _load_all() -> list[dict]:
    if not ACTIVITY_LOG_FILE.exists():
        return []
    return json.loads(ACTIVITY_LOG_FILE.read_text(encoding="utf-8"))


def _save_all(records: list[dict]) -> None:
    ACTIVITY_LOG_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def log_activity(kind: ActivityKind, summary: str, details: dict | None = None) -> dict:
    """自律活動を1件記録する。記録したレコードをそのまま返す。"""
    records = _load_all()
    record = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "kind": kind,
        "summary": summary,
        "details": details or {},
    }
    records.append(record)
    _save_all(records)
    return record


def get_recent_activity(limit: int = 20) -> list[dict]:
    """直近の活動を新しい順にlimit件返す。"""
    records = _load_all()
    return list(reversed(records))[:limit]
