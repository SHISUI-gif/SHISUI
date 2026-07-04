"""志粋の頭脳(src/chat/shisui_chat.py)の思考中表示ロジックをモックで検証する。

実際のOllamaサーバーには接続せず、think=Trueで得られるthinkingフィールドの
有無に応じた表示切り替えのみを検証する(会話ロジック全体はshisui_app.py側の
モジュールテストで別途検証済み)。

stream_shisui_reply()/stream_shisui_events()は内部でhippocampus.log_episode()・
memory_context.build_recall_context()・literary_context.build_literary_hint()を
必ず呼ぶため、以前は一部のテストだけがERROR_LOG_FILE等を個別に隔離しており、
海馬(本番のHIPPOCAMPUS_DB_PATH)への書き込みが隔離されていなかった。
stream_shisui_reply()はuser_id/conversation_idを省略するとデフォルト値(1, 1)を
使うため、これがそのまま本番DBの実際のuser_id=1アカウントと衝突し、テスト用の
偽の会話が実ユーザーの会話履歴に紛れ込むという実害のある不具合になっていた。
このファイル全体にautouseで最小限の隔離をかけることで、個々のテストが
明示的に隔離し忘れても本番データに触れないようにする。
"""
import hashlib

import ollama
import pytest

from src.chat import shisui_chat
from src.corpus import ingest as literary_ingest
from src.core import error_log, feedback_log
from src.memory import hippocampus, neocortex


def _fake_embeddings(model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@pytest.fixture(autouse=True)
def _isolate_all_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    monkeypatch.setattr(neocortex, "NEOCORTEX_DB_DIR", tmp_path / "neocortex_chroma")
    monkeypatch.setattr(literary_ingest, "LITERARY_CHROMA_DIR", tmp_path / "literary_chroma")
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)


@pytest.mark.parametrize(
    "model,expected",
    [
        ("qwen2.5:32b", "0"),
        ("qwen3-coder:30b", "0"),
        ("deepseek-r1:8b", "1m"),
        ("qwen3:8b", "1m"),
        ("qwen3:1.7b", "1m"),
        ("model-without-a-size", "0"),  # サイズ不明なら安全側(即解放)に倒す
    ],
)
def test_keep_alive_for_by_model_size(model, expected):
    assert shisui_chat._keep_alive_for(model) == expected


def test_stream_shisui_reply_shows_thinking_when_present(monkeypatch):
    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}

        def gen():
            yield {"message": {"thinking": "まず要件を整理する。"}}
            yield {"message": {"content": "こんにちは、志粋だよ。"}}

        return gen()

    monkeypatch.setattr(ollama, "chat", fake_chat)

    results = list(shisui_chat.stream_shisui_reply("テスト", []))

    assert "[思考中...]" in results[0]
    assert "まず要件を整理する。" in results[0]
    assert "こんにちは、志粋だよ。" in results[-1]


def test_stream_shisui_reply_omits_thinking_block_when_absent(monkeypatch):
    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}

        def gen():
            yield {"message": {"content": "普通の応答だよ。"}}

        return gen()

    monkeypatch.setattr(ollama, "chat", fake_chat)

    results = list(shisui_chat.stream_shisui_reply("テスト", []))

    assert all("[思考中...]" not in r for r in results)
    assert results[-1] == "普通の応答だよ。"


def test_stream_shisui_reply_retries_without_think_when_model_unsupported(monkeypatch):
    """qwen2.5:32bのような非対応モデルにthink=Trueを渡すとOllamaが400を返す実際の挙動を再現し、
    自動的にthinkなしで再試行して応答が続くことを検証する。

    実際のOllamaは、この「think非対応」エラーをchat()呼び出し時点ではなく、
    ストリーミングレスポンスをイテレートし始めた瞬間に遅延して投げてくる。
    fake_chatの`think=True`ケースをジェネレータの中でraiseすることで、
    その遅延評価の挙動を正確に再現している(呼び出し時点でraiseする実装だと、
    この不具合を見逃してしまっていた)。"""
    calls = []

    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if not stream:
            # ツール判定呼び出し・model_routerの分類呼び出し(いずれもstream未指定)は
            # 通常の応答として素通しする
            return {"message": {"role": "assistant", "content": "CHAT", "tool_calls": None}}

        calls.append(think)

        def gen():
            if think:
                raise ollama.ResponseError('"qwen2.5:32b" does not support thinking', status_code=400)
            yield {"message": {"content": "通常モードで応答するね。"}}

        return gen()

    monkeypatch.setattr(ollama, "chat", fake_chat)

    results = list(shisui_chat.stream_shisui_reply("テスト", []))

    assert calls == [True, None]
    assert results[-1] == "通常モードで応答するね。"


