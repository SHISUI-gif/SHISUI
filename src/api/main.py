"""志粋のFastAPIバックエンド。

Gradio(shisui_app.py)と同じ「頭脳」(src/chat/shisui_chat.py)を、
Next.jsフロントエンド(frontend/)から呼び出せるHTTP APIとして公開する。
Gradio版とは独立したポート(既定8000)で動作し、既存のGradio版(7860)を
壊さずに並行稼働できる。
"""
from __future__ import annotations

import json
import threading
import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from rich.console import Console

from config.settings import SLEEP_IN_PROGRESS_FILE, settings
from src.chat.shisui_chat import generate_proactive_checkin, stream_shisui_events
from src.core import activity_log, auth, evolution, feedback_autopilot, user_feedback
from src.corpus.scheduler import maybe_run_nightly_archive_crawl
from src.debate.scheduler import maybe_run_nightly_debate_autonomous
from src.memory import avatar, conversations, hippocampus
from src.memory.avatar_catalog import AVATAR_CATALOG
from src.memory.scheduler import maybe_run_nightly_sleep
from src.study.scheduler import maybe_run_nightly_study

console = Console()

# OllamaのllamaserverはモデルごとにOLLAMA_NUM_PARALLEL=1(-np 1)で動いており、
# 実質「同時に1人分しか生成できない」。複数人が同時にメッセージを送ると、
# 後続のリクエストはOllama側で無言のまま待たされ、その間ストリーミング
# レスポンスに一切バイトが流れないため、Cloudflareトンネルの無応答タイムアウト
# (約100秒)に引っかかって502/524になっていた。このロックで「順番待ち中」を
# 明示的に送り続け、コネクションを生かしたままユーザーにも状況を見せる。
_generation_lock = threading.Lock()
_QUEUE_POLL_SECONDS = 5

app = FastAPI(title="志粋 API")


def _nightly_scheduler_loop() -> None:
    """夜間帯(既定23:00〜翌6:30)の間、記憶圧縮・青空文庫クロール・夜間修行・
    自律討論を順番にチェックし続ける永続ループ。

    以前は「アプリ起動時に1回だけ」チェックしていたため、サーバーを再起動
    せずに何日も動かし続けると2日目以降トリガーされなくなるバグがあった。
    定期的にチェックし直すことで、サーバーを再起動しなくても夜間帯の開始を
    取りこぼさないようにする。
    """
    while True:
        try:
            maybe_run_nightly_sleep()
            maybe_run_nightly_archive_crawl()
            maybe_run_nightly_study()
            maybe_run_nightly_debate_autonomous()
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]夜間スケジューラの巡回でエラー(継続します): {exc}[/yellow]")
        time.sleep(settings.night_mode_check_interval_seconds)


@app.on_event("startup")
def _start_nightly_scheduler() -> None:
    # Next.jsフロントエンド経由(このFastAPIだけ)で使う場合でも、記憶圧縮・
    # 青空文庫クロール・夜間修行・自律討論が自動で動くようにする。
    threading.Thread(target=_nightly_scheduler_loop, daemon=True).start()

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


class UserFeedbackRequest(BaseModel):
    content: str = Field(min_length=1)


