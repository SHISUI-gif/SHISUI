"""Groq APIを、Ollamaの`ollama.chat()`/`ollama.embeddings()`と同じ呼び出し形・
戻り値の形に見せかけるアダプター。

クラウド移行(Macの蓋を閉じても志粋が動けるようにする)の選択肢として追加した。
`src/chat/shisui_chat.py`・`src/chat/model_router.py`・`src/common/embeddings.py`は
このモジュールを`ollama`パッケージの代わりに使うだけで、呼び出し側のロジックを
一切変えずにGroq経由へ切り替えられるようにするのが狙い。

Groq(OpenAI互換API)とOllamaでは細かい形が異なるため、以下を吸収する:
- tool_calls: Groqの`arguments`はJSON文字列、Ollamaは既にパース済みの辞書。
  ここで`json.loads()`して揃える。
- ストリーミングのチャンク形式: Groqは`chunk.choices[0].delta.content`、
  Ollamaは`chunk["message"]["content"]`。
- `think`・`keep_alive`はOllama固有のパラメータなのでここでは無視する
  (Groqにキャッシュ管理やthinking分離の概念はまだ無い)。
"""
from __future__ import annotations

import json
from collections.abc import Iterator

import groq

from config.settings import settings

_client: groq.Groq | None = None


def _get_client() -> groq.Groq:
    global _client
    if _client is None:
        _client = groq.Groq(api_key=settings.groq_api_key)
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
    think: bool | None = None,  # noqa: ARG001 - Ollama固有、Groqには概念が無いため無視
    keep_alive: str | None = None,  # noqa: ARG001 - 同上
) -> dict | Iterator[dict]:
    """Ollamaの`ollama.chat()`と同じシグネチャ・戻り値の形でGroqを呼ぶ。"""
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


def embeddings(model: str, prompt: str) -> dict:
    """Ollamaの`ollama.embeddings()`と同じシグネチャ・戻り値の形でGroqを呼ぶ。"""
    client = _get_client()
    response = client.embeddings.create(model=model, input=prompt)
    return {"embedding": response.data[0].embedding}
