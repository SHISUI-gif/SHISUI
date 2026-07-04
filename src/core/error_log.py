"""実行時に起きたエラーを永続化するログ。

自己修復プロトコル(src/core/evolution.py)への入力になる。志粋の会話中に
何らかの例外が発生した場合、ユーザーには友好的なメッセージだけを見せつつ、
ここに完全なトレースバックを記録しておくことで、後から「何を直すべきか」を
機械的に洗い出せるようにする。
"""
from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime

from config.settings import ERROR_LOG_FILE


def _load_all() -> list[dict]:
    if not ERROR_LOG_FILE.exists():
        return []
    return json.loads(ERROR_LOG_FILE.read_text(encoding="utf-8"))


def _save_all(records: list[dict]) -> None:
    ERROR_LOG_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def log_error(source: str, exc: Exception) -> dict:
    """例外を1件、エラーログに追記する。追記したレコードをそのまま返す。"""
    records = _load_all()
    record = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
        "reviewed": False,
    }
    records.append(record)
    _save_all(records)
    return record


def get_unreviewed_errors() -> list[dict]:
    """まだ修正案が生成されていないエラーの一覧を返す。"""
    return [r for r in _load_all() if not r.get("reviewed")]


def mark_reviewed(error_id: str) -> None:
    """修正案を生成し終えたエラーに既読フラグを立てる(再度提案が作られないようにする)。"""
    records = _load_all()
    for record in records:
        if record["id"] == error_id:
            record["reviewed"] = True
    _save_all(records)
