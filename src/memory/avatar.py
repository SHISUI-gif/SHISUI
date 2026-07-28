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
    # 「解除済みの中からどれを今着せるか」の選択(那由多さんの要望:
    # 着せ替え機能。それまでは常に最後に解除したものが自動で表示されていた)。
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS avatar_selection (
            user_id INTEGER PRIMARY KEY,
            item_slug TEXT NOT NULL
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


def get_selected_slug(user_id: int) -> str | None:
    """明示的に選択中のアイテムslugを返す。選択したことが無ければNone
    (呼び出し側が「最後に解除したもの」等の既定表示にフォールバックする)。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT item_slug FROM avatar_selection WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row[0] if row else None


def select_item(user_id: int, item_slug: str) -> bool:
    """着せ替え: 解除済みのアイテムの中から表示するものを選ぶ。

    未解除のアイテムは選べない(解除済みかどうかはget_unlocked_slugsで
    確認済みであることを呼び出し側が保証する設計ではなく、ここでも
    再確認する——他人になりすまして未解除の見た目を先取りされないため)。
    """
    if item_slug not in get_unlocked_slugs(user_id):
        return False
    with _connect() as conn:
        conn.execute(
            "INSERT INTO avatar_selection (user_id, item_slug) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET item_slug = excluded.item_slug",
            (user_id, item_slug),
        )
    return True
