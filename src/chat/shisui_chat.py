"""志粋の「頭脳」— UIフレームワークに依存しない会話ロジック。

人格プロンプトの構築、記憶/文学的感性コーパス/夜間修行レポートの注入、
自律検索ツールコールの判定・実行、ストリーミング応答生成、海馬への記録までを
純粋なジェネレータ関数として提供する。Gradio(shisui_app.py)・FastAPI(src/api/main.py)の
どちらのフロントエンドからも、この同じ関数を呼び出すことで同じ「志粋」として振る舞う。

`stream_shisui_events()`が実際にOllamaと対話する唯一の実装で、"thinking"/"content"/
"tool_status"の3種類の構造化イベントを逐次yieldする。Gradio向けの`stream_shisui_reply()`は
その上に薄く被せた「累積HTML文字列」への変換レイヤーに過ぎない。
"""
from __future__ import annotations

import concurrent.futures
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

import ollama

from config.settings import settings
from src.chat.model_router import route_model
from src.common.persona import SHISUI_SYSTEM_PROMPT
from src.common.tools import ALL_TOOL_SCHEMAS, AVAILABLE_TOOLS
from src.core import error_log
from src.corpus import context as literary_context
from src.memory import context as memory_context
from src.memory import hippocampus
from src.study import report as study_report


@dataclass
class ChatEvent:
    type: str  # "thinking" | "content" | "tool_status"
    text: str


def _normalize_history(history: list[dict]) -> list[dict]:
    """historyのcontentを、Ollamaが要求する文字列形式に揃える。

    Gradio 6.xなど一部のフロントエンドは、contentを文字列ではなく
    [{"type": "text", "text": "..."}] 形式のパーツ配列で渡すことがあり、
    そのままOllamaに渡すとMessage.contentのバリデーションエラーになるため正規化する。
    """
    normalized = []
    for turn in history:
        content = turn.get("content")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        normalized.append({"role": turn.get("role"), "content": content})
    return normalized


def stream_shisui_events(user_message: str, history: list[dict]) -> Iterator[ChatEvent]:
    """志粋の応答を、構造化イベント("thinking"/"content"/"tool_status")として逐次yieldする。

    実際にOllamaと対話する唯一の実装。Gradio向け・FastAPI向けの両方が、
    この関数の出力を自分の形式に整形するだけの薄いレイヤーとして実装される。

    内部の処理(記憶検索・ツールコール・Ollama通信)のどこで例外が起きても、
    ここで必ず捕捉してエラーイベントに変換する。捕捉範囲をOllama呼び出しだけに
    絞っていた際、記憶検索(embedding呼び出し)側の例外がそのまま外へ漏れ、
    FastAPIのストリームごと強制終了する不具合があったため、関数全体を対象にしている。
    """
    try:
        yield from _stream_shisui_events_inner(user_message, history)
    except Exception as e:  # noqa: BLE001
        # ユーザーには要点だけを見せつつ、完全なトレースバックは自己修復プロトコル
        # (src/core/evolution.py)が後で読めるようエラーログに残しておく
        error_log.log_error(source="stream_shisui_events", exc=e)
        yield ChatEvent(
            type="content",
            text=f"⚠️ エラーが発生しちゃった:{str(e)}\nOllamaが起動しているか、モデル名が正しいか確認してね!",
        )


_MODEL_SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)b", re.IGNORECASE)
_HEAVY_MODEL_PARAM_THRESHOLD = 20  # 億単位ではなくB(billion)単位のパラメータ数


def _keep_alive_for(model: str) -> str:
    """モデルサイズに応じてkeep_aliveを変える。

    20B超級の重いモデル(qwen2.5:32b・qwen3-coder:30b等)は使用後すぐ解放しないと
    メモリを圧迫してスワップを引き起こす(524タイムアウトの一因になっていた)ため
    即座に解放する。8B前後の中量級モデルはメモリ負荷が軽いため、次の応答に
    備えて短時間だけ常駐させておく方が(再ロードのコストを避けられて)有利。
    サイズが読み取れないモデル名の場合は安全側(即解放)に倒す。
    """
    match = _MODEL_SIZE_PATTERN.search(model)
    if match and float(match.group(1)) < _HEAVY_MODEL_PARAM_THRESHOLD:
        return "1m"
    return "0"


