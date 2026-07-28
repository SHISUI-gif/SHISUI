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
import dataclasses
import hashlib

import groq
import httpx
import ollama
import pytest

from src.chat import shisui_chat
from src.corpus import ingest as literary_ingest
from src.core import error_log, evolution, feedback_log
from src.memory import conversations, hippocampus, neocortex


def _fake_embeddings(model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@pytest.fixture(autouse=True)
def _isolate_all_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(hippocampus, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    # conversations.pyはconfig.settingsからHIPPOCAMPUS_DB_PATHを直接importしており、
    # hippocampus.HIPPOCAMPUS_DB_PATHとは別の名前束縛のため、個別に隔離が必要
    # (generate_proactive_checkin()がconversations.get_messages()を呼ぶようになったため)
    monkeypatch.setattr(conversations, "HIPPOCAMPUS_DB_PATH", tmp_path / "hippocampus.sqlite3")
    monkeypatch.setattr(neocortex, "NEOCORTEX_DB_DIR", tmp_path / "neocortex_chroma")
    monkeypatch.setattr(literary_ingest, "LITERARY_CHROMA_DIR", tmp_path / "literary_chroma")
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)
    # エラー発生時にstream_shisui_events()がバックグラウンドスレッドで
    # evolution.generate_fix_proposals()を自動発火するため、デフォルトではno-opにしておく。
    # 個々のテストがmonkeypatchで上書きすれば、実際に呼ばれたことも検証できる
    # (スレッドはpytestのmonkeypatch巻き戻し後まで生き残りうるため、本物のollama.chat/
    # ファイルIOに触れさせないことが重要)
    monkeypatch.setattr(evolution, "generate_fix_proposals", lambda: [])
    # このマシンの実際の.env(USE_GROQ)に関わらず決定的に振る舞わせる。個々の
    # テストがGroq経由の挙動を検証したい場合は、自分でshisui_chat.settingsを
    # 上書きすればこの既定値を後から上書きできる(モンキーパッチは後勝ち)。
    # 2026-07-27、Oracle VM(USE_GROQ=true)で実際にこれが無いテストだけ
    # 実物のGroq APIを叩いてしまい、遅延・失敗する実害が出て気づいた。
    monkeypatch.setattr(shisui_chat, "settings", dataclasses.replace(shisui_chat.settings, use_groq=False))


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


def test_stream_shisui_events_triggers_background_evolution_scan_on_error(monkeypatch, tmp_path):
    """エラー発生時、手動で`evolution scan`を実行しなくても自己修復の修正案生成が
    自主的にバックグラウンドで走ることを検証する(以前は夜間サイクルか手動実行を
    待つ必要があった)。スレッドの完了を確定的に待つため、threading.Threadを
    「同期的にtarget()を呼ぶだけの偽物」に差し替える。"""
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")

    calls = []
    monkeypatch.setattr(evolution, "generate_fix_proposals", lambda: (calls.append(1), [])[1])

    class SyncThread:
        def __init__(self, target, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(shisui_chat.threading, "Thread", SyncThread)

    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}
        raise ollama.ResponseError("model not found", status_code=404)

    monkeypatch.setattr(ollama, "chat", fake_chat)

    list(shisui_chat.stream_shisui_reply("テスト", []))

    assert calls == [1]


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


def test_stream_shisui_reply_reflects_correction_immediately_via_neocortex(monkeypatch, tmp_path):
    """訂正は翌日の睡眠モードを待たず、次のターンから即座に思い出せる必要がある
    (「決めつけないで」と言われた直後に繰り返す、という事故を防ぐための要件)。"""
    monkeypatch.setattr(feedback_log, "FEEDBACK_LOG_FILE", tmp_path / "feedback_log.json")

    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}

        def gen():
            yield {"message": {"content": "ごめんね、気をつけるよ。"}}

        return gen()

    monkeypatch.setattr(ollama, "chat", fake_chat)

    history = [
        {"role": "user", "content": "最近文学の話ばかりしてるね"},
        {"role": "assistant", "content": "文学がお好きなんですね!"},
    ]
    list(
        shisui_chat.stream_shisui_reply(
            "そこまで好きではないな、決めつけるの気をつけて", history, user_id=42
        )
    )

    memories = neocortex.list_all(user_id=42)
    correction_memories = [m for m in memories if m.category == "correction"]
    assert len(correction_memories) == 1
    assert "決めつける" in correction_memories[0].text

    recall = shisui_chat.memory_context.build_recall_context(
        "最近どう?", user_id=42
    )
    assert "決めつける" in recall


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


