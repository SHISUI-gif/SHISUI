"""討論機能の自律実行。

夜間、那由多さんが不在の間に、志粋が自分の弱点トピック(src/study/weakness_finder.py、
夜間修行と共用)について、提案者・批判者・ファシリテーターの3エージェントで自律的に
討論する。夜間修行(src/study/)とは別のlaunchdジョブとして独立してスケジュールされる想定。

ユーザーが不在のため、debate_agent.collect_feedback()のようなCLI入力待ちは一切行わない。
討論結論は新皮質(neocortex)へ通常の記憶として保存し、朝の会話へは夜間修行と同じ
セッションログ・注入の仕組み(src/study/report.py)を共用して伝える。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.common.llm_client import OllamaClient
from src.debate.debate_agent import DebateSystem
from src.memory import neocortex
from src.study import report as study_report
from src.study import weakness_finder

CONCLUSION_SUMMARY_MAX_CHARS = 300


@dataclass
class DebatedTopic:
    topic: str
    conclusion_summary: str
    report_path: str
    memory_id: str


@dataclass
class AutonomousDebateResult:
    topics_debated: list[DebatedTopic] = field(default_factory=list)
    skipped: bool = False


def run_autonomous_debate(llm: OllamaClient | None = None) -> AutonomousDebateResult:
    """弱点トピックについて自律的に討論し、結論を新皮質へ保存する。学ぶべき材料が無ければスキップする。"""
    llm = llm or OllamaClient()

    topics = weakness_finder.find_weak_topics(llm=llm)
    if not topics:
        return AutonomousDebateResult(skipped=True)

    result = AutonomousDebateResult()
    session_topics = []

    for topic in topics:
        system = DebateSystem(llm=llm)
        debate_result = system.run(topic)

        summary = debate_result.conclusion[:CONCLUSION_SUMMARY_MAX_CHARS]
        # 自律討論の結論は特定の友達個人のものではなく志粋自身の成長なので、
        # 共通のSYSTEM_USER_IDに保存する(全ユーザーの会話で参照されうる)
        memory_id = neocortex.add_memory(
            f"討論テーマ「{topic}」の結論: {summary}",
            category="insight",
            source_episode_ids=[],
            user_id=neocortex.SYSTEM_USER_ID,
        )

        debated = DebatedTopic(
            topic=topic,
            conclusion_summary=summary,
            report_path=str(debate_result.report_path),
            memory_id=memory_id,
        )
        result.topics_debated.append(debated)
        session_topics.append({"topic": topic, "insight": summary, "memory_id": memory_id})

    study_report.append_session(session_topics)
    return result
