"""エラー(例外)を伴わない「ユーザーからの訂正・不満」を蓄積するログ。

src/core/error_log.pyは実際にPythonの例外が起きた場合しか拾えないが、
「その答え違うよ」「全然機能してないじゃん」のように、クラッシュはしていないが
内容や挙動に問題がある、というケースは拾えない。このモジュールはそれを
キーワードベースで検知し、後から人間(または自己修復プロトコル)が見返せる
材料として記録する。error_log.pyと違い、ここからdiffを自動生成する仕組みは
持たない(具体的なファイル・行を指し示すトレースバックが無く、対応するコードが
本当にあるのか自体が曖昧なため、人間が中身を見て判断する前提)。
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime

from config.settings import FEEDBACK_LOG_FILE

# 「違う」「間違ってる」「機能してない」等、直前の志粋の発言に対する
# 訂正・不満を示唆する典型的な言い回し。過検知(本当は問題無いのに拾ってしまう)は
# 許容する設計(人間が後で読んで判断するだけなので実害が無い)。
CORRECTION_KEYWORDS = re.compile(
    r"違う|間違|そうじゃな|ちがうよ|できてない|動いてない|機能してない|"
    r"おかしい|直って(ない|ませ)|直してない|バグって|壊れて|"
    r"決めつけ|勝手に(思|決)|そんなこと(言|い)って(な|い)|誤解して",
)


def looks_like_correction(user_message: str) -> bool:
    """ユーザーの発言が、直前の志粋の発言への訂正・不満らしいかをキーワードで判定する。"""
    return bool(CORRECTION_KEYWORDS.search(user_message))


def _load_all() -> list[dict]:
    if not FEEDBACK_LOG_FILE.exists():
        return []
    return json.loads(FEEDBACK_LOG_FILE.read_text(encoding="utf-8"))


def _save_all(records: list[dict]) -> None:
    FEEDBACK_LOG_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def log_feedback(
    previous_user_message: str, previous_assistant_response: str, correction_message: str
) -> dict:
    """会話の流れ(直前のユーザー発言・志粋の返答・今回の訂正発言)を1件記録する。"""
    records = _load_all()
    record = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "previous_user_message": previous_user_message,
        "previous_assistant_response": previous_assistant_response,
        "correction_message": correction_message,
        "reviewed": False,
    }
    records.append(record)
    _save_all(records)
    return record


def get_unreviewed_feedback() -> list[dict]:
    return [r for r in _load_all() if not r.get("reviewed")]


def mark_reviewed(feedback_id: str) -> None:
    records = _load_all()
    for record in records:
        if record["id"] == feedback_id:
            record["reviewed"] = True
    _save_all(records)
