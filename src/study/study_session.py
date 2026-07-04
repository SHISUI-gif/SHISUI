"""夜間修行(Autonomous Study Loop)のメインロジック。

弱点分析(weakness_finder) → メンター(Gemini)との深掘り討論 → 教訓の新皮質への統合、
という一連の流れを実行する。志粋の人格・システムプロンプト自体は一切書き換えず、
得られた知見は通常の記憶(neocortex)として保存するだけに留める。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from config.settings import STUDY_SESSIONS_FILE, settings
from src.common.llm_client import OllamaClient
from src.memory import neocortex
from src.study import weakness_finder
from src.study.mentor_client import GeminiClient

SHISUI_ASK_SYSTEM_PROMPT = (
    "あなたは志粋です。以下のトピックについて、外部のメンターAIに最初に聞くべき、"
    "具体的で答えやすい質問を1つだけ日本語で作成してください。質問文のみを出力してください。"
)

SHISUI_CHALLENGE_SYSTEM_PROMPT = (
    "あなたは志粋です。メンターAIの直前の回答を読み、「なぜそうなるのか」「別の視点はないか」"
    "など、議論を深めるための鋭い追加質問を1つだけ日本語で作成してください。"
    "質問文のみを出力してください。"
)

MENTOR_SYSTEM_PROMPT = (
    "あなたは経験豊富なメンターAIです。質問に対して、具体的で実践的な回答を日本語で簡潔に述べてください。"
)

INSIGHT_SYSTEM_PROMPT = (
    "あなたは志粋です。以下はメンターAIとの議論の記録です。この議論から得られた教訓を、"
    "1〜2文の日本語で、今後の会話に活かせる形に要約してください。"
)


@dataclass
class TopicResult:
    topic: str
    dialogue: list[dict]
    insight: str
    memory_id: str


@dataclass
class StudySessionResult:
    topics_studied: list[TopicResult] = field(default_factory=list)
    gemini_calls: int = 0
    skipped: bool = False


def _format_dialogue(dialogue: list[dict]) -> str:
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in dialogue)


def _study_topic(topic: str, llm: OllamaClient, mentor: GeminiClient, turns: int) -> TopicResult:
    dialogue: list[dict] = []
    question = llm.chat(SHISUI_ASK_SYSTEM_PROMPT, f"トピック: {topic}")
    dialogue.append({"role": "志粋", "content": question})

    for i in range(turns):
        answer = mentor.ask(MENTOR_SYSTEM_PROMPT, question)
        dialogue.append({"role": "メンター", "content": answer})

        if i == turns - 1:
            break

        question = llm.chat(SHISUI_CHALLENGE_SYSTEM_PROMPT, f"メンターの直前の回答:\n{answer}")
        dialogue.append({"role": "志粋", "content": question})

    insight = llm.chat(INSIGHT_SYSTEM_PROMPT, _format_dialogue(dialogue))
    memory_id = neocortex.add_memory(insight, category="insight", source_episode_ids=[])

    return TopicResult(topic=topic, dialogue=dialogue, insight=insight, memory_id=memory_id)


def run_study_session(
    llm: OllamaClient | None = None, mentor: GeminiClient | None = None
) -> StudySessionResult:
    """弱点トピックを見つけ、メンターと議論し、教訓を新皮質へ保存する。学ぶべき材料が無ければスキップする。"""
    llm = llm or OllamaClient()

    topics = weakness_finder.find_weak_topics(llm=llm)
    if not topics:
        return StudySessionResult(skipped=True)

    mentor = mentor or GeminiClient()

    result = StudySessionResult()
    for topic in topics:
        topic_result = _study_topic(topic, llm, mentor, settings.study_dialogue_turns)
        result.topics_studied.append(topic_result)
        result.gemini_calls += settings.study_dialogue_turns

    _save_session_log(result)
    return result


def _save_session_log(result: StudySessionResult) -> None:
    sessions = []
    if STUDY_SESSIONS_FILE.exists():
        sessions = json.loads(STUDY_SESSIONS_FILE.read_text(encoding="utf-8"))

    sessions.append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "unread": True,
            "topics": [
                {"topic": t.topic, "insight": t.insight, "memory_id": t.memory_id}
                for t in result.topics_studied
            ],
            "gemini_calls": result.gemini_calls,
        }
    )

    STUDY_SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STUDY_SESSIONS_FILE.write_text(
        json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
