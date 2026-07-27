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


def _messages_to_groq_shape(messages: list[dict]) -> list[dict]:
    """呼び出し側(shisui_chat.py)はOllama形式の会話履歴をそのまま積み上げて
    再送してくる: tool_callsのargumentsは既にパース済みの辞書、"id"は無く、
    tool結果メッセージは"tool_name"だけを持ち"tool_call_id"を持たない。
    GroqはOpenAI互換APIのため、tool_callsに"id"/"type":"function"を要求し、
    argumentsはJSON文字列でなければならず、tool結果メッセージは対応する
    "tool_call_id"を要求する。ここで変換する(実際にツール呼び出しを含む
    会話をGroq経由で送るまで気づかれなかったバグ)。
    """
    converted: list[dict] = []
    pending_tool_call_ids: list[str] = []
    for message in messages:
        if message.get("role") == "assistant" and message.get("tool_calls"):
            pending_tool_call_ids = []
            new_calls = []
            for i, call in enumerate(message["tool_calls"]):
                call_id = f"call_{len(converted)}_{i}"
                pending_tool_call_ids.append(call_id)
                new_calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": call["function"]["name"],
                            "arguments": json.dumps(call["function"]["arguments"]),
                        },
                    }
                )
            converted.append({**message, "tool_calls": new_calls})
        elif message.get("role") == "tool" and "tool_call_id" not in message:
            call_id = pending_tool_call_ids.pop(0) if pending_tool_call_ids else f"call_unknown_{len(converted)}"
            new_message = {k: v for k, v in message.items() if k != "tool_name"}
            new_message["tool_call_id"] = call_id
            converted.append(new_message)
        elif message.get("role") == "assistant" and "tool_calls" in message:
            # tool_calls=Noneの平常時のアシスタント発言。Groqにnullキーを
            # 送らないよう取り除く(必須ではないが素直にしておく)。
            converted.append({k: v for k, v in message.items() if k != "tool_calls"})
        else:
            converted.append(message)
    return converted


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
        messages=_messages_to_groq_shape(messages),
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
    """Ollamaの`ollama.embeddings()`と同じシグネチャ・戻り値の形でGroqを呼ぶ。

    警告: このプロジェクトの実際のAPIキーで検証したところ、GroqのSDKが型ヒント上
    公開している`nomic-embed-text-v1_5`は404(モデルが存在しない/アクセス権が無い)
    で失敗した(`client.models.list()`にも埋め込み系モデルは1つも出てこない)。
    現時点では`src/common/embeddings.py`はGroqを使わず常にOllamaを使う実装に
    なっている。この関数は将来Groq側でembeddingsが一般提供された場合に備えて
    残しているだけで、**呼び出し前に実際にモデルが利用可能か`models.list()`で
    再確認すること**(過去に確認せず使い、新皮質の記憶データを実際に失った事故がある)。
    """
    client = _get_client()
    response = client.embeddings.create(model=model, input=prompt)
    return {"embedding": response.data[0].embedding}
