"""夜間修行の「弱点分析(Curiosity Generator)」。

海馬(短期記憶)の直近アシスタント発言から「⚠️」(志粋の掟4の不確実性マーカー)を
含むものを抽出し、討論機能のフィードバック履歴から「誤り」と判定された記録も集め、
ローカルLLMに具体的な学習トピックへ要約させる。
"""
from __future__ import annotations

from config.settings import settings
from src.common.llm_client import OllamaClient
from src.debate import feedback_store
from src.memory import hippocampus

WEAKNESS_SYSTEM_PROMPT = (
    "あなたは志粋の「弱点分析」担当です。以下は最近の会話で志粋自身が自信を持てなかった発言と、"
    "過去の討論でユーザーに誤りと指摘された結論の記録です。これらから、今夜メンターAIと"
    "深掘りして学ぶべき具体的なトピックを最大{top_n}個、日本語で1行ずつ挙げてください。\n"
    "説明文や番号付けは不要で、トピック名のみを1行ずつ出力してください。\n"
    "学ぶべき内容が見当たらない場合は何も出力しないでください。"
)


def _collect_uncertain_episodes() -> list[str]:
    episodes = hippocampus.get_unconsolidated_episodes()
    return [e.content for e in episodes if e.role == "assistant" and "⚠️" in e.content]


def _collect_incorrect_feedback() -> list[str]:
    entries = feedback_store.load_all()
    return [
        f"テーマ「{e['topic']}」: {e.get('conclusion_summary', '')}"
        for e in entries
        if e.get("verdict") == "incorrect"
    ]


def find_weak_topics(top_n: int | None = None, llm: OllamaClient | None = None) -> list[str]:
    """最近の不確実な発言・誤った結論から、学ぶべきトピックを抽出する。材料が無ければ空リストを返す。"""
    top_n = top_n or settings.study_weak_topics_count

    uncertain = _collect_uncertain_episodes()
    incorrect = _collect_incorrect_feedback()

    if not uncertain and not incorrect:
        return []

    material_lines = [f"- (不確実な発言) {c}" for c in uncertain]
    material_lines += [f"- (誤りと指摘された結論) {c}" for c in incorrect]

    llm = llm or OllamaClient()
    raw = llm.chat(WEAKNESS_SYSTEM_PROMPT.format(top_n=top_n), "\n".join(material_lines))
    topics = [line.strip("-・ 　") for line in raw.splitlines() if line.strip()]
    return topics[:top_n]
