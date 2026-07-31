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
import inspect
import math
import os
import re
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

import groq
import ollama
from rich.console import Console

from config.settings import settings
from src.chat import emotion
from src.chat.model_router import route_model
from src.common import groq_client, openrouter_client
from src.common.persona import SHISUI_SYSTEM_PROMPT
from src.common.tools import ALL_TOOL_SCHEMAS, AVAILABLE_TOOLS
from src.core import error_log, evolution
from src.core import feedback_log
from src.corpus import context as literary_context
from src.memory import context as memory_context
from src.memory import conversations, hippocampus, neocortex
from src.study import report as study_report

console = Console()


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


def stream_shisui_events(
    user_message: str, history: list[dict], user_id: int, conversation_id: int
) -> Iterator[ChatEvent]:
    """志粋の応答を、構造化イベント("thinking"/"content"/"tool_status")として逐次yieldする。

    実際にOllamaと対話する唯一の実装。FastAPI(src/api/main.py)が、この関数の
    出力をNDJSON形式に整形するだけの薄いレイヤーとして実装される。

    user_id・conversation_idは、友達それぞれの会話・記憶を混ぜない/覗き見しない
    ためのスコープ(海馬への記録・新皮質での記憶検索の両方に使われる)。

    内部の処理(記憶検索・ツールコール・Ollama通信)のどこで例外が起きても、
    ここで必ず捕捉してエラーイベントに変換する。捕捉範囲をOllama呼び出しだけに
    絞っていた際、記憶検索(embedding呼び出し)側の例外がそのまま外へ漏れ、
    FastAPIのストリームごと強制終了する不具合があったため、関数全体を対象にしている。
    """
    try:
        yield from _stream_shisui_events_inner(user_message, history, user_id, conversation_id)
    except Exception as e:  # noqa: BLE001
        # ユーザーには要点だけを見せつつ、完全なトレースバックは自己修復プロトコル
        # (src/core/evolution.py)が後で読めるようエラーログに残しておく
        error_log.log_error(source="stream_shisui_events", exc=e)
        _trigger_background_evolution_scan()
        yield ChatEvent(
            type="content",
            text=f"⚠️ エラーが発生しちゃった:{str(e)}\nOllamaが起動しているか、モデル名が正しいか確認してね!",
        )


def _trigger_background_evolution_scan() -> None:
    """エラー発生直後に、修正案生成→(evolution_auto_apply設定に従い)自動適用を
    自主的にバックグラウンドで走らせる。生成・適用ともにLLM呼び出しやテスト実行を
    伴うため、今エラーになった会話のストリームは決してブロックしない
    (別スレッドで実行し、失敗しても会話には一切影響しない)。

    2026-07-27、那由多さんの明示的な同意によりevolution.auto_apply_fix_proposals()
    (テスト全件通過を条件にした無承認の自動適用)を呼ぶよう変更。systemd管理下
    (INVOCATION_ID環境変数の有無で判定)で1件でも適用できた場合は、変更を実際の
    挙動に反映させるためプロセスを終了し、systemdのRestart=alwaysに再起動させる
    (ローカルMacでの手動実行時は再起動せず、次回起動時に反映される)。
    """

    def _run() -> None:
        try:
            results = evolution.auto_apply_fix_proposals()
            applied = [proposal for proposal, success, _ in results if success]
            if applied:
                console.print(
                    f"[dim]🔧 自己修復: {len(applied)}件を自動適用しました"
                    f"({', '.join(p.file_path for p in applied)})[/dim]"
                )
                if os.environ.get("INVOCATION_ID"):
                    console.print("[dim]🔄 変更を反映するため再起動します(systemdが自動で立ち上げ直します)[/dim]")
                    os._exit(0)
            for proposal, success, message in results:
                if not success:
                    console.print(
                        f"[yellow]自己修復: {proposal.file_path}の修正案は適用されませんでした: {message}[/yellow]"
                    )
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]自己修復の自動実行に失敗しました(会話は続行します): {exc}[/yellow]")

    threading.Thread(target=_run, daemon=True).start()


