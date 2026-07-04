"""青空文庫全体クロール(src/corpus/full_archive.py)をフェイクでチェックポイント進行を検証する。

実際のネットワークやOllamaサーバーには接続せず、aozora_scraperの各関数と
LLM呼び出し・埋め込みをモック化して、チェックポイントの保存・再開・
作家をまたぐカーソル進行・完了判定のロジックのみを検証する。
"""
import hashlib
import json

import ollama
import pytest

from src.corpus import aozora_scraper, full_archive, ingest

FAKE_ALL_AUTHORS = [("100", "作家A"), ("200", "作家B")]

FAKE_AUTHOR_WORKS = {
    "100": [
        ("作品A1", "https://example.com/cards/100/card1.html"),
        ("作品A2", "https://example.com/cards/100/card2.html"),
    ],
    "200": [("作品B1", "https://example.com/cards/200/card1.html")],
}

SAMPLE_TEXT = "これはテスト用の本文サンプルです。" * 50


class FakeLLM:
    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        return "静かで淡々とした文体。"


def _fake_embeddings(model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(full_archive, "AOZORA_ARCHIVE_PROGRESS_FILE", tmp_path / "progress.json")
    monkeypatch.setattr(ingest, "RAW_CACHE_DIR", tmp_path / "raw_cache")
    monkeypatch.setattr(ingest, "LITERARY_CHROMA_DIR", tmp_path / "literary_chroma")
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)

    monkeypatch.setattr(aozora_scraper, "fetch_all_authors", lambda: FAKE_ALL_AUTHORS)
    monkeypatch.setattr(
        aozora_scraper, "fetch_author_index", lambda person_id: FAKE_AUTHOR_WORKS[person_id]
    )
    monkeypatch.setattr(
        aozora_scraper, "resolve_text_url", lambda card_url: "https://example.com/files/x.html"
    )
    monkeypatch.setattr(aozora_scraper, "fetch_work_text", lambda url: SAMPLE_TEXT)
    yield


def test_first_run_ingests_up_to_daily_limit_from_first_author(tmp_path):
    result = full_archive.run_daily_archive_crawl(daily_limit=2, llm=FakeLLM())

    assert result.ingested_this_run == 2
    assert result.total_ingested == 2
    assert result.complete is False

    progress = json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))
    assert progress["author_cursor"] == 0  # まだ作家Aの2作品目まで進んだだけ
    assert progress["work_cursor"] == 2
    assert progress["total_ingested"] == 2

    assert len(ingest.list_all()) == 2


def test_second_run_advances_to_next_author_and_completes(tmp_path):
    full_archive.run_daily_archive_crawl(daily_limit=2, llm=FakeLLM())
    result = full_archive.run_daily_archive_crawl(daily_limit=2, llm=FakeLLM())

    assert result.ingested_this_run == 1  # 作家Bの1作品のみ(それで全作家が尽きる)
    assert result.total_ingested == 3
    assert result.complete is True

    assert len(ingest.list_all()) == 3


def test_third_run_after_completion_is_a_noop(tmp_path):
    full_archive.run_daily_archive_crawl(daily_limit=2, llm=FakeLLM())
    full_archive.run_daily_archive_crawl(daily_limit=2, llm=FakeLLM())
    result = full_archive.run_daily_archive_crawl(daily_limit=2, llm=FakeLLM())

    assert result.ingested_this_run == 0
    assert result.complete is True
    assert result.total_ingested == 3


def test_get_progress_summary_reflects_state():
    full_archive.run_daily_archive_crawl(daily_limit=2, llm=FakeLLM())

    summary = full_archive.get_progress_summary()
    assert summary["total_authors"] == 2
    assert summary["total_ingested"] == 2
    assert summary["complete"] is False


def test_get_progress_summary_before_any_run():
    summary = full_archive.get_progress_summary()
    assert summary["total_authors"] == 0
    assert summary["complete"] is False
