"""既存のChromaDBコレクション(新皮質・文学的感性コーパス)を、新しい埋め込み
モデルで再構築する一度きりの移行スクリプト。

埋め込みモデルを切り替える際、既存のベクトルは新しいモデルのベクトル空間とは
別物として扱う必要がある。埋め込みモデルが変わると類似度検索の前提が崩れる
ため、既存の全テキストを新しい埋め込みで登録し直す。

**重要: 先に新しいコレクションを完全に構築・検証してから、古いコレクションを
削除する(delete-then-rebuildではなくbuild-then-swap)。** 以前のバージョンは
「削除→再登録」の順で実装しており、再登録中にAPI側の問題(例: 指定した
埋め込みモデルが実際にはアクセスできず404)で失敗し、新皮質のデータを
実際に失う事故を起こした。二度と同じ事故を起こさないよう、
新しいコレクションの件数が元と一致することを確認できるまでは、古い
コレクションには一切手を付けない設計にしている。

使い方:
    python scripts/migrate_embeddings.py
"""
from __future__ import annotations

import chromadb
from rich.console import Console

from config.settings import LITERARY_CHROMA_DIR, NEOCORTEX_DB_DIR, settings
from src.common.embeddings import OllamaEmbeddingFunction

console = Console()

_TEMP_SUFFIX = "_migrating_tmp"


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

    temp_name = collection_name + _TEMP_SUFFIX
    # 前回の失敗で残った同名の一時コレクションがあれば作り直す
    try:
        client.delete_collection(name=temp_name)
    except Exception:  # noqa: BLE001
        pass

    new_collection = client.get_or_create_collection(
        name=temp_name,
        embedding_function=OllamaEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )

    try:
        batch_size = 20
        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            new_collection.add(
                ids=ids[start:end], documents=documents[start:end], metadatas=metadatas[start:end]
            )
            console.print(f"  {min(end, len(ids))}/{len(ids)}件完了")
    except Exception as e:  # noqa: BLE001
        console.print(
            f"[red]{collection_name}: 新しい埋め込みでの登録に失敗しました。"
            f"元のコレクションは無傷です。エラー: {e}[/red]"
        )
        return

    if new_collection.count() != len(ids):
        console.print(
            f"[red]{collection_name}: 件数不一致(元{len(ids)}件 → 新{new_collection.count()}件)。"
            "元のコレクションは削除せずそのままにします。[/red]"
        )
        return

    # ここまで来て初めて、古いコレクションを削除し、一時コレクションを本来の名前に戻す
    client.delete_collection(name=collection_name)
    new_collection.modify(name=collection_name)
    console.print(f"[green]{collection_name}: 完了({len(ids)}件)[/green]")


def main() -> None:
    mode = "Groq" if settings.use_groq else "Ollama(ローカル)"
    console.print(f"[bold]埋め込み再構築を開始します(移行先: {mode})[/bold]")
    _migrate_collection(NEOCORTEX_DB_DIR, "shisui_neocortex")
    _migrate_collection(LITERARY_CHROMA_DIR, "shisui_literary_corpus")
    console.print("[bold green]完了しました。[/bold green]")


if __name__ == "__main__":
    main()
