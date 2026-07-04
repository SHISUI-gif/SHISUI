"""志粋の「進化プロトコル」(自己修復)。

エラーログ(src/core/error_log.py)の未レビュー分を読み、コーディング特化の
ローカルモデルにトレースバックと該当ファイルを読ませて、統一diff形式の
修正案を生成する。

那由多さんと合意した方針:
  - shutil.copyによる手動バックアップではなく、gitのブランチ/コミットで変更を管理する
  - 生成された修正案はoutput/evolution/pending/に保存されるだけで、実際の
    ソースファイルには一切書き込まない
  - 適用は那由多さんが`python app.py evolution apply <id>`で明示的に
    承認した時だけ行う(全自動の自己書き換えにはしない)
"""
from __future__ import annotations

import json
import re
import subprocess
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import ollama

from config.settings import BASE_DIR, PENDING_PATCHES_DIR, settings
from src.core import error_log

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

        response = ollama.chat(
            model=settings.evolution_fix_model,
            messages=[{"role": "user", "content": prompt}],
        )
        explanation, diff = _parse_llm_response(response["message"]["content"])

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


def apply_proposal(proposal_id: str) -> tuple[bool, str]:
    """修正案をgit apply経由で実ファイルに適用する。那由多さんの明示的な承認を経て呼ばれる想定。

    安全のため:
      - 作業ツリーがクリーンでない場合は適用を拒否する(この修正だけの差分だと保証できないため)
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


def reject_proposal(proposal_id: str) -> bool:
    """修正案を却下し、破棄する。"""
    path = PENDING_PATCHES_DIR / f"{proposal_id}.json"
    if not path.exists():
        return False
    path.unlink()
    return True
