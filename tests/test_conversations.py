"""会話スレッド(src/memory/conversations.py)を検証する。

覗き見防止(他人のconversation_idを渡されたらuser_idが一致しない限り
中身を返さない)を中心に検証する。
"""
import pytest

from src.memory import conversations, hippocampus


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    db_path = tmp_path / "hippocampus.sqlite3"
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(conversations, "HIPPOCAMPUS_DB_PATH", db_path)


def test_create_conversation_auto_generates_title_from_first_message():
    conversation_id = conversations.create_conversation(user_id=1, first_message="来期のアニメ教えて")

    threads = conversations.list_conversations(user_id=1)
    assert len(threads) == 1
    assert threads[0].id == conversation_id
    assert threads[0].title == "来期のアニメ教えて"


def test_create_conversation_truncates_long_first_message():
    long_message = "あ" * 50
    conversation_id = conversations.create_conversation(user_id=1, first_message=long_message)

    threads = conversations.list_conversations(user_id=1)
    thread = next(t for t in threads if t.id == conversation_id)
    assert thread.title.endswith("...")
    assert len(thread.title) <= 33  # 30文字 + "..."


def test_list_conversations_only_returns_own_threads():
    conversations.create_conversation(user_id=1, first_message="ユーザー1の会話")
    conversations.create_conversation(user_id=2, first_message="ユーザー2の会話")

    user1_threads = conversations.list_conversations(user_id=1)
    assert len(user1_threads) == 1
    assert user1_threads[0].title == "ユーザー1の会話"


def test_get_messages_returns_history_for_owner():
    conversation_id = conversations.create_conversation(user_id=1, first_message="こんにちは")
    hippocampus.log_episode(
        role="user", content="こんにちは", source="chat", user_id=1, conversation_id=conversation_id
    )
    hippocampus.log_episode(
        role="assistant", content="やあ!", source="chat", user_id=1, conversation_id=conversation_id
    )

    messages = conversations.get_messages(conversation_id, user_id=1)

    assert messages == [
        {"role": "user", "content": "こんにちは"},
        {"role": "assistant", "content": "やあ!"},
    ]


def test_get_messages_returns_empty_for_non_owner():
    """他人のconversation_idを渡されても、user_idが一致しなければ中身を見せない。"""
    conversation_id = conversations.create_conversation(user_id=1, first_message="秘密の会話")
    hippocampus.log_episode(
        role="user", content="秘密の会話", source="chat", user_id=1, conversation_id=conversation_id
    )

    messages = conversations.get_messages(conversation_id, user_id=2)

    assert messages == []


def test_get_messages_returns_empty_for_nonexistent_conversation():
    assert conversations.get_messages(9999, user_id=1) == []


def test_touch_conversation_updates_ordering():
    first_id = conversations.create_conversation(user_id=1, first_message="最初の会話")
    second_id = conversations.create_conversation(user_id=1, first_message="2番目の会話")

    # 最初の会話に触れて更新日時を新しくすると、一覧の先頭に来る
    conversations.touch_conversation(first_id)

    threads = conversations.list_conversations(user_id=1)
    assert threads[0].id == first_id
    assert threads[1].id == second_id
