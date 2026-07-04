"""討論グラフ(src/debate/graph.py)のロジックをフェイクLLM・フェイク埋め込みで検証する。

実際のOllamaサーバーには接続せず、ラウンド進行・発言回数・結論生成に加え、
ASAL(Sakana AI)の収束判定を参考にした「新規性が収束したら早期終了する」
ロジックも検証する。
"""
import hashlib

from src.debate.graph import build_debate_graph


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        self.calls += 1
        if "最終結論" in system_prompt:
            return "## 討論の要旨\nテスト結論です。"
        return f"発言{self.calls}"


def _distinct_embedding_fn(texts: list[str]) -> list[list[float]]:
    """入力テキストごとに異なるベクトルを返すフェイク埋め込み(新規性が続くケースの再現)。"""
    vectors = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vectors.append([b / 255.0 for b in digest[:16]])
    return vectors


def _constant_embedding_fn(texts: list[str]) -> list[list[float]]:
    """常に同じベクトルを返すフェイク埋め込み(新規性が収束し続けるケースの再現)。"""
    return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _make_initial_state(max_rounds: int, min_rounds_before_novelty_check: int = 2) -> dict:
    return {
        "topic": "リモートワークは生産性を高めるか",
        "transcript": [],
        "round": 0,
        "max_rounds": max_rounds,
        "feedback_context": "",
        "conclusion": "",
        "round_embeddings": [],
        "min_rounds_before_novelty_check": min_rounds_before_novelty_check,
        "novelty_similarity_threshold": 0.92,
    }


def test_debate_graph_runs_expected_rounds_and_concludes() -> None:
    graph = build_debate_graph(FakeLLM(), embedding_fn=_distinct_embedding_fn)
    final_state = graph.invoke(_make_initial_state(max_rounds=2))

    assert final_state["round"] == 2
    # 2ラウンド x (提案者・批判者・ファシリテーター) = 6発言
    assert len(final_state["transcript"]) == 6
    assert [e["speaker"] for e in final_state["transcript"][:3]] == [
        "提案者",
        "批判者",
        "ファシリテーター",
    ]
    assert final_state["conclusion"]


def test_debate_graph_halts_early_when_novelty_converges() -> None:
    # 常に同じ埋め込みを返す = 議論が新しい論点を生んでいない、という状況を再現
    graph = build_debate_graph(FakeLLM(), embedding_fn=_constant_embedding_fn)
    final_state = graph.invoke(_make_initial_state(max_rounds=5, min_rounds_before_novelty_check=2))

    # max_rounds=5だが、2ラウンド目で新規性収束を検知して早期終了するはず
    assert final_state["round"] == 2
    assert len(final_state["transcript"]) == 6
    assert final_state["conclusion"]


def test_debate_graph_respects_min_rounds_before_novelty_check() -> None:
    # min_rounds=3なら、新規性が無くても最低3ラウンドは続く
    graph = build_debate_graph(FakeLLM(), embedding_fn=_constant_embedding_fn)
    final_state = graph.invoke(_make_initial_state(max_rounds=5, min_rounds_before_novelty_check=3))

    assert final_state["round"] == 3
