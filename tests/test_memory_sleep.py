"""記憶圧縮システム(海馬→睡眠モード→新皮質)のロジックをフェイクLLM/フェイク埋め込みで検証する。

実際のOllamaサーバーやqwen2.5には接続せず、ollama.embeddings()と睡眠モードの
LLM呼び出しをモック化して、統合・supersede・prune・ユーザーごとのグループ化
周りのロジックのみを検証する。
"""
import hashlib
import json

import ollama
import pytest

from src.memory import avatar, hippocampus, neocortex, sleep


class FakeLLM:
    def __init__(self, extractions):
        self.extractions = extractions

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        return json.dumps(self.extractions, ensure_ascii=False)


def _fake_embeddings(model: str, prompt: str) -> dict:
    """文字列のハッシュから決定論的な固定長ベクトルを作るフェイク埋め込み。"""
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    db_path = tmp_path / "hippocampus.sqlite3"
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(avatar, "HIPPOCAMPUS_DB_PATH", db_path)
    monkeypatch.setattr(neocortex, "NEOCORTEX_DB_DIR", tmp_path / "neocortex_chroma")
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)
    yield


def test_run_sleep_cycle_consolidates_and_adds_memories():
    hippocampus.log_episode(
        role="user", content="那由多はPythonのCLIツールを開発中", source="chat", user_id=1
    )
    hippocampus.log_episode(role="assistant", content="いいね!どんなツール?", source="chat", user_id=1)

    fake_llm = FakeLLM([{"category": "fact", "text": "那由多はPythonのCLIツールを開発中"}])
    result = sleep.run_sleep_cycle(llm=fake_llm)

    assert result.episodes_considered == 2
    assert result.memories_added == 1
    assert result.memories_superseded == 0
    assert hippocampus.get_unconsolidated_episodes() == []

    memories = neocortex.list_all(user_id=1)
    assert len(memories) == 1
    assert "那由多はPythonのCLIツールを開発中" in memories[0].text


def test_run_sleep_cycle_supersedes_similar_memory():
    hippocampus.log_episode(role="user", content="UIはGradioを使う予定", source="chat", user_id=1)
    sleep.run_sleep_cycle(llm=FakeLLM([{"category": "decision", "text": "UIはGradioを使う"}]))

    hippocampus.log_episode(role="user", content="やっぱりUIはStreamlitに変更した", source="chat", user_id=1)
    # フェイク埋め込みは文字列一致で類似度1.0になるため、意図的に同一文言で置き換えを再現する
    result = sleep.run_sleep_cycle(llm=FakeLLM([{"category": "decision", "text": "UIはGradioを使う"}]))

    assert result.memories_superseded == 1
    memories = neocortex.list_all(user_id=1)
    superseded_count = sum(1 for m in memories if m.text.startswith("[superseded]"))
    assert superseded_count == 1


def test_run_sleep_cycle_with_no_episodes_is_noop():
    result = sleep.run_sleep_cycle(llm=FakeLLM([]))
    assert result.episodes_considered == 0
    assert result.memories_added == 0


def test_run_sleep_cycle_keeps_different_users_separate():
    """友達それぞれの会話が、互いの長期記憶に混ざらないことを検証する。"""
    hippocampus.log_episode(role="user", content="ユーザー1はコーヒー派", source="chat", user_id=1)
    hippocampus.log_episode(role="user", content="ユーザー2は紅茶派", source="chat", user_id=2)

    class PerUserFakeLLM:
        """トランスクリプトの中身を見て、ユーザーごとに違う抽出結果を返すフェイク。"""

        def chat(self, system_prompt, user_prompt, temperature=0.3):
            if "コーヒー" in user_prompt:
                return json.dumps([{"category": "preference", "text": "ユーザー1はコーヒー派"}])
            return json.dumps([{"category": "preference", "text": "ユーザー2は紅茶派"}])

    result = sleep.run_sleep_cycle(llm=PerUserFakeLLM())

    assert result.memories_added == 2
    user1_memories = neocortex.list_all(user_id=1)
    user2_memories = neocortex.list_all(user_id=2)
    assert len(user1_memories) == 1
    assert len(user2_memories) == 1
    assert "コーヒー" in user1_memories[0].text
    assert "紅茶" in user2_memories[0].text


