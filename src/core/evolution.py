"""志粋の「進化プロトコル」(自己修復)。

エラーログ(src/core/error_log.py)の未レビュー分を読み、コーディング特化の
モデル(ローカルまたはGroq、use_groq設定に従う)にトレースバックと該当
ファイルを読ませて、統一diff形式の修正案を生成する。

那由多さんと合意した方針(2026-07-27改定):
  - shutil.copyによる手動バックアップではなく、gitのブランチ/コミットで変更を管理する
  - 生成された修正案はoutput/evolution/pending/に保存される
  - `EVOLUTION_AUTO_APPLY=true`(既定)の場合、テストが全件通った修正案のみ
    人間の承認なしで自動適用・自動コミットする(那由多さんの明示的な同意による、
    2026-07-27以前は人間承認が必須だった)。テストが1件でも失敗すれば
    作業ツリーを破棄し、その修正案は適用されない。falseにすれば、
    那由多さんが`python app.py evolution apply <id>`で明示的に承認する
    従来モードに戻せる
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import groq
import ollama

from config.settings import BASE_DIR, PENDING_PATCHES_DIR, settings
from src.common import groq_client
from src.core import activity_log, error_log

FIX_PROMPT_TEMPLATE = """\
以下はPythonアプリケーションで実際に発生したエラーのトレースバックです。
原因を特定し、該当ファイルへの最小限の修正をunified diff形式で提案してください。

## エラー種別
{error_type}: {message}

## トレースバック
{traceback}

## 該当ファイルの内容({file_path})
```python
{file_content}
```