def test_generate_proactive_checkin_returns_content_and_logs_episode(monkeypatch):
    conversation_id = conversations.create_conversation(user_id=1, first_message="カフェ巡りの話")
    hippocampus.log_episode(
        role="user", content="カフェ巡りの話", source="chat", user_id=1, conversation_id=conversation_id
    )
    hippocampus.log_episode(
        role="assistant", content="いいね!", source="chat", user_id=1, conversation_id=conversation_id
    )

    def fake_chat(model, messages, stream=False):
        assert stream is False
        # 直近の会話履歴がsystemの後に続けて渡っていること
        assert messages[0]["role"] == "system"
        assert any(m.get("content") == "カフェ巡りの話" for m in messages[1:])
        return {"message": {"content": "そういえばさっきのカフェの話、続き聞きたいな"}}

    monkeypatch.setattr(ollama, "chat", fake_chat)

    result = shisui_chat.generate_proactive_checkin(user_id=1, conversation_id=conversation_id)

    assert result == "そういえばさっきのカフェの話、続き聞きたいな"

    saved = conversations.get_messages(conversation_id, user_id=1)
    assert saved[-1] == {"role": "assistant", "content": "そういえばさっきのカフェの話、続き聞きたいな"}


def test_generate_proactive_checkin_uses_groq_when_enabled(monkeypatch):
    conversation_id = conversations.create_conversation(user_id=1, first_message="やあ")
    hippocampus.log_episode(
        role="user", content="やあ", source="chat", user_id=1, conversation_id=conversation_id
    )

    class _FakeSettings:
        use_groq = True
        groq_chat_model = "llama-3.3-70b"
        ollama_model = "qwen2.5"

    monkeypatch.setattr(shisui_chat, "settings", _FakeSettings())

    called = {}

    def fake_groq_chat(model, messages, stream=False):
        called["model"] = model
        return {"message": {"content": "元気にしてる?"}}

    monkeypatch.setattr(shisui_chat.groq_client, "chat", fake_groq_chat)

    result = shisui_chat.generate_proactive_checkin(user_id=1, conversation_id=conversation_id)

    assert result == "元気にしてる?"
    assert called["model"] == "llama-3.3-70b"


def test_generate_proactive_checkin_limits_history_to_recent_messages(monkeypatch):
    conversation_id = conversations.create_conversation(user_id=1, first_message="最初")
    for i in range(20):
        hippocampus.log_episode(
            role="user" if i % 2 == 0 else "assistant",
            content=f"メッセージ{i}",
            source="chat",
            user_id=1,
            conversation_id=conversation_id,
        )

    captured = {}

    def fake_chat(model, messages, stream=False):
        captured["messages"] = messages
        return {"message": {"content": "おかえり"}}

    monkeypatch.setattr(ollama, "chat", fake_chat)

    shisui_chat.generate_proactive_checkin(user_id=1, conversation_id=conversation_id)

    # system 1件 + 直近10件のみで、20件全部を積み上げていないこと
    assert len(captured["messages"]) == 11


def test_generate_proactive_checkin_retries_once_on_empty_response(monkeypatch):
    """ローカルLLMがまれに空応答を返す既知の癖への対応: 1回だけ取り直しを試みる。"""
    conversation_id = conversations.create_conversation(user_id=1, first_message="やあ")
    hippocampus.log_episode(
        role="user", content="やあ", source="chat", user_id=1, conversation_id=conversation_id
    )

    call_count = {"n": 0}

    def fake_chat(model, messages, stream=False):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"message": {"content": ""}}
        return {"message": {"content": "おかえり、元気にしてた?"}}

    monkeypatch.setattr(ollama, "chat", fake_chat)

    result = shisui_chat.generate_proactive_checkin(user_id=1, conversation_id=conversation_id)

    assert result == "おかえり、元気にしてた?"
    assert call_count["n"] == 2


def test_generate_proactive_checkin_returns_none_and_does_not_log_when_still_empty(monkeypatch):
    """1回取り直しても空のままなら、Noneを返し履歴にも保存しない
    (空応答を保存すると、次回以降の生成が悪循環的に空になりやすくなるため)。"""
    conversation_id = conversations.create_conversation(user_id=1, first_message="やあ")
    hippocampus.log_episode(
        role="user", content="やあ", source="chat", user_id=1, conversation_id=conversation_id
    )

    monkeypatch.setattr(ollama, "chat", lambda model, messages, stream=False: {"message": {"content": "   "}})

    result = shisui_chat.generate_proactive_checkin(user_id=1, conversation_id=conversation_id)

    assert result is None
    saved = conversations.get_messages(conversation_id, user_id=1)
    assert all(m["content"].strip() for m in saved)  # 空のエントリが追加されていないこと