_MODEL_SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)b", re.IGNORECASE)
_HEAVY_MODEL_PARAM_THRESHOLD = 20  # 億単位ではなくB(billion)単位のパラメータ数

TOOL_DETECTION_SYSTEM_PROMPT = (
    "あなたは志粋というAIアシスタントの、ツール呼び出し判定専用の内部処理です。"
    "直近の会話とユーザーの最新の発言を見て、提供されたツールを使うべきか判断して"
    "ください。ツールが必要な場合だけ呼び出し、雑談など不要な場合はツールを"
    "呼ばずに何も出力しないでください。"
)
# フルの人格プロンプト・記憶検索結果は渡さず、直近の履歴もここまでに絞る
# (会話が長くなるほどTPM上限を超えて413になっていた実害への対処、2026-07-28)。
_TOOL_DETECTION_HISTORY_TURNS = 6
# 最終回答生成の会話履歴も同じ理由で無制限には積まない(2026-07-29、
# qwen3.6-27b自体のTPM上限(8000)を、長い会話ではフルの人格プロンプト+
# 記憶検索結果+全履歴の合計が超えてしまい413になる実害が発生)。ツール判定
# より文脈の連続性が重要なため、少し長めに取る。
_MAIN_GENERATION_HISTORY_TURNS = 20

# 2026-07-31、上記2つの「ターン数」による打ち切りだけでは413(Request too large)を
# 防ぎきれないことが本番で再確認された(max_completion_tokensを8192→4096に
# 下げた後も、"Requested 8889"/"Requested 6410"のように依然としてTPM上限を
# 超過し続けていた)。ターン数は固定でも、1ターンあたりの文字数は会話によって
# 大きく変わる(ユーザーの長文貼り付け・志粋自身の長めの返答など)ため、
# 件数ベースの上限では実際のトークン量を抑えきれない。ここから下は、実際の
# 文字数からトークン数を概算し、Groq利用時(settings.use_groq)に限って履歴を
# 動的に(会話が長い/重いほど多く)間引く、トークン予算ベースの安全網を追加する。
# ローカルOllama利用時はTPMという概念自体が無いため対象外。
_GROQ_MAIN_GENERATION_TPM_LIMIT = 8000  # qwen/qwen3.6-27b(groq_chat_model)の無料枠TPM
_GROQ_TOOL_DETECTION_TPM_LIMIT = 6000  # llama-3.1-8b-instant(groq_classifier_model)の無料枠TPM
_GROQ_SAFETY_MARGIN_TOKENS = 500  # 概算誤差・メッセージのrole/JSON構造オーバーヘッド分の余裕
# ツール判定は関数呼び出しの引数(短いJSON)か「ツール不要」の判定だけを返せば
# よく、雑談の返答のような長さは要らない。予約分を大きく減らすほど、TPM予算の
# うち実際の履歴に回せる分が増える。
_TOOL_DETECTION_MAX_COMPLETION_TOKENS = 512
# groq_client.chat()のmax_completion_tokens既定値(4096)と一致させる。ここで
# 明示的に参照するのは、TPM予算計算(下記_trim_history_to_token_budget呼び出し)を
# groq_client.py側の実際の予約量とズレないようにするため。
_MAIN_GENERATION_MAX_COMPLETION_TOKENS = 4096


def _estimate_tokens(text: str) -> int:
    """Groqの正確なトークナイザ計算はせず、日本語混じりのテキストで1トークン
    あたり平均1.5文字程度という経験則に基づく、安全側(多め)の概算を使う。
    実際より少なく見積もって上限を超えるより、多めに見積もって早めに履歴を
    間引く方が安全なため。"""
    return math.ceil(len(text) / 1.5)


