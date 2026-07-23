"""OpenRouterをOllamaと同じ呼び出し形に見せかけるアダプター
(src/common/openrouter_client.py)を検証する。

実際のOpenRouter APIには接続せず、groq.Groqクライアント(base_url差し替えで
OpenRouterへ向けている)の.chat.completions.create()をフェイクの
レスポンスオブジェクトでモック化する。
"""
import json
import types

from src.common import openrouter_client


def _fake_message(role="assistant", content="", tool_calls=None):
    return types.SimpleNamespace(role=role, content=content, tool_calls=tool_calls)


def _fake_tool_call(name: str, arguments: dict):
    return types.SimpleNamespace(
        function=types.SimpleNamespace(name=name, arguments=json.dumps(arguments))
    )


class _FakeChatCompletions:
    def __init__(self, response=None, stream_chunks=None):
        self._response = response
        self._stream_chunks = stream_chunks or []

    def create(self, **kwargs):
        if kwargs.get("stream"):
            return iter(self._stream_chunks)
        return self._response


class _FakeClient:
    def __init__(self, chat_completions=None):
        self.chat = types.SimpleNamespace(completions=chat_completions)


def test_chat_non_streaming_returns_ollama_shaped_response(monkeypatch):
    fake_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=_fake_message(content="def foo(): pass"))]
    )
    monkeypatch.setattr(
        openrouter_client, "_get_client", lambda: _FakeClient(_FakeChatCompletions(response=fake_response))
    )

    result = openrouter_client.chat(
        model="qwen/qwen3-coder:free", messages=[{"role": "user", "content": "hi"}]
    )

    assert result == {
        "message": {"role": "assistant", "content": "def foo(): pass", "tool_calls": None}
    }


def test_chat_converts_tool_calls_to_ollama_shape(monkeypatch):
    tool_call = _fake_tool_call("execute_web_search", {"query": "今日の天気"})
    fake_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=_fake_message(tool_calls=[tool_call]))]
    )
    monkeypatch.setattr(
        openrouter_client, "_get_client", lambda: _FakeClient(_FakeChatCompletions(response=fake_response))
    )

    result = openrouter_client.chat(model="qwen/qwen3-coder:free", messages=[], tools=[{}])

    assert result["message"]["tool_calls"] == [
        {"function": {"name": "execute_web_search", "arguments": {"query": "今日の天気"}}}
    ]


def test_chat_streaming_yields_ollama_shaped_chunks(monkeypatch):
    chunk1 = types.SimpleNamespace(
        choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="def "))]
    )
    chunk2 = types.SimpleNamespace(
        choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="foo(): pass"))]
    )
    monkeypatch.setattr(
        openrouter_client,
        "_get_client",
        lambda: _FakeClient(_FakeChatCompletions(stream_chunks=[chunk1, chunk2])),
    )

    chunks = list(openrouter_client.chat(model="qwen/qwen3-coder:free", messages=[], stream=True))

    assert chunks == [{"message": {"content": "def "}}, {"message": {"content": "foo(): pass"}}]
