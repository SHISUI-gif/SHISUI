"""GroqをOllamaと同じ呼び出し形に見せかけるアダプター(src/common/groq_client.py)を検証する。

実際のGroq APIには接続せず、groq.Groqクライアントの.chat.completions.create()・
.embeddings.create()をフェイクのレスポンスオブジェクトでモック化する。
"""
import json
import types

from src.common import groq_client


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
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if kwargs.get("stream"):
            return iter(self._stream_chunks)
        return self._response


class _FakeEmbeddings:
    def __init__(self, vector):
        self._vector = vector

    def create(self, **kwargs):
        return types.SimpleNamespace(data=[types.SimpleNamespace(embedding=self._vector)])


class _FakeClient:
    def __init__(self, chat_completions=None, embeddings=None):
        self.chat = types.SimpleNamespace(completions=chat_completions)
        self.embeddings = embeddings


def test_chat_non_streaming_returns_ollama_shaped_response(monkeypatch):
    fake_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=_fake_message(content="こんにちは"))]
    )
    monkeypatch.setattr(
        groq_client, "_get_client", lambda: _FakeClient(_FakeChatCompletions(response=fake_response))
    )

    result = groq_client.chat(model="qwen/qwen3-32b", messages=[{"role": "user", "content": "hi"}])

    assert result == {
        "message": {"role": "assistant", "content": "こんにちは", "tool_calls": None}
    }


def test_chat_converts_tool_calls_to_ollama_shape(monkeypatch):
    tool_call = _fake_tool_call("execute_web_search", {"query": "今日の天気"})
    fake_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=_fake_message(tool_calls=[tool_call]))]
    )
    monkeypatch.setattr(
        groq_client, "_get_client", lambda: _FakeClient(_FakeChatCompletions(response=fake_response))
    )

    result = groq_client.chat(model="llama-3.1-8b-instant", messages=[], tools=[{}])

    assert result["message"]["tool_calls"] == [
        {"function": {"name": "execute_web_search", "arguments": {"query": "今日の天気"}}}
    ]


def test_chat_streaming_yields_ollama_shaped_chunks(monkeypatch):
    chunk1 = types.SimpleNamespace(
        choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="こん"))]
    )
    chunk2 = types.SimpleNamespace(
        choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content="にちは"))]
    )
    monkeypatch.setattr(
        groq_client,
        "_get_client",
        lambda: _FakeClient(_FakeChatCompletions(stream_chunks=[chunk1, chunk2])),
    )

    chunks = list(groq_client.chat(model="qwen/qwen3-32b", messages=[], stream=True))

    assert chunks == [{"message": {"content": "こん"}}, {"message": {"content": "にちは"}}]


def test_chat_non_streaming_splits_think_tags_into_thinking_field(monkeypatch):
    """2026-07-27に発覚した実バグの回帰テスト: qwen3.6系はOllamaの専用thinking
    フィールドの代わりに<think>...</think>を地の文でcontentに埋め込んでくる。
    そのまま返すとユーザーに生の思考過程がそのまま表示されてしまう。"""
    fake_response = types.SimpleNamespace(
        choices=[
            types.SimpleNamespace(
                message=_fake_message(content="<think>ユーザーは天気を知りたがっている。</think>晴れだよ!")
            )
        ]
    )
    monkeypatch.setattr(
        groq_client, "_get_client", lambda: _FakeClient(_FakeChatCompletions(response=fake_response))
    )

    result = groq_client.chat(model="qwen/qwen3.6-27b", messages=[])

    assert result["message"]["content"] == "晴れだよ!"
    assert result["message"]["thinking"] == "ユーザーは天気を知りたがっている。"


def test_chat_streaming_splits_think_tags_across_chunk_boundaries(monkeypatch):
    """<think>タグ自体がチャンクの境目で分割されるケース(実際のストリーミングで
    十分起こりうる)でも、生のタグ文字列がcontentに漏れ出さないことを確認する。"""
    pieces = ["<thi", "nk>考え中", "...</thi", "nk>", "結論はこう", "だよ"]
    chunks = [
        types.SimpleNamespace(choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content=p))])
        for p in pieces
    ]
    monkeypatch.setattr(
        groq_client, "_get_client", lambda: _FakeClient(_FakeChatCompletions(stream_chunks=chunks))
    )

    events = list(groq_client.chat(model="qwen/qwen3.6-27b", messages=[], stream=True))

    thinking_text = "".join(
        e["message"]["thinking"] for e in events if "thinking" in e["message"]
    )
    content_text = "".join(
        e["message"]["content"] for e in events if "content" in e["message"]
    )
    assert thinking_text == "考え中..."
    assert content_text == "結論はこうだよ"
    assert "<think>" not in content_text and "</think>" not in content_text


def test_chat_sets_a_generous_max_completion_tokens(monkeypatch):
    """2026-07-28の回帰テスト: max_completion_tokensを省略するとGroq側の
    デフォルト値に依存してしまい、「回答が途中で途切れる」という実際の
    フィードバックにつながった。明示的に十分な上限を渡すべき。"""
    fake_response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=_fake_message(content="こんにちは"))]
    )
    completions = _FakeChatCompletions(response=fake_response)
    monkeypatch.setattr(groq_client, "_get_client", lambda: _FakeClient(completions))

    groq_client.chat(model="qwen/qwen3.6-27b", messages=[{"role": "user", "content": "hi"}])

    assert completions.last_kwargs["max_completion_tokens"] == 8192


def test_embeddings_returns_ollama_shaped_response(monkeypatch):
    monkeypatch.setattr(
        groq_client, "_get_client", lambda: _FakeClient(embeddings=_FakeEmbeddings([0.1, 0.2, 0.3]))
    )

    result = groq_client.embeddings(model="nomic-embed-text-v1_5", prompt="テスト")

    assert result == {"embedding": [0.1, 0.2, 0.3]}