def _trim_history_to_token_budget(history: list[dict], budget: int) -> list[dict]:
    """新しい発言を優先して残しつつ、推定トークン数がbudget以下に収まるよう
    履歴を古い方から間引く。budgetが十分大きければ何も削らない。budgetが
    0以下でも、直近1件だけは(文脈が完全に消えるよりはましなため)残す。"""
    kept: list[dict] = []
    total = 0
    for turn in reversed(history):
        turn_tokens = _estimate_tokens(str(turn.get("content") or ""))
        if kept and total + turn_tokens > budget:
            break
        total += turn_tokens
        kept.append(turn)
    kept.reverse()
    return kept


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

    Groq経由(settings.use_groq)・OpenRouter経由(コーディング質問の限定的な
    振り分け先、src/chat/model_router.py参照)の場合は、そもそもthink/keep_aliveの
    概念が無いためこのフォールバック処理自体が不要で、素直にストリーミングするだけでよい。
    """
    if model == settings.openrouter_coding_model and settings.openrouter_api_key:
        yield from openrouter_client.chat(model=model, messages=messages, stream=True)
        return

    if settings.use_groq:
        # Groq無料枠のTPD(1日あたりトークン数)上限はモデルごとに独立したプール
        # なので、1つのモデルが枯渇しても他のモデルはまだ余裕があることが多い。
        # 2026-07-27に1段目→2段目のフォールバックを追加したが、2026-07-28に
        # 2段目(groq_fallback_chat_model)自体も枯渇する実害が出たため3段構成に
        # 拡張。3段目まで全て枯渇した場合は、生のエラーダンプではなく
        # 分かりやすい一言を返して会話だけは終わらせる。
        candidates = [model, settings.groq_fallback_chat_model, settings.groq_second_fallback_chat_model]
        for i, candidate_model in enumerate(candidates):
            try:
                yield from groq_client.chat(
                    model=candidate_model,
                    messages=messages,
                    stream=True,
                    # _MAIN_GENERATION_MAX_COMPLETION_TOKENSと明示的に一致させる
                    # (TPM予算計算で使っている予約量と実際の呼び出しがズレないように)。
                    max_completion_tokens=_MAIN_GENERATION_MAX_COMPLETION_TOKENS,
                )
                return
            except groq.RateLimitError:
                if i == len(candidates) - 1:
                    yield {
                        "message": {
                            "content": (
                                "ごめん、今日使える分のAIの割り当てを使い切っちゃったみたい…💦"
                                "しばらく経ったらまた話しかけてみてね!"
                            )
                        }
                    }
                    return
                continue

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


def _maybe_log_correction_feedback(user_message: str, history: list[dict], user_id: int) -> None:
    """ユーザーの発言が直前の志粋の返答への訂正・不満らしければ、feedback_logに記録し、
    かつ次の会話ターンから即座に参照できるよう新皮質(neocortex)へも直接記録する。

    例外を伴わないバグ・不満(「その答え違うよ」等)はsrc/core/error_log.pyでは
    拾えない(実際にPythonの例外が起きた場合しか記録されないため)。ここで
    キーワードベースに検知し、自己修復プロトコルの追加の材料としてfeedback_logへ
    蓄積する(こちらは人間が後で読むだけで、自動で反映される経路は無い)。

    それとは別に、この訂正内容をneocortexへ"correction"カテゴリで即座に保存する。
    build_recall_context()は毎ターンneocortexを検索するため、翌日の睡眠モードを
    待たずに次の返信から反映される(「決めつけないで」のような訂正を言われた
    直後にまた繰り返す、という事故を防ぐ)。埋め込み1回分のコストで済むため、
    生成そのもの(自己回帰的なLLM呼び出し)より十分軽く、応答の遅延にはほぼ影響しない。
    誤検知は許容する設計(多少無関係な訂正メモリが増えても実害は小さい)。
    ログ自体の失敗で会話を止めないよう例外は握りつぶす。
    """
    try:
        if not feedback_log.looks_like_correction(user_message):
            return

        normalized = _normalize_history(history)
        last_assistant_index = next(
            (i for i in range(len(normalized) - 1, -1, -1) if normalized[i].get("role") == "assistant"),
            None,
        )
        if last_assistant_index is None:
            return
        last_user_index = next(
            (i for i in range(last_assistant_index - 1, -1, -1) if normalized[i].get("role") == "user"),
            None,
        )

        feedback_log.log_feedback(
            previous_user_message=(
                normalized[last_user_index]["content"] if last_user_index is not None else ""
            ),
            previous_assistant_response=normalized[last_assistant_index]["content"],
            correction_message=user_message,
        )

        neocortex.add_memory(
            f"訂正: {user_message}",
            category="correction",
            source_episode_ids=[],
            user_id=user_id,
        )
    except Exception:  # noqa: BLE001
        pass


def _call_tool_ignoring_unknown_kwargs(tool_fn, arguments: dict) -> str:
    """LLMがツールスキーマに無い引数を勝手に付け足すことがある(例: get_weatherに
    スキーマ外の"time"を渡すなど、モデルが指示に無いパラメータを creative に
    補ってしまうケース)。素直に**argumentsで展開すると即TypeErrorでツール
    呼び出し全体が失敗するため、対象関数の実際のシグネチャに無いキーは
    黙って捨てて呼び出す(2026-07-27、本番で実際に起きた事故から追加)。
    """
    accepted = set(inspect.signature(tool_fn).parameters)
    filtered = {k: v for k, v in arguments.items() if k in accepted}
    return tool_fn(**filtered)


def _stream_shisui_events_inner(
    user_message: str, history: list[dict], user_id: int, conversation_id: int
) -> Iterator[ChatEvent]:
    _maybe_log_correction_feedback(user_message, history, user_id)

    # モデルは学習データの時点を「現在」だと錯覚するため(例: 「来期のアニメ」を
    # 学習当時の季節で検索してしまう)、実際の今日の日付を明示的に教える。
    today_str = datetime.now().strftime("%Y年%m月%d日")
    system_content = (
        SHISUI_SYSTEM_PROMPT
        + f"\n\n今日の日付は{today_str}です。「最新」「今期」「来期」「現在」などの"
        "時間に関する言及は、必ずこの日付を基準に判断・検索してください。"
    )

    # 記憶検索(embeddingモデル)×2・モデル振り分け(分類モデル)は互いの結果に
    # 依存せず、かつ異なるOllamaモデルプロセスを使うため、ここでまとめて並列実行
    # する。以前はこの2つのembedding呼び出しが直列で、その後のツール判定との
    # 並列化ブロックに入る前に完了を待つ必要があったため、合計の待ち時間に
    # そのまま乗っていた。
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        recall_future = executor.submit(memory_context.build_recall_context, user_message, user_id=user_id)
        literary_future = executor.submit(literary_context.build_literary_hint, user_message)
        model_future = executor.submit(route_model, user_message)
        emotion_future = executor.submit(emotion.detect_emotion, user_message)
        recall_context = recall_future.result()
        literary_hint = literary_future.result()
        model = model_future.result()
        emotion_category = emotion_future.result()

    if recall_context:
        system_content += "\n\n" + recall_context

    if literary_hint:
        system_content += "\n\n" + literary_hint

    tone_hint = emotion.tone_hint_for(emotion_category)
    if tone_hint:
        system_content += "\n\n" + tone_hint

    unread_study_report = study_report.get_unread_report()
    if unread_study_report:
        system_content += "\n\n" + unread_study_report
        study_report.mark_report_read()

    main_history = _normalize_history(history)[-_MAIN_GENERATION_HISTORY_TURNS:]
    if settings.use_groq:
        reserved = (
            _estimate_tokens(system_content)
            + _estimate_tokens(user_message)
            + _MAIN_GENERATION_MAX_COMPLETION_TOKENS
            + _GROQ_SAFETY_MARGIN_TOKENS
        )
        main_history = _trim_history_to_token_budget(
            main_history, _GROQ_MAIN_GENERATION_TPM_LIMIT - reserved
        )

    messages = [{"role": "system", "content": system_content}]
    messages.extend(main_history)
    messages.append({"role": "user", "content": user_message})

    hippocampus.log_episode(
        role="user",
        content=user_message,
        source="chat",
        user_id=user_id,
        conversation_id=conversation_id,
        emotion=emotion_category,
    )

    # ツール判定は振り分け先の大きいモデル(qwen2.5:32b等)ではなく軽量な分類モデルを使う
    # (応答が全く届かない時間が長引くと、Cloudflareトンネル経由で524タイムアウトになるため)。
    # messagesの構築(=記憶検索の結果)に依存するため、上の並列バッチには含められない。
    #
    # フルのsystem_content(人格プロンプト+記憶検索結果+文学的感性ヒント等)や
    # 会話履歴全体は渡さない。ツール判定に必要なのは直近の文脈と最新の発言だけで、
    # 会話が長くなるほどフルの履歴を渡すと軽量モデルのTPM(1分あたりトークン数)
    # 上限を超えて413(Request too large)になる実害があった(2026-07-28、本番で
    # 実際にlllama-3.1-8b-instantのTPM 6000を超過して発生)。
    tool_history = _normalize_history(history)[-_TOOL_DETECTION_HISTORY_TURNS:]
    if settings.use_groq:
        # ツールスキーマ(ALL_TOOL_SCHEMAS)自体もリクエストのトークン数に加算される
        # が、メッセージ本文ではないため_estimate_tokens()では測れない。ここは
        # 実測せず、安全側のマージンを大きめ(1500)に取って吸収する。
        reserved = (
            _estimate_tokens(TOOL_DETECTION_SYSTEM_PROMPT)
            + _estimate_tokens(user_message)
            + _TOOL_DETECTION_MAX_COMPLETION_TOKENS
            + _GROQ_SAFETY_MARGIN_TOKENS
            + 1500
        )
        tool_history = _trim_history_to_token_budget(
            tool_history, _GROQ_TOOL_DETECTION_TPM_LIMIT - reserved
        )

    tool_messages = [{"role": "system", "content": TOOL_DETECTION_SYSTEM_PROMPT}]
    tool_messages.extend(tool_history)
    tool_messages.append({"role": "user", "content": user_message})

    tool_client = groq_client if settings.use_groq else ollama
    tool_model = settings.groq_classifier_model if settings.use_groq else settings.router_classifier_model
    # ツール判定は関数呼び出しの引数(短いJSON)を返すだけでよく、雑談の返答のような
    # 長さは要らないため、main-generation用の既定(4096)より大きく減らして予約分を
    # 節約する(ollama.chat()にはこの引数が無いためGroq利用時のみ渡す)。
    tool_extra_kwargs = (
        {"max_completion_tokens": _TOOL_DETECTION_MAX_COMPLETION_TOKENS} if settings.use_groq else {}
    )
    try:
        first_response = tool_client.chat(
            model=tool_model,
            messages=tool_messages,
            tools=ALL_TOOL_SCHEMAS,
            **tool_extra_kwargs,
        )
        assistant_message = first_response["message"]
        tool_calls = assistant_message["tool_calls"] if "tool_calls" in assistant_message else None
    except groq.APIStatusError as exc:
        # Groqの一部軽量モデル(llama-3.1-8b-instant等)は、構造化ツール呼び出し
        # ではなく独自の関数呼び出し記法("<function=...>")を出力して400
        # tool_use_failedになることがあり(2026-07-27)、また上記の対策後も
        # なお413(リクエストが大きすぎる)になりうる。ツール検知1回の失敗で
        # 会話全体を落とすのではなく、今回はツール無しとして扱い、通常の
        # 応答生成へフォールバックする(APIStatusErrorはBadRequestError/
        # RateLimitError等の共通基底クラスなので、この種のステータスエラーを
        # まとめて拾える)。
        error_log.log_error(source="tool_detection", exc=exc)
        assistant_message = {"role": "assistant", "content": "", "tool_calls": None}
        tool_calls = None

    if tool_calls:
        messages.append(assistant_message)
        for call in tool_calls:
            tool_name = call["function"]["name"]
            # get_today_news/get_weatherのように全パラメータが省略可能なツールは、
            # モデルが無引数で呼び出した場合argumentsが{}ではなくNoneになることが
            # ある(2026-07-31、本番で実際にAttributeErrorとして発生)。
            arguments = call["function"]["arguments"] or {}
            query = arguments.get("query", "")
            yield ChatEvent(type="tool_status", text=f"🔍 「{query}」について自律検索中...ちょっと待ってね!")

            tool_fn = AVAILABLE_TOOLS.get(tool_name)
            tool_result = _call_tool_ignoring_unknown_kwargs(tool_fn, arguments) if tool_fn else f"未知のツール: {tool_name}"
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
        hippocampus.log_episode(
            role="assistant",
            content=partial_content,
            source="chat",
            user_id=user_id,
            conversation_id=conversation_id,
        )


PROACTIVE_CHECKIN_INSTRUCTION = (
    "\n\n【追加指示】ユーザーはこの会話でここ数分、何も発言していません。あなたから自然に"
    "一言、様子を伺うか会話を続けるメッセージを送ってください。「まだ見てる?」のような"
    "機械的な催促文にはせず、直前のやり取りの内容を踏まえた自然な一言(1〜2文程度)に"
    "すること。相手が忙しい可能性もあるので、催促がましくならないよう軽いトーンで。"
    "同じような文言を毎回繰り返さないこと。"
)


def _call_proactive_checkin_model(messages: list[dict]) -> str:
    model = settings.groq_chat_model if settings.use_groq else settings.ollama_model
    if settings.use_groq:
        response = groq_client.chat(model=model, messages=messages, stream=False)
    else:
        response = ollama.chat(model=model, messages=messages, stream=False)
    return response["message"]["content"].strip()


def generate_proactive_checkin(user_id: int, conversation_id: int) -> str | None:
    """チャット画面を開いたまま数分間発言が無かったユーザーに対し、志粋から自然に
    話しかける一言を生成する。何も生成できなかった場合はNoneを返す(空文字列を
    会話履歴に保存しない・フロントエンドにも空の吹き出しを出させないため)。

    通常のstream_shisui_events()と違い、新しいユーザー発言への応答ではなく、
    志粋側から会話を再開する発話のため、記憶検索・ツール判定・モデルルーティングは
    行わず、直近の会話履歴を踏まえた軽量な1回のLLM呼び出しのみで完結させる
    (フロントエンドが数分おきに定期チェックする性質上、待たせすぎない応答速度を優先)。
    """
    history = conversations.get_messages(conversation_id, user_id)
    # 過去にLLMが空応答を返し、そのまま履歴に保存されてしまった発言(既知の不具合、
    # 現在は保存前に弾いているが過去分が残っている可能性がある)を除外する。
    # 空の発言が履歴に混ざっていると、モデルが「アシスタントは黙ることが多い」
    # という文脈を学習してしまい、空応答が連鎖的に増える悪循環になるため。
    recent_history = [h for h in history if h.get("content", "").strip()][-10:]

    messages = [{"role": "system", "content": SHISUI_SYSTEM_PROMPT + PROACTIVE_CHECKIN_INSTRUCTION}]
    messages.extend(recent_history)

    content = _call_proactive_checkin_model(messages)
    if not content:
        # ローカルLLMがまれに空応答を返すことがある(既知の癖)。1回だけ
        # 取り直してみて、それでも空ならこの回はスキップする。
        content = _call_proactive_checkin_model(messages)
    if not content:
        return None

    hippocampus.log_episode(
        role="assistant",
        content=content,
        source="proactive_checkin",
        user_id=user_id,
        conversation_id=conversation_id,
    )
    return content


def stream_shisui_reply(
    user_message: str, history: list[dict], user_id: int = 1, conversation_id: int = 1
) -> Iterator[str]:
    """Gradio向け(現在は運用から外している。詳細はCLAUDE.md参照): 志粋としての応答を、
    累積HTML文字列として逐次yieldする。

    呼び出しごとに部分的な応答テキストが積み上がった状態でyieldされる
    (Gradio ChatInterfaceの規約に合わせている)。中身はstream_shisui_events()を
    整形しているだけで、Ollamaとの対話ロジック自体は一切重複させない。
    Gradioはユーザーの概念が無い単一ユーザー向けだったため、user_id/conversation_idは
    固定値のデフォルトを持たせている。
    """
    partial_thinking = ""
    partial_content = ""
    for event in stream_shisui_events(user_message, history, user_id, conversation_id):
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
