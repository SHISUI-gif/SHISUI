"""記憶圧縮システム(海馬→睡眠モード→新皮質)のロジックをフェイクLLM/フェイク埋め込みで検証する。

実際のOllamaサーバーやqwen2.5には接続せず、ollama.embeddings()と睡眠モードの
LLM呼び出しをモック化して、統合・supersede・prune周りのロジックのみを検証する。
"""
import hashlib
import json

import ollama
import pytest

from src.memory import hippocampus, neocortex, sleep


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
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    monkeypatch.setattr(neocortex, "NEOCORTEX_DB_DIR", tmp_path / "neocortex_chroma")
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)
    yield


def test_run_sleep_cycle_consolidates_and_adds_memories():
    hippocampus.log_episode(role="user", content="那由多はPythonのCLIツールを開発中", source="chat")
    hippocampus.log_episode(role="assistant", content="いいね!どんなツール?", source="chat")

    fake_llm = FakeLLM([{"category": "fact", "text": "那由多はPythonのCLIツールを開発中"}])
    result = sleep.run_sleep_cycle(llm=fake_llm)

    assert result.episodes_considered == 2
    assert result.memories_added == 1
    assert result.memories_superseded == 0
    assert hippocampus.get_unconsolidated_episodes() == []

    memories = neocortex.list_all()
    assert len(memories) == 1
    assert "那由多はPythonのCLIツールを開発中" in memories[0].text


def test_run_sleep_cycle_supersedes_similar_memory():
    hippocampus.log_episode(role="user", content="UIはGradioを使う予定", source="chat")
    sleep.run_sleep_cycle(llm=FakeLLM([{"category": "decision", "text": "UIはGradioを使う"}]))

    hippocampus.log_episode(role="user", content="やっぱりUIはStreamlitに変更した", source="chat")
    # フェイク埋め込みは文字列一致で類似度1.0になるため、意図的に同一文言で置き換えを再現する
    result = sleep.run_sleep_cycle(llm=FakeLLM([{"category": "decision", "text": "UIはGradioを使う"}]))

    assert result.memories_superseded == 1
    memories = neocortex.list_all()
    superseded_count = sum(1 for m in memories if m.text.startswith("[superseded]"))
    assert superseded_count == 1


def test_run_sleep_cycle_with_no_episodes_is_noop():
    result = sleep.run_sleep_cycle(llm=FakeLLM([]))
    assert result.episodes_considered == 0
    assert result.memories_added == 0


def test_recall_context_reflects_stored_memory():
    from src.memory import context

    hippocampus.log_episode(role="user", content="那由多はコーヒーよりお茶派", source="chat")
    sleep.run_sleep_cycle(llm=FakeLLM([{"category": "preference", "text": "那由多はコーヒーよりお茶派"}]))

    recall = context.build_recall_context("那由多はコーヒーよりお茶派")
    assert "那由多はコーヒーよりお茶派" in recall
