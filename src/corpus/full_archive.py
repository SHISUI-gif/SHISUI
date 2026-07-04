"""青空文庫全体を、睡眠モード中に少しずつ読み進めるチェックポイント式クローラー。

curated_list.py(厳選5作家)とは別に、青空文庫の全作家(2000名以上)を1人ずつ
順番に辿り、1日あたり設定された件数(既定10件)だけ作品を取り込む。
チェックポイントをJSONファイルに保存し、実行のたびに続きから再開する。
本文そのものは保存せず、src/corpus/ingest.pyと同じスタイル記述子生成
パイプラインを再利用する(著作権への配慮は完全に共通)。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from config.settings import AOZORA_ARCHIVE_PROGRESS_FILE, settings
from src.common.llm_client import OllamaClient
from src.corpus import aozora_scraper, ingest


@dataclass
class ArchiveCrawlResult:
    ingested_this_run: int = 0
    total_ingested: int = 0
    current_author: str = ""
    complete: bool = False
    errors: list[str] = field(default_factory=list)


def _load_progress() -> dict:
    if not AOZORA_ARCHIVE_PROGRESS_FILE.exists():
        return {"all_authors": None, "author_cursor": 0, "work_cursor": 0, "total_ingested": 0}
    return json.loads(AOZORA_ARCHIVE_PROGRESS_FILE.read_text(encoding="utf-8"))


def _save_progress(progress: dict) -> None:
    AOZORA_ARCHIVE_PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    AOZORA_ARCHIVE_PROGRESS_FILE.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _ensure_all_authors(progress: dict) -> dict:
    """全作家リストが未取得なら1回だけ取得してプログレスに保存する。"""
    if progress.get("all_authors"):
        return progress
    all_authors = aozora_scraper.fetch_all_authors()
    progress["all_authors"] = [list(pair) for pair in all_authors]
    _save_progress(progress)
    return progress


def run_daily_archive_crawl(
    daily_limit: int | None = None, llm: OllamaClient | None = None
) -> ArchiveCrawlResult:
    """未処理の作家・作品を、1日あたりの上限件数まで取り込む。"""
    llm = llm or OllamaClient()
    daily_limit = daily_limit or settings.aozora_archive_daily_limit

    progress = _load_progress()
    progress = _ensure_all_authors(progress)
    all_authors: list[list[str]] = progress["all_authors"]

    result = ArchiveCrawlResult(total_ingested=progress["total_ingested"])

    if progress["author_cursor"] >= len(all_authors):
        result.complete = True
        return result

    collection = ingest._get_collection()  # noqa: SLF001 (同一パッケージ内での再利用)

    while result.ingested_this_run < daily_limit and progress["author_cursor"] < len(all_authors):
        person_id, author = all_authors[progress["author_cursor"]]
        result.current_author = author

        try:
            works = aozora_scraper.fetch_author_index(person_id)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"{author}(作家ページ取得失敗: {exc})")
            progress["author_cursor"] += 1
            progress["work_cursor"] = 0
            _save_progress(progress)
            continue

        if progress["work_cursor"] >= len(works):
            progress["author_cursor"] += 1
            progress["work_cursor"] = 0
            _save_progress(progress)
            continue

        title, card_url = works[progress["work_cursor"]]
        label = f"{author}『{title}』"

        try:
            status = ingest.ingest_one_work(collection, llm, person_id, author, title, card_url)
            if status == "succeeded":
                result.ingested_this_run += 1
                progress["total_ingested"] += 1
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"{label}({exc})")

        progress["work_cursor"] += 1
        _save_progress(progress)

    result.total_ingested = progress["total_ingested"]
    result.complete = progress["author_cursor"] >= len(all_authors)
    return result


def get_progress_summary() -> dict:
    """現在の進捗状況を人間可読な形で返す。CLI表示用。"""
    progress = _load_progress()
    all_authors = progress.get("all_authors") or []
    return {
        "total_authors": len(all_authors),
        "author_cursor": progress["author_cursor"],
        "total_ingested": progress["total_ingested"],
        "complete": bool(all_authors) and progress["author_cursor"] >= len(all_authors),
    }
