"""自律討論(src/debate/autonomous.py)をフェイクLLM・フェイク埋め込みで検証する。

実際のOllamaサーバーには接続せず、弱点分析→討論→新皮質への保存→
朝レポートへのセッション追記までのロジックのみを検証する。
"""
import hashlib

import ollama
import pytest

from src.debate import autonomous, debate_agent, feedback_store
from src.memory import hippocampus, neocortex
from src.study import report as study_report
from src.study import weakness_finder


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        self.calls += 1
        if "最終結論" in system_prompt:
            return "## 討論の要旨\nテスト結論です。"
        return f"発言{self.calls}"


def _fake_embeddings(model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    monkeypatch.setattr(feedback_store, "FEEDBACK_FILE", tmp_path / "feedback_history.json")
    monkeypatch.setattr(neocortex, "NEOCORTEX_DB_DIR", tmp_path / "neocortex_chroma")
    monkeypatch.setattr(debate_agent, "DEBATE_DIR", tmp_path)
    monkeypatch.setattr(study_report, "STUDY_SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)
    yield


def test_run_autonomous_debate_skips_when_no_weak_topics():
    result = autonomous.run_autonomous_debate(llm=FakeLLM())
    assert result.skipped is True
    assert result.topics_debated == []


def test_run_autonomous_debate_debates_and_saves_to_neocortex(monkeypatch):
    monkeypatch.setattr(
        weakness_finder, "find_weak_topics", lambda top_n=None, llm=None: ["人間工学的なUI設計"]
    )

    result = autonomous.run_autonomous_debate(llm=FakeLLM())

    assert result.skipped is False
    assert len(result.topics_debated) == 1
    debated = result.topics_debated[0]
    assert debated.topic == "人間工学的なUI設計"
    assert debated.conclusion_summary
    assert debated.report_path

    memories = neocortex.list_all()
    assert len(memories) == 1
    assert memories[0].category == "insight"
    assert "人間工学的なUI設計" in memories[0].text


def test_run_autonomous_debate_appends_unread_session(monkeypatch):
    monkeypatch.setattr(
        weakness_finder, "find_weak_topics", lambda top_n=None, llm=None: ["テストトピック"]
    )
    autonomous.run_autonomous_debate(llm=FakeLLM())

    report_text = study_report.get_unread_report()
    assert "テストトピック" in report_text

    study_report.mark_report_read()
    assert study_report.get_unread_report() == ""


def test_run_autonomous_debate_does_not_prompt_for_input(monkeypatch):
    """ユーザー不在のため、collect_feedbackのようなinput()待ちが一切発生しないことを確認する。"""
    monkeypatch.setattr(
        weakness_finder, "find_weak_topics", lambda top_n=None, llm=None: ["テストトピック"]
    )

    def _fail_on_input(*args, **kwargs):
        raise AssertionError("自律討論中にinput()が呼ばれてはいけない")

    monkeypatch.setattr("builtins.input", _fail_on_input)

    result = autonomous.run_autonomous_debate(llm=FakeLLM())
    assert result.skipped is False
