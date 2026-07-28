"""夜間対話(src/study/external_dialogue.py)をフェイクLLM・フェイク先輩AIで検証する。

実際のOllama/OpenRouterサーバーには接続せず、弱点分析→対話→新皮質への保存→
activity_logへの記録までのロジックのみを検証する。
"""
import hashlib
import types

import ollama
import pytest

from src.core import activity_log
from src.debate import feedback_store
from src.memory import hippocampus, neocortex
from src.study import external_dialogue, weakness_finder


def _fake_settings(**overrides):
    base = dict(openrouter_api_key="test-key", external_dialogue_turns=3)
    base.update(overrides)
    return types.SimpleNamespace(**base)


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        self.calls += 1
        return f"応答{self.calls}"


class FakeMentor:
    def __init__(self) -> None:
        self.calls = 0

    def ask(self, system_instruction: str, prompt: str, temperature: float = 0.3) -> str:
        self.calls += 1
        return f"先輩AI回答{self.calls}"


def _fake_embeddings(model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    monkeypatch.setattr(feedback_store, "FEEDBACK_FILE", tmp_path / "feedback_history.json")
    monkeypatch.setattr(neocortex, "NEOCORTEX_DB_DIR", tmp_path / "neocortex_chroma")
    monkeypatch.setattr(activity_log, "ACTIVITY_LOG_FILE", tmp_path / "activity_log.json")
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)
    monkeypatch.setattr(external_dialogue, "settings", _fake_settings())
    yield


def test_run_external_dialogue_session_skips_when_no_api_key(monkeypatch):
    monkeypatch.setattr(external_dialogue, "settings", _fake_settings(openrouter_api_key=""))

    result = external_dialogue.run_external_dialogue_session(llm=FakeLLM())

    assert result.skipped is True
    assert result.topics_discussed == []


def test_run_external_dialogue_session_skips_when_no_weak_topics():
    result = external_dialogue.run_external_dialogue_session(llm=FakeLLM(), mentor=FakeMentor())
    assert result.skipped is True
    assert result.topics_discussed == []


def test_run_external_dialogue_session_discusses_topics_and_saves_to_neocortex(monkeypatch):
    monkeypatch.setattr(
        weakness_finder, "find_weak_topics", lambda top_n=None, llm=None: ["人間工学的なUI設計"]
    )

    mentor = FakeMentor()
    result = external_dialogue.run_external_dialogue_session(llm=FakeLLM(), mentor=mentor)

    assert result.skipped is False
    assert len(result.topics_discussed) == 1
    assert result.topics_discussed[0].topic == "人間工学的なUI設計"
    assert mentor.calls == 3  # external_dialogue_turnsの既定値

    memories = neocortex.list_all()
    assert len(memories) == 1
    assert memories[0].category == "insight"


def test_run_external_dialogue_session_logs_full_dialogue_to_activity_log(monkeypatch):
    monkeypatch.setattr(
        weakness_finder, "find_weak_topics", lambda top_n=None, llm=None: ["テストトピック"]
    )

    external_dialogue.run_external_dialogue_session(llm=FakeLLM(), mentor=FakeMentor())

    recent = activity_log.get_recent_activity()
    assert len(recent) == 1
    assert recent[0]["kind"] == "external_dialogue"
    dialogues = recent[0]["details"]["dialogues"]
    assert dialogues[0]["topic"] == "テストトピック"
    assert len(dialogues[0]["dialogue"]) > 0
    assert dialogues[0]["dialogue"][0]["role"] == "志粋"


def test_run_external_dialogue_session_discusses_multiple_topics(monkeypatch):
    monkeypatch.setattr(
        weakness_finder,
        "find_weak_topics",
        lambda top_n=None, llm=None: ["トピックA", "トピックB"],
    )

    result = external_dialogue.run_external_dialogue_session(llm=FakeLLM(), mentor=FakeMentor())

    assert len(result.topics_discussed) == 2
    assert len(neocortex.list_all()) == 2
