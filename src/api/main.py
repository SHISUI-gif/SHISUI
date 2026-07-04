"""志粋のFastAPIバックエンド。

Gradio(shisui_app.py)と同じ「頭脳」(src/chat/shisui_chat.py)を、
Next.jsフロントエンド(frontend/)から呼び出せるHTTP APIとして公開する。
Gradio版とは独立したポート(既定8000)で動作し、既存のGradio版(7860)を
壊さずに並行稼働できる。
"""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.chat.shisui_chat import stream_shisui_events

app = FastAPI(title="志粋 API")

app.add_middleware(
    CORSMiddleware,
    # Next.js開発サーバーからのアクセスを許可する。同じLAN上のスマホ等から
    # 192.168.x.x:3000のようなアドレスでアクセスされるケースもあるため、
    # localhost/127.0.0.1固定ではなくプライベートIPレンジ全体を正規表現で許可する。
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}):3000",
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@app.get("/api/health")
def health() -> dict:
    """疎通確認用のヘルスチェック。"""
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    """志粋との会話をNDJSON形式でストリーミングする。

    1行が1つのJSONイベント: {"type": "thinking" | "content" | "tool_status", "text": "..."}
    Gradio向けとは異なり、各イベントは「差分」(そのチャンクで新しく生成された分)であり、
    累積テキストではない。フロントエンドはtypeごとに表示先(アコーディオン/本文/ステータス)
    を分けて追記していく。
    """
    history = [turn.model_dump() for turn in request.history]

    def event_stream():
        for event in stream_shisui_events(request.message, history):
            yield json.dumps({"type": event.type, "text": event.text}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
