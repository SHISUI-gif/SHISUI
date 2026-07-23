"""OpenRouter APIを、Ollamaの`ollama.chat()`と同じ呼び出し形・戻り値の形に
見せかけるアダプター。

OpenRouterはOpenAI互換APIで、Groqの`groq`パッケージ自体もOpenAI互換クライアント
(base_urlを差し替え可能)なので、新しい依存パッケージを増やさずに`groq`
パッケージをOpenRouterのエンドポイントへ向けて再利用する。

コーディング質問だけ、より大きなモデル(Qwen3 Coder 480B等)に逃がす限定用途
専用(src/chat/model_router.py参照)。OpenRouterの無料枠(:freeモデル)は
1日50〜1000リクエストとGroqよりかなり少ないため、一般的な会話全体を
ここへ流すことは想定していない。
"""
from __future__ import annotations

import json
from collections.abc import Iterator

import groq

from config.settings import settings

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_client: groq.Groq | None = None


def _get_client() -> groq.Groq:
    global _client
    if _client is None:
        _client = groq.Groq(api_key=settings.openrouter_api_key, base_url=_OPENROUTER_BASE_URL)
    return _client


def _tool_calls_to_ollama_shape(tool_calls) -> list[dict] | None:
    if not tool_calls:
        return None
    return [
        {
            "function": {
                "name": call.function.name,
                "arguments": json.loads(call.function.arguments or "{}"),
            }
        }
        for call in tool_calls
    ]


def _stream_chunks(response) -> Iterator[dict]:
    for chunk in response:
        delta = chunk.choices[0].delta
        message: dict = {}
        if delta.content:
            message["content"] = delta.content
        if message:
            yield {"message": message}


def chat(
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    stream: bool = False,
    think: bool | None = None,  # noqa: ARG001 - Ollama固有、OpenRouterには概念が無いため無視
    keep_alive: str | None = None,  # noqa: ARG001 - 同上
) -> dict | Iterator[dict]:
    """Ollamaの`ollama.chat()`と同じシグネチャ・戻り値の形でOpenRouterを呼ぶ。"""
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        stream=stream,
    )

    if stream:
        return _stream_chunks(response)

    choice_message = response.choices[0].message
    return {
        "message": {
            "role": choice_message.role,
            "content": choice_message.content or "",
            "tool_calls": _tool_calls_to_ollama_shape(choice_message.tool_calls),
        }
    }
