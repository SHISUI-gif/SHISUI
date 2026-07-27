"""OllamaClient(src/common/llm_client.py)を検証する。

2026-07-28に見つかった実障害の回帰テスト: このクライアントはsettings.use_groq
を一切考慮しておらず、sleep.py・study_session.py・debate/autonomous.py等
10箇所から使われているにもかかわらず、Groqオンリーの環境(埋め込み専用の
Ollamaしか無いOracle VM)では常に404していた(睡眠モード・夜間修行・自律
討論が一度も成功していなかった)。
"""
import dataclasses

import groq
import httpx
import ollama
import pytest

from src.common import llm_client


def _fake_settings(**overrides):
    from config.settings import settings

    return dataclasses.replace(settings, **overrides)


def test_chat_messages_uses_local_ollama_when_use_groq_false(monkeypatch):
    monkeypatch.setattr(llm_client, "settings", _fake_settings(use_groq=False, ollama_model="qwen2.5:32b"))

    captured = {}

    class FakeOllamaClient:
        def __init__(self, host=None):
            pass

        def chat(self, model, messages, options=None):
            captured["model"] = model
            return {"message": {"content": "ローカル応答"}}

    monkeypatch.setattr(ollama, "Client", FakeOllamaClient)

    client = llm_client.OllamaClient()
    result = client.chat("システム", "ユーザー")

    assert result == "ローカル応答"
    assert captured["model"] == "qwen2.5:32b"


def test_chat_messages_uses_groq_when_use_groq_true(monkeypatch):
    monkeypatch.setattr(
        llm_client, "settings", _fake_settings(use_groq=True, groq_chat_model="qwen/qwen3.6-27b")
    )

    captured = {}

    def fake_groq_chat(model, messages):
        captured["model"] = model
        return {"message": {"content": "Groq応答"}}

    monkeypatch.setattr(llm_client.groq_client, "chat", fake_groq_chat)

    client = llm_client.OllamaClient()
    result = client.chat("システム", "ユーザー")

    assert result == "Groq応答"
    assert captured["model"] == "qwen/qwen3.6-27b"


def test_explicit_model_overrides_default_in_both_modes(monkeypatch):
    monkeypatch.setattr(llm_client, "settings", _fake_settings(use_groq=True, groq_chat_model="default-model"))
    monkeypatch.setattr(
        llm_client.groq_client, "chat", lambda model, messages: {"message": {"content": model}}
    )

    client = llm_client.OllamaClient(model="custom-model")

    assert client.chat("システム", "ユーザー") == "custom-model"


def test_chat_falls_back_to_secondary_groq_model_on_rate_limit(monkeypatch):
    """2026-07-28に本番で実際に発生: sleep.py経由の呼び出しがGroqのTPD上限に
    達し、フォールバックが無かったため睡眠モードの実行自体が失敗していた。"""
    monkeypatch.setattr(
        llm_client,
        "settings",
        _fake_settings(
            use_groq=True,
            groq_chat_model="qwen/qwen3.6-27b",
            groq_fallback_chat_model="llama-3.3-70b-versatile",
        ),
    )

    fake_response = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/x"))
    calls = []

    def fake_groq_chat(model, messages):
        calls.append(model)
        if model == "qwen/qwen3.6-27b":
            raise groq.RateLimitError("rate_limit_exceeded", response=fake_response, body=None)
        return {"message": {"content": "フォールバック応答"}}

    monkeypatch.setattr(llm_client.groq_client, "chat", fake_groq_chat)

    result = llm_client.OllamaClient().chat("システム", "ユーザー")

    assert result == "フォールバック応答"
    assert calls == ["qwen/qwen3.6-27b", "llama-3.3-70b-versatile"]


def test_chat_messages_strips_whitespace(monkeypatch):
    monkeypatch.setattr(llm_client, "settings", _fake_settings(use_groq=True, groq_chat_model="m"))
    monkeypatch.setattr(
        llm_client.groq_client, "chat", lambda model, messages: {"message": {"content": "  余白入り  \n"}}
    )

    result = llm_client.OllamaClient().chat("システム", "ユーザー")

    assert result == "余白入り"
