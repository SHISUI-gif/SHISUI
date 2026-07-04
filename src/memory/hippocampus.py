"""海馬レイヤー: 短期・エピソード記憶(SQLiteによる生ログ保存)。

日々の会話をそのままrole/content単位で記録する。睡眠モード(src/memory/sleep.py)が
これを読んで新皮質(長期記憶)へ圧縮し、統合済み(consolidated)かつ保持期間を過ぎた
エピソードのみを削除する。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from config.settings import HIPPOCAMPUS_DB_PATH


@dataclass
class Episode:
    id: int
    timestamp: str
    role: str
    content: str
    source: str
    consolidated: bool


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(HIPPOCAMPUS_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            consolidated INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    return conn


def log_episode(role: str, content: str, source: str, timestamp: str | None = None) -> int:
    """1発話分のエピソードを海馬に記録し、挿入した行のidを返す。"""
    timestamp = timestamp or datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO episodes (timestamp, role, content, source) VALUES (?, ?, ?, ?)",
            (timestamp, role, content, source),
        )
        return cursor.lastrowid


def get_unconsolidated_episodes() -> list[Episode]:
    """まだ新皮質へ統合されていないエピソードを古い順で返す。"""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, timestamp, role, content, source, consolidated "
            "FROM episodes WHERE consolidated = 0 ORDER BY id ASC"
        ).fetchall()
    return [Episode(id=r[0], timestamp=r[1], role=r[2], content=r[3], source=r[4], consolidated=bool(r[5])) for r in rows]


def mark_consolidated(episode_ids: list[int]) -> None:
    """指定したエピソードを統合済みとしてマークする。"""
    if not episode_ids:
        return
    with _connect() as conn:
        placeholders = ",".join("?" for _ in episode_ids)
        conn.execute(f"UPDATE episodes SET consolidated = 1 WHERE id IN ({placeholders})", episode_ids)


def prune_old_episodes(retention_days: int) -> int:
    """保持期間を過ぎ、かつ統合済みのエピソードを削除する。削除件数を返す。"""
    cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat(timespec="seconds")
    with _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM episodes WHERE consolidated = 1 AND timestamp < ?", (cutoff,)
        )
        return cursor.rowcount
