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


def test_log_episode_stores_emotion(monkeypatch, tmp_path):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    hippocampus.log_episode(role="user", content="不安だな", source="chat", user_id=1, emotion="ANXIOUS")

    episodes = hippocampus.get_unconsolidated_episodes()
    assert episodes[0].emotion == "ANXIOUS"


def test_log_episode_defaults_emotion_to_none(monkeypatch, tmp_path):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    hippocampus.log_episode(role="assistant", content="了解!", source="chat", user_id=1)

    episodes = hippocampus.get_unconsolidated_episodes()
    assert episodes[0].emotion is None


def test_migration_adds_emotion_column_to_pre_existing_db(monkeypatch, tmp_path):
    """emotion列が無い(移行前の)DBファイルにも後から列が追加される。"""
    import sqlite3

    db_path = tmp_path / "hippocampus.sqlite3"
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            consolidated INTEGER NOT NULL DEFAULT 0,
            user_id INTEGER,
            conversation_id INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO episodes (timestamp, role, content, source, user_id) VALUES (?, ?, ?, ?, ?)",
        ("2026-01-01T00:00:00", "user", "移行前のデータ", "chat", 1),
    )
    conn.commit()
    conn.close()

    hippocampus.log_episode(role="user", content="移行後のデータ", source="chat", user_id=1, emotion="HAPPY")

    episodes = hippocampus.get_unconsolidated_episodes()
    assert len(episodes) == 2
    assert episodes[0].emotion is None
    assert episodes[1].emotion == "HAPPY"


def test_get_recent_mood_returns_most_frequent_of_last_n_episodes(monkeypatch, tmp_path):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    for e in ["ANXIOUS", "ANXIOUS", "HAPPY"]:
        hippocampus.log_episode(role="user", content="発言", source="chat", user_id=1, emotion=e)

    assert hippocampus.get_recent_mood(1) == "ANXIOUS"


def test_get_recent_mood_returns_none_when_no_emotion_data(monkeypatch, tmp_path):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    hippocampus.log_episode(role="user", content="発言", source="chat", user_id=1)

    assert hippocampus.get_recent_mood(1) is None


def test_get_recent_mood_is_scoped_per_user(monkeypatch, tmp_path):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    hippocampus.log_episode(role="user", content="発言1", source="chat", user_id=1, emotion="SAD")
    hippocampus.log_episode(role="user", content="発言2", source="chat", user_id=2, emotion="HAPPY")

    assert hippocampus.get_recent_mood(1) == "SAD"
    assert hippocampus.get_recent_mood(2) == "HAPPY"


def test_get_recent_episodes_is_scoped_per_user(monkeypatch, tmp_path):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    hippocampus.log_episode(role="user", content="ユーザー1の発言", source="chat", user_id=1)
    hippocampus.log_episode(role="user", content="ユーザー2の発言", source="chat", user_id=2)

    user1_episodes = hippocampus.get_recent_episodes(1, days=3)
    assert len(user1_episodes) == 1
    assert user1_episodes[0].content == "ユーザー1の発言"


def test_get_recent_episodes_includes_already_consolidated_episodes(monkeypatch, tmp_path):
    """アバター解除判定は複数日にまたがる話題を拾うため、統合済み(consolidated)の
    エピソードも対象に含める必要がある(get_unconsolidated_episodesとの違い)。"""
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")

    episode_id = hippocampus.log_episode(role="user", content="昨日の発言", source="chat", user_id=1)
    hippocampus.mark_consolidated([episode_id])

    episodes = hippocampus.get_recent_episodes(1, days=3)
    assert len(episodes) == 1
    assert episodes[0].consolidated is True


def test_get_recent_episodes_excludes_entries_older_than_the_window(monkeypatch, tmp_path):
    import sqlite3

    db_path = tmp_path / "hippocampus.sqlite3"
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", db_path)

    hippocampus.log_episode(role="user", content="今日の発言", source="chat", user_id=1)

    # 保持期間より古い(10日前の)発言を直接挿入する
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO episodes (timestamp, role, content, source, user_id) VALUES (?, ?, ?, ?, ?)",
        ("2020-01-01T00:00:00", "user", "10日以上前の発言", "chat", 1),
    )
    conn.commit()
    conn.close()

    episodes = hippocampus.get_recent_episodes(1, days=3)
    assert len(episodes) == 1
    assert episodes[0].content == "今日の発言"
