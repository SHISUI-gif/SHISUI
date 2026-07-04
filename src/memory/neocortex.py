"""新皮質レイヤー: 長期・意味記憶(ChromaDBによるベクトル永続化)。

睡眠モード(src/memory/sleep.py)が圧縮した「好み・決定事項・事実」を保存し、
会話時にはsrc/memory/context.pyがここへ類似度検索をかけて関連記憶を取り出す。
埋め込みはOllamaのembeddings APIをラップした自前EmbeddingFunctionを使うため、
外部クラウドサービスに一切依存しない。

友達それぞれの記憶を混ぜない/覗き見しないため、全ての書き込み・検索は
user_idをmetadataに持たせて絞り込む(1つの共有コレクションを、metadataで
論理的に区画分けする設計。ユーザーごとに別ディレクトリ・別コレクションには
していない)。list_all()だけはCLIでのデバッグ表示用途のため、user_id省略時は
全ユーザー分を返す。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

import chromadb

from config.settings import NEOCORTEX_DB_DIR, settings
from src.common.embeddings import OllamaEmbeddingFunction

COLLECTION_NAME = "shisui_neocortex"

# 夜間修行・自律討論の気づきは特定の友達個人のものではなく、志粋自身の成長として
# 全ユーザー共通で扱うための予約user_id(実在のアカウントとは重複しない0を使う)
SYSTEM_USER_ID = 0


@dataclass
class MemoryMatch:
    id: str
    text: str
    category: str
    timestamp: str
    similarity: float


def _get_collection():
    client = chromadb.PersistentClient(path=str(NEOCORTEX_DB_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=OllamaEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def _not_superseded_filter(user_id: int) -> dict:
    return {"$and": [{"superseded": False}, {"user_id": user_id}]}


def add_memory(text: str, category: str, source_episode_ids: list[int], user_id: int) -> str:
    """圧縮済みの記憶1件を新皮質へ追加し、生成したメモリIDを返す。"""
    memory_id = str(uuid.uuid4())
    metadata = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "category": category,
        "source_episode_ids": ",".join(str(i) for i in source_episode_ids),
        "superseded": False,
        "user_id": user_id,
    }
    collection = _get_collection()
    collection.add(ids=[memory_id], documents=[text], metadatas=[metadata])
    return memory_id


def find_most_similar(text: str, user_id: int) -> MemoryMatch | None:
    """同じユーザーの既存メモリの中で、テキストに最も類似する1件(superseded除く)を返す。"""
    collection = _get_collection()
    if collection.count() == 0:
        return None
    result = collection.query(
        query_texts=[text], n_results=1, where=_not_superseded_filter(user_id)
    )
    ids = result.get("ids", [[]])[0]
    if not ids:
        return None
    distance = result["distances"][0][0]
    metadata = result["metadatas"][0][0]
    return MemoryMatch(
        id=ids[0],
        text=result["documents"][0][0],
        category=metadata.get("category", ""),
        timestamp=metadata.get("timestamp", ""),
        similarity=1.0 - distance,
    )


def mark_superseded(memory_id: str) -> None:
    """指定したメモリをsuperseded(置き換え済み)としてマークする。"""
    collection = _get_collection()
    collection.update(ids=[memory_id], metadatas=[{"superseded": True}])


def search(query: str, user_id: int, top_k: int | None = None) -> list[MemoryMatch]:
    """同じユーザーの記憶の中から、クエリに関連するもの(superseded除く)を類似度上位から返す。"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    top_k = top_k or settings.memory_recall_top_k
    result = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        where=_not_superseded_filter(user_id),
    )
    matches = []
    ids = result.get("ids", [[]])[0]
    for i, memory_id in enumerate(ids):
        metadata = result["metadatas"][0][i]
        matches.append(
            MemoryMatch(
                id=memory_id,
                text=result["documents"][0][i],
                category=metadata.get("category", ""),
                timestamp=metadata.get("timestamp", ""),
                similarity=1.0 - result["distances"][0][i],
            )
        )
    return matches


def list_all(user_id: int | None = None) -> list[MemoryMatch]:
    """新皮質に保存されている全メモリ(superseded含む)を返す。CLI表示・デバッグ用。

    user_id省略時は全ユーザー分を返す(那由多さんが手元で`python app.py memory list`する
    ための管理者向けの挙動で、Web側の会話フローからは必ずuser_idを指定して呼ぶこと)。
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []
    result = collection.get(where={"user_id": user_id} if user_id is not None else None)
    matches = []
    for i, memory_id in enumerate(result["ids"]):
        metadata = result["metadatas"][i]
        label = "[superseded] " if metadata.get("superseded") else ""
        matches.append(
            MemoryMatch(
                id=memory_id,
                text=f"{label}{result['documents'][i]}",
                category=metadata.get("category", ""),
                timestamp=metadata.get("timestamp", ""),
                similarity=1.0,
            )
        )
    return matches