## 出力形式
説明を1-2文書いた後、```diff で始まるunified diff形式のコードブロックのみを出力してください。
diffの中のファイルパスは "{file_path}" を使ってください。
"""


@dataclass
class FixProposal:
    id: str
    error_id: str
    file_path: str
    explanation: str
    diff: str


def _extract_file_from_traceback(tb: str) -> Path | None:
    """トレースバックから、プロジェクト内にある最も内側(最後)のファイルパスを抽出する。"""
    matches = re.findall(r'File "([^"]+)", line \d+', tb)
    for path_str in reversed(matches):
        path = Path(path_str)
        try:
            path.relative_to(BASE_DIR)
        except ValueError:
            continue
        if path.exists() and ".venv" not in path.parts:
            return path
    return None


def _parse_llm_response(response_text: str) -> tuple[str, str]:
    """LLM応答から説明文とdiffコードブロックを分離する。diffが無ければ空文字列を返す。"""
    diff_match = re.search(r"```diff\n(.*?)```", response_text, re.DOTALL)
    if not diff_match:
        return response_text.strip(), ""
    explanation = response_text[: diff_match.start()].strip()
    diff = diff_match.group(1).strip()
    return explanation, diff


def _save_proposal(proposal: FixProposal) -> None:
    path = PENDING_PATCHES_DIR / f"{proposal.id}.json"
    path.write_text(json.dumps(asdict(proposal), ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_fix_text(prompt: str) -> str:
    """修正案の生成呼び出し。use_groq時はローカルにevolution_fix_modelが無い
    環境(例: 埋め込み専用OllamaしかないOracle VM)でも動くようGroqを使う。

    groq_coding_modelがGroq無料枠のTPD(1日あたりトークン)上限に達した場合は、
    shisui_chat.py:_stream_with_think_fallback()と同じく、別プールの
    groq_fallback_chat_modelへ1回だけフォールバックする(2026-07-28、
    自己修復・フィードバック自動反映の生成呼び出しにはこのフォールバックが
    無く、日中の会話でTPDを使い切った直後にNO_DIFFを量産してしまっていた
    ことが実際に発覚した)。"""
    if settings.use_groq:
        try:
            response = groq_client.chat(
                model=settings.groq_coding_model, messages=[{"role": "user", "content": prompt}]
            )
        except groq.RateLimitError:
            response = groq_client.chat(
                model=settings.groq_fallback_chat_model, messages=[{"role": "user", "content": prompt}]
            )
    else:
        response = ollama.chat(
            model=settings.evolution_fix_model, messages=[{"role": "user", "content": prompt}]
        )
    return response["message"]["content"]


def generate_fix_proposals() -> list[FixProposal]:
    """未レビューのエラーそれぞれについて、修正案を生成しpendingとして保存する。

    ファイルが特定できない・LLMがdiffを出力しなかった場合は、修正案を作らずに
    既読化するだけに留める(同じエラーに何度も再挑戦し続けることを防ぐ)。
    """
    if not settings.evolution_enabled:
        return []

    proposals = []
    for error in error_log.get_unreviewed_errors():
        file_path = _extract_file_from_traceback(error["traceback"])
        if file_path is None:
            error_log.mark_reviewed(error["id"])
            continue

        relative_path = file_path.relative_to(BASE_DIR)
        prompt = FIX_PROMPT_TEMPLATE.format(
            error_type=error["error_type"],
            message=error["message"],
            traceback=error["traceback"],
            file_path=relative_path,
            file_content=file_path.read_text(encoding="utf-8"),
        )

        explanation, diff = _parse_llm_response(_generate_fix_text(prompt))

        error_log.mark_reviewed(error["id"])
        if not diff:
            continue

        proposal = FixProposal(
            id=uuid.uuid4().hex[:8],
            error_id=error["id"],
            file_path=str(relative_path),
            explanation=explanation,
            diff=diff,
        )
        _save_proposal(proposal)
        proposals.append(proposal)

    return proposals


def list_pending_proposals() -> list[dict]:
    """承認待ちの修正案を一覧する。"""
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(PENDING_PATCHES_DIR.glob("*.json"))
    ]


def get_proposal(proposal_id: str) -> dict | None:
    path = PENDING_PATCHES_DIR / f"{proposal_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _run_tests() -> tuple[bool, str]:
    """バックエンドのテストスイート全件を実行する。auto_apply_fix_proposals()の最後の安全弁。"""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = (result.stdout + result.stderr)[-2000:]
    return result.returncode == 0, output


def _run_frontend_typecheck() -> tuple[bool, str]:
    """フロントエンド(frontend/以下)の型チェック。pytestはPythonしか検証しない
    ため、frontend/配下のファイルへのパッチにはこちらを安全弁として使う
    (2026-07-27、フィードバック自動反映の対象をフロントエンドにも広げた際に追加)。
    tscは型・構文エラーは検知できるが、CSSの見た目が本当に意図通りかまでは
    検証できない点は依然として同じ限界がある。"""
    result = subprocess.run(
        ["npx", "tsc", "--noEmit"],
        cwd=BASE_DIR / "frontend",
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = (result.stdout + result.stderr)[-2000:]
    return result.returncode == 0, output


def _verify_for(file_path: str) -> tuple[bool, str]:
    """修正対象ファイルの種類に応じて適切な検証コマンドを選ぶ。"""
    if file_path.startswith("frontend/"):
        return _run_frontend_typecheck()
    return _run_tests()


def apply_proposal(proposal_id: str, *, run_tests: bool = False) -> tuple[bool, str]:
    """修正案をgit apply経由で実ファイルに適用する。

    安全のため:
      - 作業ツリーがクリーンでない場合は適用を拒否する(この修正だけの差分だと保証できないため)
      - run_tests=Trueの場合、コミット前に検証を実行し(_verify_for(): 対象が
        frontend/配下ならtsc型チェック、それ以外ならバックエンドのテスト
        スイート全件)、失敗すれば適用前の状態に作業ツリーを戻す(コミット
        しない)。auto_apply_fix_proposals()(人間承認なしの全自動適用)・
        feedback_autopilot.py(フィードバックの自動反映)から呼ばれる際は
        常にTrue。`evolution apply`(那由多さんの手動承認)からはFalseのまま
        (那由多さん自身が検証の要否を判断できるため)
      - 適用に成功したらその場でコミットする(巻き戻しは`git revert`で行える)
    """
    proposal = get_proposal(proposal_id)
    if proposal is None:
        return False, f"修正案 {proposal_id} が見つかりません。"

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=BASE_DIR, capture_output=True, text=True
    )
    if status.stdout.strip():
        return False, "作業ツリーに未コミットの変更があるため、安全のため適用を中止しました。先にコミットかstashしてください。"

    diff_file = PENDING_PATCHES_DIR / f"{proposal_id}.diff"
    diff_file.write_text(proposal["diff"] + "\n", encoding="utf-8")

    try:
        result = subprocess.run(
            ["git", "apply", "--whitespace=fix", str(diff_file)],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, f"パッチの適用に失敗しました:\n{result.stderr}"

        if run_tests:
            try:
                passed, test_output = _verify_for(proposal["file_path"])
            except Exception as exc:  # noqa: BLE001
                # 検証コマンド自体が環境的な理由で失敗すること(例: フロントエンドの
                # 型チェック用にnpx/Node.jsが入っていないバックエンド専用VM)がある。
                # ここで例外を握りつぶさずに素通しすると、git applyだけ成功した
                # 半端な状態(未コミットの変更)が作業ツリーに残ってしまい、次回の
                # 自動適用が軒並み「作業ツリーが汚れている」で失敗し続ける事故になる。
                # 検証コマンドが失敗した場合も「テスト失敗」と同じ扱いで必ず戻す。
                passed, test_output = False, f"検証コマンドの実行自体に失敗しました: {exc}"
            if not passed:
                subprocess.run(
                    ["git", "checkout", "--", "."], cwd=BASE_DIR, capture_output=True, text=True
                )
                # git checkoutは追跡済みファイルの変更しか戻さない。パッチが新規
                # ファイルを作成していた場合、それは未追跡のまま残ってしまい、
                # 次回以降の適用が全て「作業ツリーが汚れている」で失敗し続ける
                # 事故になる(実際に起きた)。関数の先頭でクリーンな状態を確認
                # 済みなので、ここで生まれた未追跡ファイルは全てこのパッチに
                # 由来すると分かっており、git cleanで安全に削除できる。
                subprocess.run(
                    ["git", "clean", "-fd"], cwd=BASE_DIR, capture_output=True, text=True
                )
                return False, f"テストが失敗したため適用を取り消しました:\n{test_output}"

        subprocess.run(
            [
                "git", "commit", "-am",
                f"自己修復: {proposal['file_path']}の修正 (提案ID: {proposal_id})",
            ],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
        )
    finally:
        diff_file.unlink(missing_ok=True)

    (PENDING_PATCHES_DIR / f"{proposal_id}.json").unlink(missing_ok=True)

    return True, f"{proposal['file_path']}に適用し、コミットしました。問題があれば`git revert`で戻せます。"


def auto_apply_fix_proposals() -> list[tuple[FixProposal, bool, str]]:
    """新規に生成された修正案を、テストが全件通ることを条件に人間の承認なしで
    自動適用する(settings.evolution_auto_apply、既定true)。

    結果(適用できたか・できなかったか、どちらも)を`activity_log`に記録し、
    那由多さんがActivityLog UIで後から確認できるようにする——完全自動化の
    引き換えに那由多さんが明示的に求めた可視性。
    """
    if not settings.evolution_auto_apply:
        return []

    results: list[tuple[FixProposal, bool, str]] = []
    for proposal in generate_fix_proposals():
        success, message = apply_proposal(proposal.id, run_tests=True)
        results.append((proposal, success, message))
        activity_log.log_activity(
            kind="self_repair",
            summary=(
                f"✅ {proposal.file_path}を自動修正しました" if success
                else f"⚠️ {proposal.file_path}の修正案はテストに通らず破棄しました"
            ),
            details={
                "proposal_id": proposal.id,
                "file_path": proposal.file_path,
                "explanation": proposal.explanation,
                "applied": success,
                "message": message,
            },
        )
    return results


def reject_proposal(proposal_id: str) -> bool:
    """修正案を却下し、破棄する。"""
    path = PENDING_PATCHES_DIR / f"{proposal_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True
