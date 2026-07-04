"""志粋のFastAPIバックエンド。

Gradio(shisui_app.py)と同じ「頭脳」(src/chat/shisui_chat.py)を、
Next.jsフロントエンド(frontend/)から呼び出せるHTTP APIとして公開する。
Gradio版とは独立したポート(既定8000)で動作し、既存のGradio版(7860)を
壊さずに並行稼働できる。
"""
from __future__ import annotations

import json
import threading

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.chat.shisui_chat import stream_shisui_events
from src.core import auth
from src.corpus.scheduler import maybe_run_daily_archive_crawl
from src.debate.scheduler import maybe_run_daily_debate_autonomous
from src.memory import conversations
from src.memory.scheduler import maybe_run_daily_sleep
from src.study.scheduler import maybe_run_daily_study

# OllamaのllamaserverはモデルごとにOLLAMA_NUM_PARALLEL=1(-np 1)で動いており、
# 実質「同時に1人分しか生成できない」。複数人が同時にメッセージを送ると、
# 後続のリクエストはOllama側で無言のまま待たされ、その間ストリーミング
# レスポンスに一切バイトが流れないため、Cloudflareトンネルの無応答タイムアウト
# (約100秒)に引っかかって502/524になっていた。このロックで「順番待ち中」を
# 明示的に送り続け、コネクションを生かしたままユーザーにも状況を見せる。
_generation_lock = threading.Lock()
_QUEUE_POLL_SECONDS = 5

app = FastAPI(title="志粋 API")


@app.on_event("startup")
def _start_daily_schedulers() -> None:
    # Gradio版(shisui_app.py)と同じ「アプリ起動時に1日1回」の仕組み。
    # Next.jsフロントエンド経由(このFastAPIだけ)で使う場合でも、記憶圧縮・
    # 青空文庫クロール・夜間修行・自律討論が自動で動くようにする。
    threading.Thread(target=maybe_run_daily_sleep, daemon=True).start()
    threading.Thread(target=maybe_run_daily_archive_crawl, daemon=True).start()
    threading.Thread(target=maybe_run_daily_study, daemon=True).start()
    threading.Thread(target=maybe_run_daily_debate_autonomous, daemon=True).start()

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
    conversation_id: int | None = None


class AuthRequest(BaseModel):
    name: str
    password: str


def _require_user_id(authorization: str | None) -> int:
    """`Authorization: Bearer <token>`ヘッダーからuser_idを取り出す。無効なら401を返す。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="認証が必要です。")
    token = authorization.removeprefix("Bearer ")
    user_id = auth.get_user_id_for_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="セッションが無効です。再ログインしてください。")
    return user_id


@app.get("/api/health")
def health() -> dict:
    """疎通確認用のヘルスチェック。"""
    return {"status": "ok"}


@app.post("/api/auth/register")
def register(request: AuthRequest) -> dict:
    """新規ユーザーを登録し、セッショントークンを発行する。"""
    result = auth.register(request.name, request.password)
    if not result.success:
        raise HTTPException(status_code=409, detail=result.error)
    return {"token": result.token, "user_id": result.user_id, "name": result.name}


@app.post("/api/auth/login")
def login(request: AuthRequest) -> dict:
    """既存ユーザーでログインし、新しいセッショントークンを発行する。"""
    result = auth.login(request.name, request.password)
    if not result.success:
        raise HTTPException(status_code=401, detail=result.error)
    return {"token": result.token, "user_id": result.user_id, "name": result.name}


@app.get("/api/conversations")
def list_conversations(authorization: str | None = Header(None)) -> list[dict]:
    """ログイン中のユーザー自身の会話スレッドを、直近に更新された順で一覧する。"""
    user_id = _require_user_id(authorization)
    return [
        {"id": t.id, "title": t.title, "created_at": t.created_at, "updated_at": t.updated_at}
        for t in conversations.list_conversations(user_id)
    ]


@app.get("/api/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: int, authorization: str | None = Header(None)
) -> list[dict]:
    """指定した会話の履歴を返す。他人の会話IDを渡された場合は空リストを返す
    (conversations.get_messages()内のuser_id一致チェックによる)。"""
    user_id = _require_user_id(authorization)
    return conversations.get_messages(conversation_id, user_id)


@app.post("/api/chat")
def chat(request: ChatRequest, authorization: str | None = Header(None)) -> StreamingResponse:
    """志粋との会話をNDJSON形式でストリーミングする。

    1行が1つのJSONイベント: {"type": "thinking" | "content" | "tool_status", "text": "...",
    "conversation_id": int}。各イベントは「差分」(そのチャンクで新しく生成された分)であり、
    累積テキストではない。フロントエンドはtypeごとに表示先(アコーディオン/本文/ステータス)
    を分けて追記していく。conversation_idは新規会話の場合にフロントが知る唯一の方法なので
    毎イベントに含める。
    """
    user_id = _require_user_id(authorization)
    history = [turn.model_dump() for turn in request.history]

    conversation_id = request.conversation_id
    if conversation_id is None:
        conversation_id = conversations.create_conversation(user_id, request.message)
    else:
        conversations.touch_conversation(conversation_id)

    def _emit(event_type: str, text: str) -> str:
        return (
            json.dumps(
                {"type": event_type, "text": text, "conversation_id": conversation_id},
                ensure_ascii=False,
            )
            + "\n"
        )

    def event_stream():
        # Ollamaは実質1リクエストずつしか生成できないため、既に誰かの生成が
        # 進行中なら「順番待ち中」を送り続けてコネクションを維持する。
        # 無言のまま待たせると、トンネル(Cloudflare)の無応答タイムアウトで
        # 502/524になってしまうため、必ず定期的にバイトを流し続ける。
        while not _generation_lock.acquire(timeout=_QUEUE_POLL_SECONDS):
            yield _emit("tool_status", "順番待ち中...")

        try:
            for event in stream_shisui_events(request.message, history, user_id, conversation_id):
                yield _emit(event.type, event.text)
        finally:
            _generation_lock.release()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
