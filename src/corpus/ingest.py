"""青空文庫の厳選作品を取り込み、文体・情緒表現のスタイル記述子を生成して
文学的感性コーパス(ChromaDB)へ埋め込むパイプライン。

原文そのものはスタイル記述子の生成にのみ一時的に使い、ベクトルDBには
生成された短い記述子だけを保存する(原文は一切保存・注入しない)。
生成された記述子が原文からの長い逐語引用になっていないかも簡易チェックする。
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

import chromadb

from config.settings import LITERARY_CHROMA_DIR, RAW_CACHE_DIR, settings
from src.common.embeddings import OllamaEmbeddingFunction
from src.common.llm_client import OllamaClient
from src.corpus import aozora_scraper
from src.corpus.curated_list import CURATED_WORKS

COLLECTION_NAME = "shisui_literary_corpus"

STYLE_SYSTEM_PROMPT = (
    "あなたは文体分析の専門家です。与えられた文章の「文体・語彙・リズム・情緒表現の質」だけを"
    "2文以内の日本語で客観的に描写してください。\n"
    "あらすじやテーマには触れないでください。\n"
    "元の文章から一文もそのまま引用してはいけません。必ず自分の言葉で言い換えてください。"
)

SAMPLE_MAX_CHARS = 4000
VERBATIM_GUARD_LENGTH = 20


@dataclass
class IngestResult:
    succeeded: int = 0
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


@dataclass
class LiteraryHint:
    author: str
    title: str
    descriptor: str


def _slugify(text: str) -> str:
    return re.sub(r"[^\w]+", "_", text, flags=re.UNICODE).strip("_")


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def _get_collection():
    client = chromadb.PersistentClient(path=str(LITERARY_CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=OllamaEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def _cache_path(person_id: str, title: str):
    return RAW_CACHE_DIR / f"{person_id}_{_slugify(title)}.json"


def _resolve_card_url(index: list[tuple[str, str]], title: str) -> str | None:
    normalized_target = _normalize(title)

    for candidate_title, url in index:
        if _normalize(candidate_title) == normalized_target:
            return url
    for candidate_title, url in index:
        if normalized_target in _normalize(candidate_title):
            return url
    return None


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = truncated.rfind("。")
    if last_period != -1:
        return truncated[: last_period + 1]
    return truncated


def _fetch_sample_text_by_card_url(
    person_id: str, title: str, card_url: str, force: bool = False
) -> tuple[str, str] | None:
    """card_urlが既に分かっている場合の (サンプル本文, 出典URL) 取得。キャッシュがあれば再取得しない。"""
    cache_path = _cache_path(person_id, title)
    if not force and cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return cached["text"], cached["source_url"]

    text_url = aozora_scraper.resolve_text_url(card_url)
    if text_url is None:
        return None

    body = aozora_scraper.fetch_work_text(text_url)
    if not body:
        return None

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"text": body, "source_url": text_url}, ensure_ascii=False), encoding="utf-8"
    )
    return body, text_url


def _fetch_sample_text(
    index: list[tuple[str, str]], person_id: str, title: str, force: bool = False
) -> tuple[str, str] | None:
    """(サンプル本文, 出典URL) を返す。取得失敗時はNone。キャッシュがあれば再取得しない。"""
    cache_path = _cache_path(person_id, title)
    if not force and cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return cached["text"], cached["source_url"]

    card_url = _resolve_card_url(index, title)
    if card_url is None:
        return None

    return _fetch_sample_text_by_card_url(person_id, title, card_url, force=force)


def _contains_verbatim_excerpt(descriptor: str, source: str) -> bool:
    for i in range(0, max(0, len(descriptor) - VERBATIM_GUARD_LENGTH + 1)):
        chunk = descriptor[i : i + VERBATIM_GUARD_LENGTH]
        if chunk and chunk in source:
            return True
    return False


def _generate_style_descriptor(llm: OllamaClient, sample: str) -> str:
    descriptor = llm.chat(STYLE_SYSTEM_PROMPT, sample)
    if _contains_verbatim_excerpt(descriptor, sample):
        descriptor = llm.chat(
            STYLE_SYSTEM_PROMPT
            + "\n(直前の回答は原文を引用してしまいました。必ず自分の言葉で言い換え直してください。)",
            sample,
        )
    return descriptor


def ingest_one_work(
    collection,
    llm: OllamaClient,
    person_id: str,
    author: str,
    title: str,
    card_url: str,
    force: bool = False,
) -> str:
    """card_urlが既知の1作品を取り込む。"succeeded" / "skipped:<理由>" / "already_exists" を返す。

    src/corpus/full_archive.py(青空文庫全体の段階的取り込み)とrun_ingest()の両方から
    呼ばれる共通ロジック。呼び出し元でChroma書き込み例外を捕捉すること。
    """
    memory_id = f"{person_id}_{_slugify(title)}"

    if not force:
        existing = collection.get(ids=[memory_id])
        if existing["ids"]:
            return "already_exists"

    fetched = _fetch_sample_text_by_card_url(person_id, title, card_url, force=force)
    if fetched is None:
        return "skipped:取得失敗"

    sample, source_url = fetched
    sample = _truncate_at_sentence(sample, SAMPLE_MAX_CHARS)
    if not sample:
        return "skipped:本文抽出失敗"

    descriptor = _generate_style_descriptor(llm, sample)

    collection.upsert(
        ids=[memory_id],
        documents=[descriptor],
        metadatas=[{"author": author, "title": title, "source_url": source_url}],
    )
    return "succeeded"


def run_ingest(force: bool = False, llm: OllamaClient | None = None) -> IngestResult:
    """厳選作品を取り込み、文学的感性コーパスへスタイル記述子を追加する。"""
    llm = llm or OllamaClient()
    collection = _get_collection()
    result = IngestResult()

    for entry in CURATED_WORKS:
        person_id = entry["person_id"]
        author = entry["author"]
        index: list[tuple[str, str]] | None = None  # 著者ページは1エントリにつき最大1回だけ取得する

        for title in entry["titles"]:
            label = f"{author}『{title}』"
            try:
                if index is None:
                    index = aozora_scraper.fetch_author_index(person_id)

                card_url = _resolve_card_url(index, title)
                if card_url is None:
                    result.skipped.append(f"{label}(タイトル未検出)")
                    continue

                status = ingest_one_work(collection, llm, person_id, author, title, card_url, force=force)
                if status == "succeeded":
                    result.succeeded += 1
                elif status == "already_exists":
                    continue
                else:
                    result.skipped.append(f"{label}({status.split(':', 1)[1]})")
            except Exception as exc:  # noqa: BLE001
                result.failed.append(f"{label}({exc})")

    return result


def search(query: str, top_k: int | None = None) -> list[LiteraryHint]:
    """クエリに関連する文体・情緒表現のヒントを検索する。"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    top_k = top_k or settings.literary_hint_top_k
    result = collection.query(query_texts=[query], n_results=min(top_k, collection.count()))
    hints = []
    for i, _ in enumerate(result["ids"][0]):
        metadata = result["metadatas"][0][i]
        hints.append(
            LiteraryHint(
                author=metadata.get("author", ""),
                title=metadata.get("title", ""),
                descriptor=result["documents"][0][i],
            )
        )
    return hints


def list_all() -> list[LiteraryHint]:
    """コーパスに保存されている全スタイル記述子を返す。CLI表示用。"""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    result = collection.get()
    hints = []
    for i, _ in enumerate(result["ids"]):
        metadata = result["metadatas"][i]
        hints.append(
            LiteraryHint(
                author=metadata.get("author", ""),
                title=metadata.get("title", ""),
                descriptor=result["documents"][i],
            )
        )
    return hints
