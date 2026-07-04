"""ユーザーフィードバックの永続化ストア(JSONファイルベース)。

討論結論に対するユーザーの「正しい/正しくない」判定と、
正しい思考の連鎖(お手本)を蓄積し、次回以降の討論で
AIエージェントに読み込ませる「文脈学習」の材料として提供する。
"""
from __future__ import annotations

import json

from config.settings import FEEDBACK_FILE, settings


def load_all() -> list[dict]:
    """保存済みの全フィードバックを新しい順ではなく記録順のまま返す。"""
    if not FEEDBACK_FILE.exists():
        return []
    return json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))


def save_entry(entry: dict) -> None:
    """フィードバック1件を追記保存する。"""
    entries = load_all()
    entries.append(entry)
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK_FILE.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_context(limit: int | None = None) -> str:
    """直近のフィードバックを、討論エージェントに読み込ませるテキストに整形する。

    「正しい」と評価された結論は良い手本として、
    「正しくない」と評価された結論はユーザーが示したお手本の思考の連鎖とともに
    反面教師として、次回の討論プロンプトに注入する。
    """
    limit = limit or settings.debate_feedback_context_limit
    entries = load_all()[-limit:]
    if not entries:
        return ""

    lines = ["過去のユーザーフィードバック(今回の討論の質を高めるために必ず参考にすること):"]
    for entry in entries:
        if entry.get("verdict") == "correct":
            lines.append(
                f"- テーマ「{entry['topic']}」の討論結論はユーザーに正しいと評価された。"
                "同様の水準・方向性の結論を目指すこと。"
            )
        else:
            lines.append(
                f"- テーマ「{entry['topic']}」の討論結論はユーザーに誤りと指摘された。"
            )
            model_reasoning = entry.get("user_chain_of_thought")
            if model_reasoning:
                lines.append(
                    f"  ユーザーが提示した正しい思考の連鎖(お手本): {model_reasoning}"
                )
    return "\n".join(lines)
