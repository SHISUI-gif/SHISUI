"""LangGraphによる3エージェント討論のステートグラフ。

提案者 → 批判者 → ファシリテーター、を1ラウンドとして指定ラウンド数だけ巡回させ、
最後にファシリテーターが結論レポートをまとめて終了する。

ラウンドの終了判定は固定回数(max_rounds)だけでなく、Sakana AIのASAL
(embedding空間での新規性の変化を見て収束を判定する、というアイデア)を参考に、
直近ラウンドの発言の埋め込みが前回とほぼ同じ(=議論が新しい論点を生まなくなった)
場合は、max_roundsに達していなくても早期に打ち切る。

    START -> proposer -> critic -> facilitator --(新規性あり・上限未到達)--> proposer (次ラウンド)
    facilitator --(上限到達 or 新規性収束)--> conclude -> END
"""
from __future__ import annotations

import math
from typing import Callable, TypedDict

from langgraph.graph import END, StateGraph

from src.common.embeddings import OllamaEmbeddingFunction
from src.common.llm_client import OllamaClient
from src.debate.agents import (
    CONCLUSION_INSTRUCTION,
    CRITIC_NAME,
    CRITIC_SYSTEM_PROMPT,
    FACILITATOR_NAME,
    FACILITATOR_SYSTEM_PROMPT,
    PROPOSER_NAME,
    PROPOSER_SYSTEM_PROMPT,
)

EmbeddingFn = Callable[[list[str]], list[list[float]]]


class DebateState(TypedDict):
    topic: str
    transcript: list[dict]
    round: int
    max_rounds: int
    feedback_context: str
    conclusion: str
    round_embeddings: list[list[float]]
    min_rounds_before_novelty_check: int
    novelty_similarity_threshold: float


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _format_transcript(transcript: list[dict]) -> str:
    if not transcript:
        return "(まだ発言はありません)"
    return "\n".join(f"{entry['speaker']}: {entry['content']}" for entry in transcript)


def _with_feedback(system_prompt: str, feedback_context: str) -> str:
    if not feedback_context:
        return system_prompt
    return f"{system_prompt}\n\n{feedback_context}"


def _make_speaker_node(speaker_name: str, system_prompt: str, llm: OllamaClient):
    def node(state: DebateState) -> dict:
        user_prompt = (
            f"討論テーマ: {state['topic']}\n\n"
            f"これまでの議論:\n{_format_transcript(state['transcript'])}\n\n"
            f"{speaker_name}として、次の発言を述べてください。"
        )
        content = llm.chat(_with_feedback(system_prompt, state["feedback_context"]), user_prompt)
        entry = {"speaker": speaker_name, "content": content}
        return {"transcript": state["transcript"] + [entry]}

    return node


def _make_facilitator_node(llm: OllamaClient, embedding_fn: EmbeddingFn):
    moderate_node = _make_speaker_node(FACILITATOR_NAME, FACILITATOR_SYSTEM_PROMPT, llm)

    def node(state: DebateState) -> dict:
        result = moderate_node(state)
        result["round"] = state["round"] + 1

        latest_content = result["transcript"][-1]["content"]
        latest_embedding = embedding_fn([latest_content])[0]
        result["round_embeddings"] = state["round_embeddings"] + [latest_embedding]

        return result

    return node


def _make_conclude_node(llm: OllamaClient):
    def node(state: DebateState) -> dict:
        user_prompt = (
            f"討論テーマ: {state['topic']}\n\n"
            f"討論の全文:\n{_format_transcript(state['transcript'])}\n\n"
            "上記を踏まえて結論レポートを作成してください。"
        )
        system_prompt = _with_feedback(CONCLUSION_INSTRUCTION, state["feedback_context"])
        conclusion = llm.chat(system_prompt, user_prompt)
        return {"conclusion": conclusion}

    return node


def _should_continue(state: DebateState) -> str:
    if state["round"] >= state["max_rounds"]:
        return "conclude"

    if state["round"] < state["min_rounds_before_novelty_check"]:
        return "continue"

    embeddings = state["round_embeddings"]
    if len(embeddings) >= 2:
        similarity = _cosine_similarity(embeddings[-1], embeddings[-2])
        if similarity >= state["novelty_similarity_threshold"]:
            # 直近ラウンドが前回とほぼ同じ内容 = 議論が新しい論点を生まなくなった(収束)
            return "conclude"

    return "continue"


def build_debate_graph(llm: OllamaClient, embedding_fn: EmbeddingFn | None = None):
    """討論用のLangGraphを構築し、コンパイル済みグラフを返す。

    embedding_fnは各ラウンドの新規性判定に使う(既定はOllamaEmbeddingFunction、完全ローカル)。
    """
    embedding_fn = embedding_fn or OllamaEmbeddingFunction()
    graph = StateGraph(DebateState)

    graph.add_node("proposer", _make_speaker_node(PROPOSER_NAME, PROPOSER_SYSTEM_PROMPT, llm))
    graph.add_node("critic", _make_speaker_node(CRITIC_NAME, CRITIC_SYSTEM_PROMPT, llm))
    graph.add_node("facilitator", _make_facilitator_node(llm, embedding_fn))
    graph.add_node("conclude", _make_conclude_node(llm))

    graph.set_entry_point("proposer")
    graph.add_edge("proposer", "critic")
    graph.add_edge("critic", "facilitator")
    graph.add_conditional_edges(
        "facilitator", _should_continue, {"continue": "proposer", "conclude": "conclude"}
    )
    graph.add_edge("conclude", END)

    return graph.compile()
