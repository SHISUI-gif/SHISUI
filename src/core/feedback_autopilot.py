"""要望・フィードバック(src/core/user_feedback.py)の自動反映。

那由多さんの明示的な同意(2026-07-27)により、要望・フィードバックが届く
たびにコーディングモデルへ実装を丸ごと委ね、evolution.pyと同じ
テストゲート付き自動適用の仕組み(apply_proposal(run_tests=True))に
乗せて即座に反映する。

**リスクの所在(那由多さんも承知の上で選択)**: バグ修正(evolution.py)は
「既存のテストが通るか」で機械的に検証できるが、要望の実装には「意図通りに
実現できたか」を検証するテストがまだ存在しない。テストスイートが通っても、
それは「既存の挙動を壊していない」ことしか保証せず、「新しい要望を正しく
満たした」ことは保証しない——見当違いの実装がそのまま本番に反映される
リスクは残る。

2026-07-27、対象候補にフロントエンド(frontend/以下)の一部も追加した
(那由多さんの明示的な指示: サラさんの「文字が画面外」というUIフィード
バックを、フロントエンドが対象外だからという理由で見送ったことを受けて)。
frontend/配下への変更はevolution._verify_for()がtsc型チェックへ自動的に
ルーティングする(pytestはPythonしか検証できないため)。tscは型・構文
エラーは検知できるが、CSSの見た目が本当に意図通りかまでは検証できない
点は依然としてバックエンドと同じ限界がある。
"""
from __future__ import annotations

import uuid

from config.settings import BASE_DIR, settings
from src.core import activity_log, evolution, user_feedback

_CANDIDATE_FILES = {
    "src/common/persona.py": "志粋の口調・人格・話し方を定義するシステムプロンプト",
    "src/common/tools.py": "web検索・天気・ニュースなど、志粋が使える自律ツールの説明文と動作",
    "src/chat/model_router.py": "会話内容に応じてどのモデルに振り分けるかの判定基準",
    "src/chat/emotion.py": "ユーザーの発言の感情を検知し、返答トーンに反映する仕組み",
    "src/memory/avatar_catalog.py": "会話テーマに応じたアバター(コーデ)解除の判定基準",
    "src/study/study_session.py": "夜間修行(自律学習)で扱うトピックの選び方",
    "frontend/components/chat/ChatMessage.tsx": "チャット吹き出し(メッセージ1件)の見た目・レイアウト・折り返し",
    "frontend/components/chat/MarkdownContent.tsx": "メッセージ本文のMarkdown描画(改行・折り返し・コードブロック等)",
    "frontend/components/chat/ChatMessages.tsx": "チャット全体のスクロール・並び順・メッセージ一覧のレイアウト",
    "frontend/app/globals.css": "アプリ全体で共有される基本CSS(フォント・色・共通のはみ出し対策等)",
}

FILE_SELECTION_PROMPT = """\
以下は志粋への要望・フィードバックです。このリポジトリの以下のファイルの
うち、この要望を実現するために変更すべき最も適切な1つを選んでください。
どれも適切でない、または複数ファイルにまたがる大きな変更が必要な場合は
"NONE"とだけ答えてください。

## 要望
{content}

## 候補ファイル
{candidates}

出力はファイルパス1つ、または"NONE"のみ。説明は不要です。
"""

FEEDBACK_FIX_PROMPT = """\
以下は志粋への要望・フィードバックです。{file_path}に対して、この要望を
実現する最小限の修正をunified diff形式で提案してください。

## 要望
{content}

## {file_path}の現在の内容
```{lang}
{file_content}
```

## 出力形式
説明を1-2文書いた後、```diff で始まるunified diff形式のコードブロックのみを
出力してください。diffの中のファイルパスは "{file_path}" を使ってください。
"""

_LANG_BY_SUFFIX = {".py": "python", ".tsx": "tsx", ".ts": "typescript", ".css": "css"}


def _select_file(content: str) -> str | None:
    candidates = "\n".join(f"- {path}: {desc}" for path, desc in _CANDIDATE_FILES.items())
    text = evolution._generate_fix_text(
        FILE_SELECTION_PROMPT.format(content=content, candidates=candidates)
    )
    choice = text.strip().splitlines()[0].strip()
    return choice if choice in _CANDIDATE_FILES else None


def process_feedback(feedback_id: str, *, force: bool = False) -> str:
    """1件のフィードバックについて、対象ファイルの選定→diff生成→テストゲート
    付き自動適用までを行う。戻り値は結果を表す短い文字列
    (SKIPPED/AUTO_APPLY_DISABLED/NO_MATCH/NO_DIFF/APPLIED/TEST_FAILED)。

    候補ファイルに当てはまらない・diffが生成できない・テストに落ちた場合は
    人間(那由多さん)のレビュー待ちのまま残す(reviewed=Falseのまま)。

    force=True: 既にreviewed=True(人間が既読/却下済み、または対象拡張前に
    見送られた)のフィードバックでも、那由多さんの明示的な指示で再実行する
    場合に使う(2026-07-27、対象候補にフロントエンドを追加した際、それより
    前にNO_MATCHだった要望を再処理するために追加)。
    """
    feedback = next((f for f in user_feedback.get_all_feedback() if f["id"] == feedback_id), None)
    if feedback is None or (feedback.get("reviewed") and not force):
        return "SKIPPED"
    if not settings.evolution_auto_apply:
        return "AUTO_APPLY_DISABLED"

    content_preview = feedback["content"][:30]
    file_path = _select_file(feedback["content"])
    if file_path is None:
        activity_log.log_activity(
            kind="self_repair",
            summary=f"💭 フィードバック「{content_preview}」は自動実装できる範囲外でした(人間のレビュー待ち)",
            details={"feedback_id": feedback_id},
        )
        return "NO_MATCH"

    file_content = (BASE_DIR / file_path).read_text(encoding="utf-8")
    lang = _LANG_BY_SUFFIX.get(next((s for s in _LANG_BY_SUFFIX if file_path.endswith(s)), ""), "")
    prompt = FEEDBACK_FIX_PROMPT.format(
        content=feedback["content"], file_path=file_path, file_content=file_content, lang=lang
    )
    explanation, diff = evolution._parse_llm_response(evolution._generate_fix_text(prompt))
    if not diff:
        activity_log.log_activity(
            kind="self_repair",
            summary=f"💭 フィードバック「{content_preview}」の実装案を生成できませんでした(人間のレビュー待ち)",
            details={"feedback_id": feedback_id, "file_path": file_path},
        )
        return "NO_DIFF"

    proposal = evolution.FixProposal(
        id=uuid.uuid4().hex[:8],
        error_id=f"feedback:{feedback_id}",
        file_path=file_path,
        explanation=explanation,
        diff=diff,
    )
    evolution._save_proposal(proposal)
    success, message = evolution.apply_proposal(proposal.id, run_tests=True)

    if success:
        user_feedback.mark_applied(feedback_id, proposal.id)

    activity_log.log_activity(
        kind="self_repair",
        summary=(
            f"✅ フィードバック「{content_preview}」を{file_path}に自動反映しました"
            if success
            else f"⚠️ フィードバック「{content_preview}」の実装案はテストに通らず見送りました"
        ),
        details={
            "feedback_id": feedback_id,
            "proposal_id": proposal.id,
            "file_path": file_path,
            "applied": success,
            "message": message,
        },
    )
    return "APPLIED" if success else "TEST_FAILED"
