"""夜間対話の先輩AIクライアント(src/study/mentor_client.py:OpenRouterMentorClient)を検証する。

実際のOpenRouter APIには接続せず、src/common/openrouter_client.chat()をモック化する。
GeminiClientはgoogle.genai SDKへの直接依存が大きくここでは検証しない
(既存のsrc/study/study_session.py用テストがGeminiClient自体をFakeMentorで
置き換える形で間接的にカバーしている)。
"""
import pytest

from src.study import mentor_client


def test_openrouter_mentor_client_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(
        mentor_client,
        "settings",
        type("S", (), {"openrouter_api_key": "", "openrouter_free_mentor_model": "x"})(),
    )
    with pytest.raises(ValueError):
        mentor_client.OpenRouterMentorClient(api_key="")


def test_openrouter_mentor_client_ask_returns_stripped_content(monkeypatch):
    captured = {}

    def fake_chat(model, messages):
        captured["model"] = model
        captured["messages"] = messages
        return {"message": {"content": "  応答本文  \n"}}

    monkeypatch.setattr(mentor_client.openrouter_client, "chat", fake_chat)

    client = mentor_client.OpenRouterMentorClient(api_key="test-key", model="deepseek/deepseek-r1:free")
    result = client.ask("システム指示", "質問文")

    assert result == "応答本文"
    assert captured["model"] == "deepseek/deepseek-r1:free"
    assert captured["messages"] == [
        {"role": "system", "content": "システム指示"},
        {"role": "user", "content": "質問文"},
    ]


def test_openrouter_mentor_client_defaults_to_settings_model(monkeypatch):
    monkeypatch.setattr(
        mentor_client,
        "settings",
        type("S", (), {"openrouter_api_key": "k", "openrouter_free_mentor_model": "default/model:free"})(),
    )

    client = mentor_client.OpenRouterMentorClient()

    assert client.model == "default/model:free"