def test_stream_shisui_reply_reraises_other_response_errors(monkeypatch, tmp_path):
    # stream_shisui_reply()は内部でerror_log.log_error()を呼ぶため、
    # 本番のエラーログファイルを汚染しないよう必ず隔離する
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")

    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}
        raise ollama.ResponseError("model not found", status_code=404)

    monkeypatch.setattr(ollama, "chat", fake_chat)

    results = list(shisui_chat.stream_shisui_reply("テスト", []))

    assert "エラーが発生しちゃった" in results[-1]


def test_stream_shisui_reply_logs_unexpected_errors(monkeypatch, tmp_path):
    """自己修復プロトコルが後で拾えるよう、未処理例外はerror_logにも記録される。"""
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")

    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}
        raise ollama.ResponseError("model not found", status_code=404)

    monkeypatch.setattr(ollama, "chat", fake_chat)

    list(shisui_chat.stream_shisui_reply("テスト", []))

    logged = error_log.get_unreviewed_errors()
    assert len(logged) == 1
    assert logged[0]["source"] == "stream_shisui_events"
    assert logged[0]["error_type"] == "ResponseError"


def test_stream_shisui_reply_logs_correction_feedback(monkeypatch, tmp_path):
    """例外が起きていなくても、訂正・不満らしい発言はfeedback_logに残る。"""
    monkeypatch.setattr(feedback_log, "FEEDBACK_LOG_FILE", tmp_path / "feedback_log.json")

    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}

        def gen():
            yield {"message": {"content": "了解、次から気をつけるね。"}}

        return gen()

    monkeypatch.setattr(ollama, "chat", fake_chat)

    history = [
        {"role": "user", "content": "来期のアニメ教えて"},
        {"role": "assistant", "content": "2023年冬のアニメは..."},
    ]
    list(shisui_chat.stream_shisui_reply("それ違うよ、今は2026年だよ", history))

    unreviewed = feedback_log.get_unreviewed_feedback()
    assert len(unreviewed) == 1
    assert unreviewed[0]["previous_user_message"] == "来期のアニメ教えて"
    assert unreviewed[0]["previous_assistant_response"] == "2023年冬のアニメは..."
    assert unreviewed[0]["correction_message"] == "それ違うよ、今は2026年だよ"


def test_stream_shisui_reply_does_not_log_feedback_for_normal_messages(monkeypatch, tmp_path):
    monkeypatch.setattr(feedback_log, "FEEDBACK_LOG_FILE", tmp_path / "feedback_log.json")

    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}

        def gen():
            yield {"message": {"content": "どういたしまして!"}}

        return gen()

    monkeypatch.setattr(ollama, "chat", fake_chat)

    history = [
        {"role": "user", "content": "来期のアニメ教えて"},
        {"role": "assistant", "content": "2026年のアニメは..."},
    ]
    list(shisui_chat.stream_shisui_reply("ありがとう!", history))

    assert feedback_log.get_unreviewed_feedback() == []


def test_stream_shisui_events_logs_episodes_with_user_and_conversation_id(monkeypatch):
    """user_id・conversation_idが海馬への記録まで正しく伝わることを検証する
    (友達それぞれの会話を混ぜない/覗き見しないための多ユーザー化の要)。"""
    monkeypatch.setattr(shisui_chat.memory_context, "build_recall_context", lambda *a, **k: "")
    monkeypatch.setattr(shisui_chat.literary_context, "build_literary_hint", lambda *a, **k: "")

    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}

        def gen():
            yield {"message": {"content": "了解!"}}

        return gen()

    monkeypatch.setattr(ollama, "chat", fake_chat)

    list(shisui_chat.stream_shisui_events("こんにちは", [], user_id=42, conversation_id=7))

    episodes = hippocampus.get_unconsolidated_episodes()
    assert len(episodes) == 2
    assert all(e.user_id == 42 and e.conversation_id == 7 for e in episodes)
