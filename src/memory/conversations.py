"""会話スレッド(Gemini/Claude風のサイドバーで一覧・切り替えるための単位)。

海馬(hippocampus.episodes)はもともと「圧縮対象の生ログ」という睡眠モード向けの
役割だけを持っていたが、user_id・conversation_id列を足したことで、同じテーブルを
そのまま会話スレッドの実体としても再利用できる。ここでは「スレッドの作成・一覧・
取得」というUI向けの薄い層だけを持ち、実際のメッセージ保存はhippocampus.log_episode()
に任せる(二重管理にしない)。

get_messages()のuser_id一致チェックが、他人のconversation_idを渡されても
中身を見せない唯一の「覗き見防止」ロジックになっている。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from config.settings import HIPPOCAMPUS_DB_PATH

_TITLE_MAX_LENGTH = 30


@dataclass
class Conversation:
    id: int
    title: str
    created_at: str
    updated_at: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(HIPPOCAMPUS_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return conn


def _make_title(first_message: str) -> str:
    stripped = first_message.strip().replace("\n", " ")
    if len(stripped) <= _TITLE_MAX_LENGTH:
        return stripped or "新しい会話"
    return stripped[:_TITLE_MAX_LENGTH] + "..."


def create_conversation(user_id: int, first_message: str) -> int:
    """新しい会話スレッドを作成し、そのidを返す。タイトルは最初のメッセージから自動生成する。"""
    # updated_atで並べ替えて使うため、秒未満の解像度で記録する
    # (同じ秒内に複数回操作されるとseconds精度では順序が不定になる)
    now = datetime.now().isoformat(timespec="microseconds")
    title = _make_title(first_message)
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO conversations (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (user_id, title, now, now),
        )
        return cursor.lastrowid


def touch_conversation(conversation_id: int) -> None:
    """会話の更新日時を今に更新する(サイドバーで直近の会話が上に来るようにするため)。"""
    # updated_atで並べ替えて使うため、秒未満の解像度で記録する
    # (同じ秒内に複数回操作されるとseconds精度では順序が不定になる)
    now = datetime.now().isoformat(timespec="microseconds")
    with _connect() as conn:
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))


def list_conversations(user_id: int) -> list[Conversation]:
    """指定ユーザーの会話スレッドを、直近に更新された順で返す。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM conversations "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [Conversation(id=r[0], title=r[1], created_at=r[2], updated_at=r[3]) for r in rows]


def get_messages(conversation_id: int, user_id: int) -> list[dict]:
    """指定した会話のメッセージ履歴を返す。user_idが一致しない場合は空リストを返す
    (他人のconversation_idを渡されても中身を見せないための唯一のチェック)。"""
    with _connect() as conn:
        owner_row = conn.execute(
            "SELECT user_id FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if owner_row is None or owner_row[0] != user_id:
            return []

        rows = conn.execute(
            "SELECT role, content FROM episodes WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    return [{"role": r[0], "content": r[1]} for r in rows]
