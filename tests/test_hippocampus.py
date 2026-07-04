"""海馬(src/memory/hippocampus.py)のuser_id/conversation_id列を検証する。"""
from src.memory import hippocampus


def test_log_episode_stores_user_and_conversation_id(monkeypatch, tmp_path):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    hippocampus.log_episode(role="user", content="こんにちは", source="chat", user_id=1, conversation_id=10)

    episodes = hippocampus.get_unconsolidated_episodes()
    assert len(episodes) == 1
    assert episodes[0].user_id == 1
    assert episodes[0].conversation_id == 10


def test_log_episode_defaults_to_none_for_backward_compatibility(monkeypatch, tmp_path):
    """voicechat等、ユーザーの概念が無い呼び出し元は従来通りuser_id無しで動く。"""
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    hippocampus.log_episode(role="user", content="こんにちは", source="voicechat")

    episodes = hippocampus.get_unconsolidated_episodes()
    assert episodes[0].user_id is None
    assert episodes[0].conversation_id is None


def test_migration_adds_columns_to_pre_existing_db(monkeypatch, tmp_path):
    """user_id/conversation_id列が無い(移行前の)DBファイルにも後から列が追加される。"""
    import sqlite3

    db_path = tmp_path / "hippocampus.sqlite3"
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", db_path)

    # わざと旧スキーマ(新列無し)でテーブルを作っておく
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            consolidated INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        "INSERT INTO episodes (timestamp, role, content, source) VALUES (?, ?, ?, ?)",
        ("2026-01-01T00:00:00", "user", "移行前のデータ", "chat"),
    )
    conn.commit()
    conn.close()

    # 新しいコードで触ると、既存データを壊さずに新列が追加される
    hippocampus.log_episode(role="user", content="移行後のデータ", source="chat", user_id=1)

    episodes = hippocampus.get_unconsolidated_episodes()
    assert len(episodes) == 2
    assert episodes[0].content == "移行前のデータ"
    assert episodes[0].user_id is None
    assert episodes[1].content == "移行後のデータ"
    assert episodes[1].user_id == 1