def test_run_sleep_cycle_ignores_episodes_without_user_id():
    """user_idが無いエピソード(voicechat等)は圧縮対象から外れる。"""
    hippocampus.log_episode(role="user", content="ユーザー未指定の発言", source="voicechat")

    result = sleep.run_sleep_cycle(llm=FakeLLM([{"category": "fact", "text": "拾われないはず"}]))

    assert result.memories_added == 0
    # ただし統合済みマークはされ、海馬からは消える(無限に溜まり続けないように)
    assert hippocampus.get_unconsolidated_episodes() == []


def test_recall_context_reflects_stored_memory():
    from src.memory import context

    hippocampus.log_episode(role="user", content="那由多はコーヒーよりお茶派", source="chat", user_id=1)
    sleep.run_sleep_cycle(llm=FakeLLM([{"category": "preference", "text": "那由多はコーヒーよりお茶派"}]))

    recall = context.build_recall_context("那由多はコーヒーよりお茶派", user_id=1)
    assert "那由多はコーヒーよりお茶派" in recall


def test_recall_context_does_not_leak_across_users():
    from src.memory import context

    hippocampus.log_episode(role="user", content="ユーザー1の秘密の趣味はプラモデル", source="chat", user_id=1)
    sleep.run_sleep_cycle(llm=FakeLLM([{"category": "fact", "text": "ユーザー1の秘密の趣味はプラモデル"}]))

    recall = context.build_recall_context("ユーザー1の秘密の趣味はプラモデル", user_id=2)
    assert recall == ""


class _AvatarAwareFakeLLM:
    """記憶抽出プロンプトとアバター解除判定プロンプトを区別して別の応答を返すフェイク。"""

    def chat(self, system_prompt, user_prompt, temperature=0.3):
        if "アバター解除判定" in system_prompt:
            return json.dumps(["bookish_glasses"])
        return json.dumps([])  # 記憶抽出は今回のテストでは使わない


def test_run_sleep_cycle_unlocks_avatar_item_matching_conversation_theme():
    hippocampus.log_episode(role="user", content="最近読んだ本の話をしたい", source="chat", user_id=1)

    result = sleep.run_sleep_cycle(llm=_AvatarAwareFakeLLM())

    assert result.items_unlocked == 1
    assert avatar.get_unlocked_slugs(1) == ["bookish_glasses"]


def test_run_sleep_cycle_does_not_unlock_already_unlocked_item_twice():
    hippocampus.log_episode(role="user", content="最近読んだ本の話をしたい", source="chat", user_id=1)
    sleep.run_sleep_cycle(llm=_AvatarAwareFakeLLM())

    hippocampus.log_episode(role="user", content="また本の話をしたい", source="chat", user_id=1)
    result = sleep.run_sleep_cycle(llm=_AvatarAwareFakeLLM())

    assert result.items_unlocked == 0
    assert avatar.get_unlocked_slugs(1) == ["bookish_glasses"]


def test_run_sleep_cycle_avatar_unlocks_are_scoped_per_user():
    hippocampus.log_episode(role="user", content="最近読んだ本の話をしたい", source="chat", user_id=1)
    hippocampus.log_episode(role="user", content="今日の天気の話", source="chat", user_id=2)

    class PerUserAvatarLLM:
        def chat(self, system_prompt, user_prompt, temperature=0.3):
            if "アバター解除判定" not in system_prompt:
                return json.dumps([])
            if "本" in user_prompt:
                return json.dumps(["bookish_glasses"])
            return json.dumps([])

    sleep.run_sleep_cycle(llm=PerUserAvatarLLM())

    assert avatar.get_unlocked_slugs(1) == ["bookish_glasses"]
    assert avatar.get_unlocked_slugs(2) == []
