"""夜間対話(External Dialogue): OpenRouter無料枠の「先輩AI」との夜間対話。

夜間修行(study_session.py、Gemini)・自律討論(autonomous.py)とは別枠の、
3本目の夜間バックグラウンド活動。弱点トピックについて志粋⇔先輩AI(OpenRouter
無料枠モデル)で対話し、得られた気づきを新皮質へ保存する。OPENROUTER_API_KEY
未設定ならこっそり課金しない設計と同じ理由で、明示的にスキップする
(study_session.pyのGemini未設定時と同じ「静かにスキップ」ではなく、
こちらは無料枠なので設定さえあれば常に動く想定)。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from config.settings import settings
from src.common.llm_client import OllamaClient
from src.core import activity_log
from src.memory import neocortex
from src.study import weakness_finder
from src.study.mentor_client import OpenRouterMentorClient

SHISUI_ASK_SYSTEM_PROMPT = (
    "あなたは志粋です。以下のトピックについて、先輩AIに最初に聞くべき、"
    "具体的で答えやすい質問を1つだけ日本語で作成してください。質問文のみを出力してください。"
)

SHISUI_CHALLENGE_SYSTEM_PROMPT = (
    "あなたは志粋です。先輩AIの直前の回答を読み、「なぜそうなるのか」「別の視点はないか」"
    "など、対話を深めるための鋭い追加質問を1つだけ日本語で作成してください。"
    "質問文のみを出力してください。"
)

MENTOR_SYSTEM_PROMPT = (
    "あなたは経験豊富な先輩AIです。質問に対して、具体的で実践的な回答を日本語で簡潔に述べてください。"
)

INSIGHT_SYSTEM_PROMPT = (
    "あなたは志粋です。以下は先輩AIとの対話の記録です。この対話から得られた教訓を、"
    "1〜2文の日本語で、今後の会話に活かせる形に要約してください。"
)


@dataclass
class DialogueTopicResult:
    topic: str
    dialogue: list[dict]
    insight: str
    memory_id: str


@dataclass
class ExternalDialogueResult:
    topics_discussed: list[DialogueTopicResult] = field(default_factory=list)
    skipped: bool = False


def _format_dialogue(dialogue: list[dict]) -> str:
    return "\n".join(f"{turn['role']}: {turn['content']}" for turn in dialogue)


def _discuss_topic(
    topic: str, llm: OllamaClient, mentor: OpenRouterMentorClient, turns: int
) -> DialogueTopicResult:
    dialogue: list[dict] = []
    question = llm.chat(SHISUI_ASK_SYSTEM_PROMPT, f"トピック: {topic}")
    dialogue.append({"role": "志粋", "content": question})

    for i in range(turns):
        answer = mentor.ask(MENTOR_SYSTEM_PROMPT, question)
        dialogue.append({"role": "先輩AI", "content": answer})

        if i == turns - 1:
            break

        question = llm.chat(SHISUI_CHALLENGE_SYSTEM_PROMPT, f"先輩AIの直前の回答:\n{answer}")
        dialogue.append({"role": "志粋", "content": question})

    insight = llm.chat(INSIGHT_SYSTEM_PROMPT, _format_dialogue(dialogue))
    # 夜間対話の気づきは特定の友達個人のものではなく志粋自身の成長なので、
    # 共通のSYSTEM_USER_IDに保存する(夜間修行・自律討論と同じ)
    memory_id = neocortex.add_memory(
        insight, category="insight", source_episode_ids=[], user_id=neocortex.SYSTEM_USER_ID
    )

    return DialogueTopicResult(topic=topic, dialogue=dialogue, insight=insight, memory_id=memory_id)


def run_external_dialogue_session(
    llm: OllamaClient | None = None, mentor: OpenRouterMentorClient | None = None
) -> ExternalDialogueResult:
    """弱点トピックについて先輩AI(OpenRouter無料枠)と対話し、教訓を新皮質へ保存する。

    OPENROUTER_API_KEY未設定、または学ぶべき材料が一つも無ければスキップする。
    """
    if mentor is None and not settings.openrouter_api_key:
        return ExternalDialogueResult(skipped=True)

    llm = llm or OllamaClient(force_local=True)

    topics = weakness_finder.find_weak_topics(llm=llm)
    if not topics:
        return ExternalDialogueResult(skipped=True)

    mentor = mentor or OpenRouterMentorClient()

    result = ExternalDialogueResult()
    for topic in topics:
        topic_result = _discuss_topic(topic, llm, mentor, settings.external_dialogue_turns)
        result.topics_discussed.append(topic_result)

    insight_preview = "、".join(t.insight for t in result.topics_discussed[:3])
    summary = f"夜間対話: {len(result.topics_discussed)}件のトピックについて先輩AIと話した"
    if insight_preview:
        summary += f"(気づき: {insight_preview})"
    activity_log.log_activity(
        kind="external_dialogue",
        summary=summary,
        details={
            "topics": [t.topic for t in result.topics_discussed],
            "insights": [t.insight for t in result.topics_discussed],
            "dialogues": [
                {"topic": t.topic, "dialogue": t.dialogue} for t in result.topics_discussed
            ],
        },
    )
    return result