def test_generate_proactive_checkin_filters_out_past_empty_entries_from_history(monkeypatch):
    """過去にこの不具合で保存されてしまった空のアシスタント発言が履歴に残っていても、
    LLMへ渡す会話履歴からは除外する(空応答の連鎖を断ち切るため)。"""
    conversation_id = conversations.create_conversation(user_id=1, first_message="やあ")
    hippocampus.log_episode(
        role="user", content="やあ", source="chat", user_id=1, conversation_id=conversation_id
    )
    hippocampus.log_episode(
        role="assistant", content="", source="proactive_checkin", user_id=1, conversation_id=conversation_id
    )
    hippocampus.log_episode(
        role="user", content="いる?", source="chat", user_id=1, conversation_id=conversation_id
    )

    captured = {}

    def fake_chat(model, messages, stream=False):
        captured["messages"] = messages
        return {"message": {"content": "うん、いるよ"}}

    monkeypatch.setattr(ollama, "chat", fake_chat)

    shisui_chat.generate_proactive_checkin(user_id=1, conversation_id=conversation_id)

    assert all(m.get("content", "").strip() for m in captured["messages"])


def test_call_tool_ignoring_unknown_kwargs_drops_args_not_in_signature():
    """2026-07-27に実際に本番で起きた事故の回帰テスト: LLMがget_weatherに
    スキーマに無い"time"引数を勝手に付け足し、TypeErrorでツール呼び出し
    全体が落ちた。シグネチャに無いキーは黙って無視して呼び出すべき。"""

    def fake_get_weather(location: str | None = None) -> str:
        return f"location={location}"

    result = shisui_chat._call_tool_ignoring_unknown_kwargs(
        fake_get_weather, {"location": "東京", "time": "night"}
    )

    assert result == "location=東京"


def test_call_tool_ignoring_unknown_kwargs_still_works_with_no_extra_args():
    def fake_get_weather(location: str | None = None) -> str:
        return f"location={location}"

    result = shisui_chat._call_tool_ignoring_unknown_kwargs(fake_get_weather, {"location": "大阪"})

    assert result == "location=大阪"


def test_stream_shisui_events_falls_back_when_groq_tool_detection_rejects_call(monkeypatch, tmp_path):
    """2026-07-27に本番で実際に発生: Groqの軽量モデル(llama-3.1-8b-instant)が
    構造化ツール呼び出しの代わりに独自記法("<function=...>")を出力し、Groqが
    tool_use_failedとして400を返すことがある。ツール検知1回の失敗で会話全体を
    落とすのではなく、その回はツール無しとして通常応答へフォールバックすべき。"""
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")
    monkeypatch.setattr(
        shisui_chat, "settings", dataclasses.replace(shisui_chat.settings, use_groq=True)
    )

    fake_response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com/x"))

    def fake_groq_chat(model, messages, tools=None, stream=False):
        if tools:
            raise groq.BadRequestError("tool_use_failed", response=fake_response, body=None)
        assert stream is True
        return iter([{"message": {"content": "天気ツールは使えなかったけど元気だよ!"}}])

    monkeypatch.setattr(shisui_chat.groq_client, "chat", fake_groq_chat)

    results = list(shisui_chat.stream_shisui_reply("今日の天気は?", []))

    assert results[-1] == "天気ツールは使えなかったけど元気だよ!"
    logged = error_log.get_unreviewed_errors()
    assert any(e["source"] == "tool_detection" for e in logged)


def test_stream_shisui_events_falls_back_when_tool_detection_request_too_large(monkeypatch, tmp_path):
    """2026-07-28に本番で実際に発生: 413(Request too large)はgroq.BadRequestError
    ではなく共通基底クラスgroq.APIStatusErrorとして送出されるため、
    BadRequestErrorだけを拾うexceptでは素通ししてしまい、会話全体が
    生のエラーダンプで落ちていた。"""
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")
    monkeypatch.setattr(
        shisui_chat, "settings", dataclasses.replace(shisui_chat.settings, use_groq=True)
    )

    fake_response = httpx.Response(413, request=httpx.Request("POST", "https://api.groq.com/x"))

    def fake_groq_chat(model, messages, tools=None, stream=False):
        if tools:
            raise groq.APIStatusError("request too large", response=fake_response, body=None)
        assert stream is True
        return iter([{"message": {"content": "ツール判定はスキップして応答するね"}}])

    monkeypatch.setattr(shisui_chat.groq_client, "chat", fake_groq_chat)

    results = list(shisui_chat.stream_shisui_reply("何か聞きたいことがあるんだけど", []))

    assert results[-1] == "ツール判定はスキップして応答するね"
    logged = error_log.get_unreviewed_errors()
    assert any(e["source"] == "tool_detection" for e in logged)


