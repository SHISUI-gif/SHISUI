"""夜間修行のメインループ(src/study/study_session.py)をフェイクLLM・フェイクメンターで検証する。

実際のOllama/Geminiサーバーには接続せず、弱点分析→対話→新皮質への保存→
セッションログ保存までのロジックのみを検証する。
"""
import hashlib
import json
import types

import ollama
import pytest

from src.core import activity_log
from src.debate import feedback_store
from src.memory import hippocampus, neocortex
from src.research.news_client import NewsArticle
from src.study import study_session, weakness_finder


def _fake_settings(**overrides):
    base = dict(
        currents_api_key="",
        study_news_topics_count=1,
        study_dialogue_turns=3,
    )
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
        return f"メンター回答{self.calls}"


def _fake_embeddings(model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    monkeypatch.setattr(feedback_store, "FEEDBACK_FILE", tmp_path / "feedback_history.json")
    monkeypatch.setattr(neocortex, "NEOCORTEX_DB_DIR", tmp_path / "neocortex_chroma")
    monkeypatch.setattr(study_session, "STUDY_SESSIONS_FILE", tmp_path / "sessions.json")
    monkeypatch.setattr(activity_log, "ACTIVITY_LOG_FILE", tmp_path / "activity_log.json")
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)
    # 実環境の.envにCURRENTS_API_KEYが設定されていても、このファイルの他のテストが
    # 実際にニュースAPIへ到達しないよう既定でオフにしておく(ニュース機能自体を
    # 検証するテストだけが、下でstudy_session.settingsを個別に上書きする)。
    monkeypatch.setattr(study_session, "settings", _fake_settings())
    yield


def test_run_study_session_skips_when_no_weak_topics():
    result = study_session.run_study_session(llm=FakeLLM(), mentor=FakeMentor())
    assert result.skipped is True
    assert result.topics_studied == []


def test_run_study_session_studies_topics_and_saves_to_neocortex(monkeypatch):
    monkeypatch.setattr(
        weakness_finder, "find_weak_topics", lambda top_n=None, llm=None: ["人間工学的なUI設計"]
    )

    mentor = FakeMentor()
    result = study_session.run_study_session(llm=FakeLLM(), mentor=mentor)

    assert result.skipped is False
    assert len(result.topics_studied) == 1
    assert result.topics_studied[0].topic == "人間工学的なUI設計"
    assert result.gemini_calls == 3  # study_dialogue_turnsの既定値
    assert mentor.calls == 3

    memories = neocortex.list_all()
    assert len(memories) == 1
    assert memories[0].category == "insight"


def test_run_study_session_saves_unread_session_log(monkeypatch, tmp_path):
    monkeypatch.setattr(
        weakness_finder, "find_weak_topics", lambda top_n=None, llm=None: ["テストトピック"]
    )
    study_session.run_study_session(llm=FakeLLM(), mentor=FakeMentor())

    session_file = tmp_path / "sessions.json"
    assert session_file.exists()
    sessions = json.loads(session_file.read_text(encoding="utf-8"))
    assert len(sessions) == 1
    assert sessions[0]["unread"] is True
    assert sessions[0]["topics"][0]["topic"] == "テストトピック"


def test_run_study_session_studies_multiple_topics(monkeypatch):
    monkeypatch.setattr(
        weakness_finder,
        "find_weak_topics",
        lambda top_n=None, llm=None: ["トピックA", "トピックB"],
    )

    result = study_session.run_study_session(llm=FakeLLM(), mentor=FakeMentor())

    assert len(result.topics_studied) == 2
    assert result.gemini_calls == 6  # 2トピック x 3往復
    assert len(neocortex.list_all()) == 2


def test_collect_news_topics_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.setattr(study_session, "settings", _fake_settings(currents_api_key=""))

    assert study_session._collect_news_topics() == []


def test_collect_news_topics_returns_empty_when_count_is_zero(monkeypatch):
    monkeypatch.setattr(
        study_session, "settings", _fake_settings(currents_api_key="test-key", study_news_topics_count=0)
    )

    assert study_session._collect_news_topics() == []


def test_collect_news_topics_returns_topics_from_headlines(monkeypatch):
    monkeypatch.setattr(
        study_session, "settings", _fake_settings(currents_api_key="test-key", study_news_topics_count=2)
    )

    class _FakeNewsClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_today_headlines(self, max_results=5):
            return [
                NewsArticle(title="見出しA", url="", description="", published=""),
                NewsArticle(title="見出しB", url="", description="", published=""),
            ]

    monkeypatch.setattr(study_session, "NewsClient", _FakeNewsClient)

    topics = study_session._collect_news_topics()

    assert len(topics) == 2
    assert "見出しA" in topics[0]
    assert "見出しB" in topics[1]


def test_collect_news_topics_returns_empty_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(study_session, "settings", _fake_settings(currents_api_key="test-key"))

    class _FakeNewsClientRaising:
        def __init__(self, *args, **kwargs):
            pass

        def get_today_headlines(self, max_results=5):
            raise Exception("APIエラー")

    monkeypatch.setattr(study_session, "NewsClient", _FakeNewsClientRaising)

    assert study_session._collect_news_topics() == []


def test_run_study_session_does_not_skip_when_only_news_topics_exist(monkeypatch):
    """弱点トピックが無くても、ニュース学習だけで夜間修行が実行されること。"""
    monkeypatch.setattr(weakness_finder, "find_weak_topics", lambda top_n=None, llm=None: [])
    monkeypatch.setattr(
        study_session, "settings", _fake_settings(currents_api_key="test-key", study_news_topics_count=1)
    )

    class _FakeNewsClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_today_headlines(self, max_results=5):
            return [NewsArticle(title="今日の見出し", url="", description="", published="")]

    monkeypatch.setattr(study_session, "NewsClient", _FakeNewsClient)

    result = study_session.run_study_session(llm=FakeLLM(), mentor=FakeMentor())

    assert result.skipped is False
    assert len(result.topics_studied) == 1
    assert "今日の見出し" in result.topics_studied[0].topic
