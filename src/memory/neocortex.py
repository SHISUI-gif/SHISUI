"""新皮質レイヤー: 長期・意味記憶(ChromaDBによるベクトル永続化)。

睡眠モード(src/memory/sleep.py)が圧縮した「好み・決定事項・事実」を保存し、
会話時にはsrc/memory/context.pyがここへ類似度検索をかけて関連記憶を取り出す。
埋め込みはOllamaのembeddings APIをラップした自前EmbeddingFunctionを使うため、
外部クラウドサービスに一切依存しない。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

import chromadb

from config.settings import NEOCORTEX_DB_DIR, settings
from src.common.embeddings import OllamaEmbeddingFunction

COLLECTION_NAME = "shisui_neocortex"


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


def add_memory(text: str, category: str, source_episode_ids: list[int]) -> str:
    """圧縮済みの記憶1件を新皮質へ追加し、生成したメモリIDを返す。"""
    memory_id = str(uuid.uuid4())
    metadata = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "category": category,
        "source_episode_ids": ",".join(str(i) for i in source_episode_ids),
        "superseded": False,
    }
    collection = _get_collection()
    collection.add(ids=[memory_id], documents=[text], metadatas=[metadata])
    return memory_id


def find_most_similar(text: str) -> MemoryMatch | None:
    """テキストに最も類似する既存メモリ(superseded除く)を1件返す。無ければNone。"""
    collection = _get_collection()
    if collection.count() == 0:
        return None
    result = collection.query(
        query_texts=[text], n_results=1, where={"superseded": False}
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


def search(query: str, top_k: int | None = None) -> list[MemoryMatch]:
    """クエリに関連する記憶(superseded除く)を類似度上位から返す。"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    top_k = top_k or settings.memory_recall_top_k
    result = collection.query(
        query_texts=[query], n_results=min(top_k, collection.count()), where={"superseded": False}
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


def list_all() -> list[MemoryMatch]:
    """新皮質に保存されている全メモリ(superseded含む)を返す。CLI表示・デバッグ用。"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    result = collection.get()
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
