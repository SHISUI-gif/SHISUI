"""既存のChromaDBコレクション(新皮質・文学的感性コーパス)を、新しい埋め込み
モデルで再構築する一度きりの移行スクリプト。

USE_GROQ=trueに切り替える前に、既存のOllama(nomic-embed-text)で埋め込まれた
ベクトルは、Groq(nomic-embed-text-v1_5)のベクトル空間とは別物として扱う必要が
ある。埋め込みモデルが変わると類似度検索の前提が崩れるため、既存の全テキストを
新しい埋め込みで登録し直す。

実行前に必ず.envのUSE_GROQ・GROQ_API_KEYを目的の値に設定してから実行すること
(このスクリプトは「今のsettings.use_groqの値」を新しい埋め込みとして使う)。

使い方:
    python scripts/migrate_embeddings.py
"""
from __future__ import annotations

import chromadb
from rich.console import Console

from config.settings import LITERARY_CHROMA_DIR, NEOCORTEX_DB_DIR, settings
from src.common.embeddings import OllamaEmbeddingFunction

console = Console()


def _migrate_collection(db_dir, collection_name: str) -> None:
    client = chromadb.PersistentClient(path=str(db_dir))

    try:
        old_collection = client.get_collection(name=collection_name)
    except Exception:  # noqa: BLE001
        console.print(f"[dim]{collection_name}: コレクションが存在しないためスキップ[/dim]")
        return

    existing = old_collection.get()
    ids = existing["ids"]
    documents = existing["documents"]
    metadatas = existing["metadatas"]

    if not ids:
        console.print(f"[dim]{collection_name}: 中身が空のためスキップ[/dim]")
        return

    console.print(f"{collection_name}: {len(ids)}件を新しい埋め込みで再構築します...")

    client.delete_collection(name=collection_name)
    new_collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=OllamaEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    # 大量件数でも一度に追加できるが、Groq無料枠のレート制限を考慮して
    # 念のため小さなバッチに分ける
    batch_size = 20
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        new_collection.add(
            ids=ids[start:end], documents=documents[start:end], metadatas=metadatas[start:end]
        )
        console.print(f"  {min(end, len(ids))}/{len(ids)}件完了")

    console.print(f"[green]{collection_name}: 完了[/green]")


def main() -> None:
    mode = "Groq" if settings.use_groq else "Ollama(ローカル)"
    console.print(f"[bold]埋め込み再構築を開始します(移行先: {mode})[/bold]")
    _migrate_collection(NEOCORTEX_DB_DIR, "shisui_neocortex")
    _migrate_collection(LITERARY_CHROMA_DIR, "shisui_literary_corpus")
    console.print("[bold green]完了しました。[/bold green]")


if __name__ == "__main__":
    main()