def _require_user_id(authorization: str | None) -> int:
    """`Authorization: Bearer <token>`ヘッダーからuser_idを取り出す。無効なら401を返す。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="認証が必要です。")
    token = authorization.removeprefix("Bearer ")
    user_id = auth.get_user_id_for_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="セッションが無効です。再ログインしてください。")
    return user_id


def _require_owner(authorization: str | None) -> int:
    """オーナー(那由多さん)以外なら403を返す。自己修復提案の承認・フィードバック
    一覧の閲覧など、オーナー専用の操作にだけ使う。"""
    user_id = _require_user_id(authorization)
    if not auth.is_owner(user_id):
        raise HTTPException(status_code=403, detail="この操作はオーナーのみ実行できます。")
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


@app.get("/api/auth/me")
def get_me(authorization: str | None = Header(None)) -> dict:
    """ログイン中のユーザー自身の情報とオーナー判定を返す。

    ログイン/登録レスポンス(AuthUser)はフロント側でlocalStorageに長期間
    キャッシュされるため、そこにis_ownerを混ぜるとOWNER_USER_NAME変更時に
    再ログインするまで古い判定が残ってしまう。そのため専用のエンドポイントに
    切り出し、フロントは毎回ここへ問い合わせてオーナー判定を得る。
    """
    user_id = _require_user_id(authorization)
    name = auth.get_user_name(user_id) or ""
    return {"user_id": user_id, "name": name, "is_owner": auth.is_owner(user_id)}


@app.get("/api/conversations")
def list_conversations(authorization: str | None = Header(None)) -> list[dict]:
    """ログイン中のユーザー自身の会話スレッドを、直近に更新された順で一覧する。"""
    user_id = _require_user_id(authorization)
    return [
        {"id": t.id, "title": t.title, "created_at": t.created_at, "updated_at": t.updated_at}
        for t in conversations.list_conversations(user_id)
    ]


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, authorization: str | None = Header(None)) -> dict:
    """ログイン中のユーザー自身の会話スレッドを削除する。

    他人の会話は削除できない(conversations.delete_conversation()が
    所有者一致チェックを行う)。見つからない・所有者不一致のどちらでも
    存在を漏らさないよう同じ404を返す。
    """
    user_id = _require_user_id(authorization)
    if not conversations.delete_conversation(conversation_id, user_id):
        raise HTTPException(status_code=404, detail="会話が見つかりませんでした。")
    return {"ok": True}


@app.get("/api/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: int, authorization: str | None = Header(None)
) -> list[dict]:
    """指定した会話の履歴を返す。他人の会話IDを渡された場合は空リストを返す
    (conversations.get_messages()内のuser_id一致チェックによる)。"""
    user_id = _require_user_id(authorization)
    return conversations.get_messages(conversation_id, user_id)


@app.get("/api/avatar")
def get_avatar(authorization: str | None = Header(None)) -> dict:
    """ログイン中のユーザーが解除済みの全身コーデ一覧と、直近の気分傾向を返す。

    カタログ(表示名・アセットファイル名)ごと返すことで、フロント側が
    src/memory/avatar_catalog.pyの内容を二重管理しなくて済むようにする。
    配列の並び順は解除日時の昇順(avatar.get_unlocked_slugsの順序どおり)なので、
    フロント側は最後の要素を「一番新しく解除したコーデ」として扱える。
    moodは直近の会話から検知した感情の傾向(hippocampus.get_recent_mood参照)で、
    データが無ければnull。
    """
    user_id = _require_user_id(authorization)
    catalog_by_slug = {item.slug: item for item in AVATAR_CATALOG}
    unlocked_items = [
        {
            "slug": slug,
            "display_name": catalog_by_slug[slug].display_name,
            "asset": catalog_by_slug[slug].asset,
        }
        for slug in avatar.get_unlocked_slugs(user_id)
        if slug in catalog_by_slug
    ]
    mood = hippocampus.get_recent_mood(user_id)
    return {
        "unlocked_items": unlocked_items,
        "mood": mood,
        "selected_slug": avatar.get_selected_slug(user_id),
    }


class SelectAvatarRequest(BaseModel):
    slug: str


@app.post("/api/avatar/select")
def select_avatar(
    request: SelectAvatarRequest, authorization: str | None = Header(None)
) -> dict:
    """着せ替え: 解除済みのコーデの中から、常に表示するものを選ぶ。

    未解除のアイテムは選べない(avatar.select_item()が再確認する)。
    """
    user_id = _require_user_id(authorization)
    if not avatar.select_item(user_id, request.slug):
        raise HTTPException(status_code=400, detail="そのコーデはまだ解除されていません。")
    return {"ok": True}


@app.get("/api/activity")
def get_activity(authorization: str | None = Header(None)) -> dict:
    """志粋の自律活動(睡眠モード・夜間修行・自律討論)の直近ログを返す。

    特定の友達に紐づくものではなく志粋自身の活動なので、認証は必須だが
    ログイン中のどのユーザーにも同じ内容を返す。
    """
    _require_user_id(authorization)
    return {"activities": activity_log.get_recent_activity()}


@app.get("/api/activity/sleep-status")
def get_sleep_status(authorization: str | None = Header(None)) -> dict:
    """睡眠モードが今まさに実行中かどうかを返す(フロントエンドのポーリング用)。

    那由多さんの要望(2026-07-28): 睡眠学習が始まったことがその場で分かる
    ようにしてほしい、を受けて追加。SLEEP_IN_PROGRESS_FILEの有無で判定する
    (src/memory/scheduler.pyがrun_sleep_cycle()の前後で作成・削除する)。
    """
    _require_user_id(authorization)
    return {"in_progress": SLEEP_IN_PROGRESS_FILE.exists()}


@app.get("/api/evolution/proposals")
def list_evolution_proposals(authorization: str | None = Header(None)) -> list[dict]:
    """承認待ちの自己修復提案を一覧する。オーナーのみ。"""
    _require_owner(authorization)
    return evolution.list_pending_proposals()


@app.get("/api/evolution/proposals/{proposal_id}")
def get_evolution_proposal(proposal_id: str, authorization: str | None = Header(None)) -> dict:
    """自己修復提案の詳細を返す。オーナーのみ。"""
    _require_owner(authorization)
    proposal = evolution.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="修正案が見つかりません。")
    return proposal


@app.post("/api/evolution/proposals/{proposal_id}/apply")
def apply_evolution_proposal(proposal_id: str, authorization: str | None = Header(None)) -> dict:
    """自己修復提案を適用する(git apply + commit)。オーナーのみ。

    apply_proposal()は「作業ツリーが汚れている」等の想定内の失敗を(bool, str)の
    タプルで返す設計になっているため、そのままok/messageとして返す(500にはしない)。
    """
    _require_owner(authorization)
    ok, message = evolution.apply_proposal(proposal_id)
    return {"ok": ok, "message": message}


@app.post("/api/evolution/proposals/{proposal_id}/reject")
def reject_evolution_proposal(proposal_id: str, authorization: str | None = Header(None)) -> dict:
    """自己修復提案を却下する。オーナーのみ。"""
    _require_owner(authorization)
    return {"ok": evolution.reject_proposal(proposal_id)}


@app.post("/api/feedback")
def submit_user_feedback(
    request: UserFeedbackRequest, authorization: str | None = Header(None)
) -> dict:
    """要望・フィードバックを送信する。ログイン中なら誰でも送信できる。

    user_id/user_nameは認証トークンから取得したものだけを使い、リクエスト
    ボディの値は一切信用しない(他人になりすませないようにするため)。
    """
    user_id = _require_user_id(authorization)
    user_name = auth.get_user_name(user_id) or ""
    record = user_feedback.submit_feedback(user_id, user_name, request.content)

    # 2026-07-27、那由多さんの明示的な同意により、要望・フィードバックの実装を
    # 自動で試みる(feedback_autopilot.py参照)。送信リクエスト自体は待たせない
    # よう別スレッドで実行する(diff生成・テスト実行にLLM呼び出し+数秒かかるため)。
    threading.Thread(
        target=feedback_autopilot.process_feedback, args=(record["id"],), daemon=True
    ).start()

    return record


@app.get("/api/feedback")
def list_user_feedback(authorization: str | None = Header(None)) -> list[dict]:
    """送信された要望・フィードバックの一覧(新しい順)を返す。オーナーのみ。"""
    _require_owner(authorization)
    return user_feedback.get_all_feedback()


@app.post("/api/feedback/{feedback_id}/dismiss")
def dismiss_user_feedback(feedback_id: str, authorization: str | None = Header(None)) -> dict:
    """要望・フィードバックを既読にする。オーナーのみ。"""
    _require_owner(authorization)
    user_feedback.mark_reviewed(feedback_id)
    return {"ok": True}


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


@app.post("/api/conversations/{conversation_id}/proactive-checkin")
def proactive_checkin(conversation_id: int, authorization: str | None = Header(None)) -> dict:
    """チャット画面を開いたまま数分間発言が無かったとき、志粋から自然に話しかける
    一言を生成して返す(フロントエンドが定期的にポーリングして呼ぶ)。

    生成した発話はhippocampus.log_episode()経由で通常のアシスタント発言として
    会話履歴に保存されるため、会話を読み込み直しても消えない。他人の
    conversation_idを渡された場合はconversations.get_messages()が空リストを
    返すため、不自然な(履歴を踏まえない)発話になるだけで情報は漏れない。
    """
    user_id = _require_user_id(authorization)
    content = generate_proactive_checkin(user_id, conversation_id)
    return {"content": content}