def _stream_with_think_fallback(model: str, messages: list[dict]) -> Iterator[dict]:
    """think=Trueで応答をストリーミングし、対応していないモデルなら自動でthinkなしに切り替えて再試行する。

    Ollamaは「think非対応」エラー("does not support thinking", 400)を、
    chat()呼び出し時点ではなく、実際にレスポンスをイテレートし始めた瞬間に
    遅延して投げてくる(ストリーミング用のレスポンスは遅延評価されるため)。
    そのため呼び出しだけでなく、forループでのイテレーションもtry/exceptで
    包む必要がある。モデルの能力チェックは生成開始前にサーバー側で行われるため、
    このエラーが起きる時点でチャンクは1つも返っていない(取りこぼしの心配はない)。
    """
    # 常時使う軽量な分類モデル(_stream_shisui_events_inner内の並列呼び出し)は
    # ここでのkeep_alive調整の対象外にして、既定のまま素早く再利用できるようにする。
    keep_alive = _keep_alive_for(model)
    try:
        yield from ollama.chat(
            model=model, messages=messages, stream=True, think=True, keep_alive=keep_alive
        )
    except ollama.ResponseError as e:
        if e.status_code == 400 and "does not support thinking" in e.error:
            yield from ollama.chat(model=model, messages=messages, stream=True, keep_alive=keep_alive)
        else:
            raise


def _stream_shisui_events_inner(user_message: str, history: list[dict]) -> Iterator[ChatEvent]:
    # モデルは学習データの時点を「現在」だと錯覚するため(例: 「来期のアニメ」を
    # 学習当時の季節で検索してしまう)、実際の今日の日付を明示的に教える。
    today_str = datetime.now().strftime("%Y年%m月%d日")
    system_content = (
        SHISUI_SYSTEM_PROMPT
        + f"\n\n今日の日付は{today_str}です。「最新」「今期」「来期」「現在」などの"
        "時間に関する言及は、必ずこの日付を基準に判断・検索してください。"
    )

    recall_context = memory_context.build_recall_context(user_message)
    if recall_context:
        system_content += "\n\n" + recall_context

    literary_hint = literary_context.build_literary_hint(user_message)
    if literary_hint:
        system_content += "\n\n" + literary_hint

    unread_study_report = study_report.get_unread_report()
    if unread_study_report:
        system_content += "\n\n" + unread_study_report
        study_report.mark_report_read()

    messages = [{"role": "system", "content": system_content}]
    messages.extend(_normalize_history(history))
    messages.append({"role": "user", "content": user_message})

    hippocampus.log_episode(role="user", content=user_message, source="chat")

    # 「どのモデルへ振り分けるか」と「検索が必要か」は互いの結果に依存しないため、
    # 並列に実行して待ち時間を短縮する(直列だと合計6〜8秒かかっていたのがmax()で済む)。
    # ツール判定は振り分け先の大きいモデル(qwen2.5:32b等)ではなく軽量な分類モデルを使う
    # (応答が全く届かない時間が長引くと、Cloudflareトンネル経由で524タイムアウトになるため)。
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        model_future = executor.submit(route_model, user_message)
        tool_future = executor.submit(
            ollama.chat,
            model=settings.router_classifier_model,
            messages=messages,
            tools=ALL_TOOL_SCHEMAS,
        )
        model = model_future.result()
        first_response = tool_future.result()

    assistant_message = first_response["message"]
    tool_calls = assistant_message["tool_calls"] if "tool_calls" in assistant_message else None

    if tool_calls:
        messages.append(assistant_message)
        for call in tool_calls:
            tool_name = call["function"]["name"]
            arguments = call["function"]["arguments"]
            query = arguments.get("query", "")
            yield ChatEvent(type="tool_status", text=f"🔍 「{query}」について自律検索中...ちょっと待ってね!")

            tool_fn = AVAILABLE_TOOLS.get(tool_name)
            tool_result = tool_fn(**arguments) if tool_fn else f"未知のツール: {tool_name}"
            messages.append({"role": "tool", "content": tool_result, "tool_name": tool_name})

    # 2段階目: (検索結果があれば踏まえて)最終回答をストリーミング生成。
    partial_content = ""
    for chunk in _stream_with_think_fallback(model, messages):
        message = chunk.get("message", {})
        thinking_piece = message.get("thinking")
        if thinking_piece:
            yield ChatEvent(type="thinking", text=thinking_piece)
        content_piece = message.get("content")
        if content_piece:
            partial_content += content_piece
            yield ChatEvent(type="content", text=content_piece)

    if partial_content:
        hippocampus.log_episode(role="assistant", content=partial_content, source="chat")


def stream_shisui_reply(user_message: str, history: list[dict]) -> Iterator[str]:
    """Gradio向け: 志粋としての応答を、累積HTML文字列として逐次yieldする。

    呼び出しごとに部分的な応答テキストが積み上がった状態でyieldされる
    (Gradio ChatInterfaceの規約に合わせている)。中身はstream_shisui_events()を
    整形しているだけで、Ollamaとの対話ロジック自体は一切重複させない。
    """
    partial_thinking = ""
    partial_content = ""
    for event in stream_shisui_events(user_message, history):
        if event.type == "tool_status":
            yield event.text
            continue

        if event.type == "thinking":
            partial_thinking += event.text
        elif event.type == "content":
            partial_content += event.text

        display = ""
        if partial_thinking:
            display += (
                '<span style="color:#999999; font-size:0.85em;">'
                f"[思考中...] {partial_thinking}</span>\n\n"
            )
        display += partial_content
        if display:
            yield display
