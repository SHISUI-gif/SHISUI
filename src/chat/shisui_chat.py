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

from collections.abc import Iterator
from dataclasses import dataclass

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


def _stream_shisui_events_inner(user_message: str, history: list[dict]) -> Iterator[ChatEvent]:
    system_content = SHISUI_SYSTEM_PROMPT

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

    # 質問内容に応じて、その場で最適なモデル(コーディング特化・推論特化・軽量雑談用)へ振り分ける。
    # 無効時・分類失敗時はsettings.ollama_modelにフォールバックする(route_model内で吸収)。
    model = route_model(user_message)

    # 1段階目: 志粋自身に、自律検索(web_searchツール)が必要かどうか判断させる
    first_response = ollama.chat(model=model, messages=messages, tools=ALL_TOOL_SCHEMAS)
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
    # think=Trueにすると、推論対応モデル(deepseek-r1・Qwen3の思考モード等)は
    # 推論過程をcontentとは別のthinkingフィールドで返す。
    # 非対応モデル(qwen2.5系・qwen3-coder系など)はOllamaがHTTP 400で拒否するため
    # (「単に無視される」という当初の想定が誤りだった)、その場合はthinkなしで再試行する。
    try:
        response = ollama.chat(model=model, messages=messages, stream=True, think=True)
    except ollama.ResponseError as e:
        if e.status_code == 400 and "does not support thinking" in e.error:
            response = ollama.chat(model=model, messages=messages, stream=True)
        else:
            raise

    partial_content = ""
    for chunk in response:
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
