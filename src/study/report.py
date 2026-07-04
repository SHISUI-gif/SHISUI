"""夜間修行・自律討論の結果を「朝のレポート」として会話に注入するためのモジュール。

src/memory/context.pyのbuild_recall_context()と同様、フォーマット済み文字列を
返すだけのシンプルな形にする。夜間修行(src/study/study_session.py)と
自律討論(src/debate/autonomous.py)は別のlaunchdジョブとして独立しているが、
朝の会話への注入は同じセッションログ(STUDY_SESSIONS_FILE)・同じ仕組みを共用する。
"""
from __future__ import annotations

import json
from datetime import datetime

from config.settings import STUDY_SESSIONS_FILE


def _load_sessions() -> list[dict]:
    if not STUDY_SESSIONS_FILE.exists():
        return []
    return json.loads(STUDY_SESSIONS_FILE.read_text(encoding="utf-8"))


def _save_sessions(sessions: list[dict]) -> None:
    STUDY_SESSIONS_FILE.write_text(
        json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_unread_report() -> str:
    """未読の夜間修行セッションがあれば、システムプロンプトに連結できる要約文字列を返す。無ければ空文字列。"""
    sessions = _load_sessions()
    unread = [s for s in sessions if s.get("unread")]
    if not unread:
        return ""

    lines = ["昨夜の「夜間修行」でメンターAIと学んだこと(会話の最初に自然に触れること):"]
    for session in unread:
        for topic in session.get("topics", []):
            lines.append(f"- [{topic['topic']}] {topic['insight']}")
    return "\n".join(lines)


def mark_report_read() -> None:
    """全セッションを既読化する。"""
    sessions = _load_sessions()
    if not sessions:
        return
    for session in sessions:
        session["unread"] = False
    _save_sessions(sessions)


def get_latest_session() -> dict | None:
    """直近のセッション(既読・未読問わず)を返す。CLIの`study report`表示用。"""
    sessions = _load_sessions()
    return sessions[-1] if sessions else None


def append_session(topics: list[dict]) -> None:
    """新しい未読セッションを1件追記する。

    study_session.py(夜間修行)とsrc/debate/autonomous.py(自律討論)の
    両方から共用する、汎用的なセッションログ追記関数。
    """
    sessions = _load_sessions()
    sessions.append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "unread": True,
            "topics": topics,
        }
    )
    _save_sessions(sessions)
