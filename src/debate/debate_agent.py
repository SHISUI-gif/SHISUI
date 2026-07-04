"""マルチエージェント討論・学習機能のメインロジック。

異なる役割を持つ3つのAIエージェント(提案者・批判者・ファシリテーター)に
テーマについて自律的に討論させ、結論レポートをMarkdownで出力する。
討論後にはユーザーが結論の妥当性と「お手本」の思考の連鎖をフィードバックでき、
その内容はJSONファイルに永続化され、次回以降の討論のコンテキストとして
LLMに読み込ませることで「文脈学習」を行う。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.console import Console

from config.settings import DEBATE_DIR, settings
from src.common.llm_client import OllamaClient
from src.debate import feedback_store
from src.debate.graph import build_debate_graph

console = Console()


@dataclass
class DebateResult:
    topic: str
    transcript: list[dict]
    conclusion: str
    report_path: Path


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE).strip("_")
    return slug[:50] or "debate"


class DebateSystem:
    """3エージェント討論の実行とレポート生成を担当するクラス。"""

    def __init__(
        self,
        llm: OllamaClient | None = None,
        max_rounds: int = 3,
        embedding_fn=None,
    ) -> None:
        self.llm = llm or OllamaClient()
        self.max_rounds = max_rounds
        self.graph = build_debate_graph(self.llm, embedding_fn=embedding_fn)

    def run(self, topic: str) -> DebateResult:
        """テーマについて討論を実行し、レポートを保存して結果を返す。"""
        feedback_context = feedback_store.build_context()
        initial_state = {
            "topic": topic,
            "transcript": [],
            "round": 0,
            "max_rounds": self.max_rounds,
            "feedback_context": feedback_context,
            "conclusion": "",
            "round_embeddings": [],
            "min_rounds_before_novelty_check": settings.debate_min_rounds_before_novelty_check,
            "novelty_similarity_threshold": settings.debate_novelty_similarity_threshold,
        }
        final_state = self.graph.invoke(initial_state)
        report_path = self._save_report(topic, final_state["transcript"], final_state["conclusion"])
        return DebateResult(
            topic=topic,
            transcript=final_state["transcript"],
            conclusion=final_state["conclusion"],
            report_path=report_path,
        )

    def _save_report(self, topic: str, transcript: list[dict], conclusion: str) -> Path:
        transcript_text = "\n\n".join(
            f"**{entry['speaker']}**: {entry['content']}" for entry in transcript
        )
        content = (
            f"# 討論レポート: {topic}\n\n"
            "## 討論の全文\n\n"
            f"{transcript_text}\n\n"
            f"{conclusion}\n"
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = DEBATE_DIR / f"{timestamp}_{_slugify(topic)}.md"
        output_path.write_text(content, encoding="utf-8")
        return output_path


def collect_feedback(topic: str, conclusion: str) -> None:
    """討論結論に対するユーザーフィードバックをCLIで収集し、永続化する。

    「正しい/正しくない」の判定と、正しくない場合は正しい思考の連鎖(お手本)を
    入力してもらい、次回以降の討論のコンテキスト学習に使う。
    """
    console.print("\n[bold]この結論についてフィードバックをお願いします。[/bold]")
    verdict_raw = input("この結論は正しいですか? (y=正しい / n=正しくない / s=スキップ): ").strip().lower()
    if verdict_raw not in ("y", "n"):
        console.print("[yellow]フィードバックの入力をスキップしました。[/yellow]")
        return

    verdict = "correct" if verdict_raw == "y" else "incorrect"
    chain_of_thought = ""
    if verdict == "incorrect":
        chain_of_thought = input(
            "正しい思考の連鎖(お手本)があれば入力してください(空欄でも可): "
        ).strip()

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "topic": topic,
        "conclusion_summary": conclusion[:500],
        "verdict": verdict,
        "user_chain_of_thought": chain_of_thought,
    }
    feedback_store.save_entry(entry)
    console.print("[bold green]フィードバックを保存しました。次回以降の討論に活用されます。[/bold green]")
