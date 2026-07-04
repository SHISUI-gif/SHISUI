"""育つアバターの解除状態を管理する。

友達それぞれの会話内容(テーマ)に応じて、志粋が夜間睡眠サイクル中に
どのアイテム(src/memory/avatar_catalog.py参照)を解除するか判定する。
avatar_unlocksテーブルは、他のユーザーテーブルと同じHIPPOCAMPUS_DB_PATHに
間借りする(新しいSQLiteファイルを増やさない設計判断)。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from config.settings import HIPPOCAMPUS_DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(HIPPOCAMPUS_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS avatar_unlocks (
            user_id INTEGER NOT NULL,
            item_slug TEXT NOT NULL,
            unlocked_at TEXT NOT NULL,
            PRIMARY KEY (user_id, item_slug)
        )
        """
    )
    return conn


def get_unlocked_slugs(user_id: int) -> list[str]:
    """指定ユーザーが解除済みのアイテムslug一覧を返す。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT item_slug FROM avatar_unlocks WHERE user_id = ? ORDER BY unlocked_at",
            (user_id,),
        ).fetchall()
    return [row[0] for row in rows]


def unlock_item(user_id: int, item_slug: str) -> bool:
    """指定アイテムを解除する。既に解除済みなら何もせずFalseを返す。新規解除ならTrue。"""
    with _connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM avatar_unlocks WHERE user_id = ? AND item_slug = ?",
            (user_id, item_slug),
        ).fetchone()
        if existing:
            return False

        conn.execute(
            "INSERT INTO avatar_unlocks (user_id, item_slug, unlocked_at) VALUES (?, ?, ?)",
            (user_id, item_slug, datetime.now().isoformat(timespec="seconds")),
        )
    return True