def test_tool_detection_call_excludes_persona_prompt_and_caps_history(monkeypatch, tmp_path):
    """2026-07-28の回帰テスト: 会話が長くなるほどフルの人格プロンプト+履歴全体を
    軽量分類モデルに渡してしまい、TPM(1分あたりトークン数)上限を超えて
    413になっていた。ツール判定にはフルの人格プロンプトは不要で、履歴も
    直近数ターンだけに絞るべき。"""
    monkeypatch.setattr(error_log, "ERROR_LOG_FILE", tmp_path / "error_log.json")

    captured = {}
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"メッセージ{i}"} for i in range(40)
    ]

    def fake_chat(model, messages, tools=None, stream=False, think=None, keep_alive=None):
        if tools:
            captured["messages"] = messages
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}

        def gen():
            yield {"message": {"content": "応答するね。"}}

        return gen()

    monkeypatch.setattr(ollama, "chat", fake_chat)

    list(shisui_chat.stream_shisui_reply("最新の発言", long_history))

    tool_messages = captured["messages"]
    assert shisui_chat.SHISUI_SYSTEM_PROMPT not in tool_messages[0]["content"]
    assert tool_messages[0]["content"] == shisui_chat.TOOL_DETECTION_SYSTEM_PROMPT
    # system 1件 + 直近数ターンのみで、40件全部を積み上げていないこと
    assert len(tool_messages) <= shisui_chat._TOOL_DETECTION_HISTORY_TURNS + 2


def test_stream_shisui_reply_falls_back_to_secondary_groq_model_on_rate_limit(monkeypatch):
    """2026-07-27に本番で実際に発生: Groq無料枠のTPD(1日あたりトークン)上限に
    達すると429が返り、会話が完全に止まってしまっていた。モデルごとに独立した
    プールなので、フォールバックモデルへ1回だけ切り替えて継続すべき。"""
    monkeypatch.setattr(
        shisui_chat,
        "settings",
        dataclasses.replace(
            shisui_chat.settings, use_groq=True, groq_fallback_chat_model="llama-3.3-70b-versatile"
        ),
    )

    fake_response = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/x"))
    calls = []

    def fake_groq_chat(model, messages, tools=None, stream=False):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}
        calls.append(model)
        if model != "llama-3.3-70b-versatile":
            raise groq.RateLimitError("rate_limit_exceeded", response=fake_response, body=None)
        return iter([{"message": {"content": "フォールバックで応答するね"}}])

    monkeypatch.setattr(shisui_chat.groq_client, "chat", fake_groq_chat)

    results = list(shisui_chat.stream_shisui_reply("テスト", []))

    assert results[-1] == "フォールバックで応答するね"
    assert calls[-1] == "llama-3.3-70b-versatile"


def test_stream_shisui_reply_returns_friendly_message_when_all_groq_tiers_exhausted(monkeypatch):
    """2026-07-28に本番で実際に発生: フォールバック先(llama-3.3-70b-versatile)
    自体もTPD上限に達し、3段目も無い当時は生のエラーダンプで会話が落ちていた。
    全段が枯渇した場合でも、生のエラーではなく分かりやすい一言で会話を終える。"""
    monkeypatch.setattr(
        shisui_chat,
        "settings",
        dataclasses.replace(
            shisui_chat.settings,
            use_groq=True,
            groq_fallback_chat_model="llama-3.3-70b-versatile",
            groq_second_fallback_chat_model="openai/gpt-oss-120b",
        ),
    )

    fake_response = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/x"))
    calls = []

    def fake_groq_chat(model, messages, tools=None, stream=False):
        if tools:
            return {"message": {"role": "assistant", "content": "", "tool_calls": None}}
        calls.append(model)
        raise groq.RateLimitError("rate_limit_exceeded", response=fake_response, body=None)

    monkeypatch.setattr(shisui_chat.groq_client, "chat", fake_groq_chat)

    results = list(shisui_chat.stream_shisui_reply("テスト", []))

    assert calls[1:] == ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]
    assert "使い切っちゃった" in results[-1]
