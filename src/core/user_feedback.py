"""ユーザーからの能動的なフィードバック・要望(「〜もできたらいいな」等)。

feedback_log.py(訂正・不満の自動検知)とは別物: あちらは会話中の訂正を
キーワードで自動検知するのに対し、こちらはユーザーが能動的に「志粋への
要望・フィードバック」として送信する、会話の訂正に紐付かない自由記述。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from config.settings import USER_FEEDBACK_FILE


def _load_all() -> list[dict]:
    if not USER_FEEDBACK_FILE.exists():
        return []
    return json.loads(USER_FEEDBACK_FILE.read_text(encoding="utf-8"))


def _save_all(records: list[dict]) -> None:
    USER_FEEDBACK_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def submit_feedback(user_id: int, user_name: str, content: str) -> dict:
    """要望・フィードバックを1件記録する。user_id/user_nameは呼び出し側が
    認証トークンから取得した値を渡すこと(リクエストボディの値を信用しない)。"""
    records = _load_all()
    record = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "user_id": user_id,
        "user_name": user_name,
        "content": content,
        "reviewed": False,
    }
    records.append(record)
    _save_all(records)
    return record


def get_all_feedback() -> list[dict]:
    """全フィードバックを新しい順で返す。"""
    return list(reversed(_load_all()))


def mark_reviewed(feedback_id: str) -> None:
    records = _load_all()
    for record in records:
        if record["id"] == feedback_id:
            record["reviewed"] = True
    _save_all(records)
