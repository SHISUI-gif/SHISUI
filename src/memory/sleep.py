"""睡眠モード: 海馬(短期記憶)の生ログを新皮質(長期記憶)へ圧縮する処理。

Macがアイドル状態の時や一日の終わりを想定したタイミングで実行され(実際のトリガーは
src/memory/scheduler.pyが担う)、Qwen2.5に未統合の会話ログを読ませて
「好み・決定事項・事実」だけを抽出させる。抽出結果は新皮質へ追加し、
既存の類似記憶があればsupersededとしてマークすることで、記憶が矛盾したまま
無限に増え続けるのを防ぐ。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from config.settings import settings
from src.common.llm_client import OllamaClient
from src.memory import hippocampus, neocortex

SLEEP_SYSTEM_PROMPT = (
    "あなたは志粋の「睡眠モード」です。日々の生の会話ログを読み込み、"
    "今後の会話で覚えておくべき「好み(preference)」「決定事項(decision)」"
    "「事実(fact)」だけを抽出し、圧縮された記憶として書き出してください。\n"
    "些細な雑談や一時的なやり取りは無視してください。\n"
    "出力は必ず次のJSON配列形式のみとし、説明文やMarkdown装飾は付けないでください。\n"
    '[{"category": "preference|decision|fact", "text": "圧縮された記憶の内容(一文)"}]\n'
    "抽出すべき内容が無い場合は空配列 [] を返してください。"
)


@dataclass
class SleepCycleResult:
    episodes_considered: int
    memories_added: int
    memories_superseded: int
    raw_extractions: list[dict] = field(default_factory=list)


def _extract_json_array(raw_text: str) -> list[dict]:
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        return []
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def run_sleep_cycle(llm: OllamaClient | None = None) -> SleepCycleResult:
    """未統合の海馬エピソードを、ユーザーごとに分けて新皮質へ圧縮し、海馬側を整理する。

    友達それぞれの会話が互いの記憶に混ざらないよう、user_idでグループ化してから
    ユーザーごとに別のトランスクリプトとして圧縮する。user_idが無いエピソード
    (voicechat等、Web版のユーザー概念導入より前からある単一ユーザー向け機能)は
    圧縮対象から外す(誰の長期記憶として保存すべきか特定できないため)。
    """
    llm = llm or OllamaClient()
    episodes = hippocampus.get_unconsolidated_episodes()
    if not episodes:
        return SleepCycleResult(episodes_considered=0, memories_added=0, memories_superseded=0)

    episodes_by_user: dict[int, list] = {}
    for episode in episodes:
        if episode.user_id is None:
            continue
        episodes_by_user.setdefault(episode.user_id, []).append(episode)

    memories_added = 0
    memories_superseded = 0
    all_extractions: list[dict] = []

    for user_id, user_episodes in episodes_by_user.items():
        transcript = "\n".join(
            f"[{e.timestamp}] {e.role}({e.source}): {e.content}" for e in user_episodes
        )
        raw_response = llm.chat(SLEEP_SYSTEM_PROMPT, transcript)
        extractions = _extract_json_array(raw_response)
        all_extractions.extend(extractions)

        episode_ids = [e.id for e in user_episodes]
        for item in extractions:
            text = (item.get("text") or "").strip()
            category = (item.get("category") or "fact").strip()
            if not text:
                continue

            existing = neocortex.find_most_similar(text, user_id=user_id)
            if existing and existing.similarity >= settings.memory_similarity_threshold:
                neocortex.mark_superseded(existing.id)
                memories_superseded += 1

            neocortex.add_memory(text, category, episode_ids, user_id=user_id)
            memories_added += 1

    all_episode_ids = [e.id for e in episodes]
    hippocampus.mark_consolidated(all_episode_ids)
    hippocampus.prune_old_episodes(settings.memory_retention_days)

    return SleepCycleResult(
        episodes_considered=len(episodes),
        memories_added=memories_added,
        memories_superseded=memories_superseded,
        raw_extractions=all_extractions,
    )
