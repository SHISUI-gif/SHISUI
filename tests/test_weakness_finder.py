"""夜間修行の弱点分析(src/study/weakness_finder.py)をフェイクLLMで検証する。

実際のOllamaサーバーには接続せず、海馬・討論フィードバックの材料抽出と
トピック要約のロジックのみを検証する。
"""
import pytest

from src.debate import feedback_store
from src.memory import hippocampus
from src.study import weakness_finder


class FakeLLM:
    def __init__(self, topics: list[str]):
        self.topics = topics

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        return "\n".join(self.topics)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    monkeypatch.setattr(feedback_store, "FEEDBACK_FILE", tmp_path / "feedback_history.json")
    yield


def test_find_weak_topics_returns_empty_when_no_material():
    assert weakness_finder.find_weak_topics(llm=FakeLLM([])) == []


def test_find_weak_topics_uses_uncertain_episodes_and_incorrect_feedback():
    hippocampus.log_episode(role="user", content="UI設計についてどう思う?", source="chat")
    hippocampus.log_episode(
        role="assistant", content="⚠️ 人間工学的な観点はちょっと自信ないかも", source="chat"
    )

    feedback_store.save_entry(
        {
            "timestamp": "2026-07-01T00:00:00",
            "topic": "週4日勤務制",
            "conclusion_summary": "誤った試算に基づく結論でした",
            "verdict": "incorrect",
            "user_chain_of_thought": "生産性データを先に確認すべきだった",
        }
    )

    topics = weakness_finder.find_weak_topics(
        top_n=2, llm=FakeLLM(["人間工学的なUI設計", "週4日勤務制の生産性データ"])
    )

    assert topics == ["人間工学的なUI設計", "週4日勤務制の生産性データ"]


def test_find_weak_topics_respects_top_n():
    hippocampus.log_episode(role="assistant", content="⚠️ 自信ない", source="chat")
    topics = weakness_finder.find_weak_topics(
        top_n=1, llm=FakeLLM(["トピックA", "トピックB", "トピックC"])
    )
    assert topics == ["トピックA"]
