"""文学的感性コーパス取り込みパイプライン(src/corpus/ingest.py)をモックで検証する。

実際のネットワークやOllamaサーバーには接続せず、aozora_scraperの各関数と
LLM呼び出し・埋め込みをモック化して、取り込み・冪等性・スキップ処理・
逐語引用ガード・キャッシュのロジックのみを検証する。
"""
import hashlib

import ollama
import pytest

from src.corpus import aozora_scraper, ingest

SAMPLE_TEXT = "これはテスト用の本文サンプルです。" * 50


class FakeLLM:
    def __init__(self, descriptor="静かで内省的な文体。比喩を多用する。"):
        self.descriptor = descriptor
        self.calls = 0

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        self.calls += 1
        return self.descriptor


def _fake_embeddings(model: str, prompt: str) -> dict:
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    return {"embedding": [b / 255.0 for b in digest[:16]]}


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "RAW_CACHE_DIR", tmp_path / "raw_cache")
    monkeypatch.setattr(ingest, "LITERARY_CHROMA_DIR", tmp_path / "literary_chroma")
    monkeypatch.setattr(
        ingest,
        "CURATED_WORKS",
        [{"person_id": "999", "author": "テスト作家", "titles": ["テスト作品一", "テスト作品二"]}],
    )
    monkeypatch.setattr(ollama, "embeddings", _fake_embeddings)
    yield


def _mock_scraper(monkeypatch, *, index=None, body=SAMPLE_TEXT, fetch_calls=None):
    index = index or [
        ("テスト作品一", "https://example.com/cards/999/card1.html"),
        ("テスト作品二", "https://example.com/cards/999/card2.html"),
    ]

    def fake_fetch_author_index(person_id):
        return index

    def fake_resolve_text_url(card_url):
        return "https://example.com/files/1.html"

    def fake_fetch_work_text(url):
        if fetch_calls is not None:
            fetch_calls.append(url)
        return body

    monkeypatch.setattr(aozora_scraper, "fetch_author_index", fake_fetch_author_index)
    monkeypatch.setattr(aozora_scraper, "resolve_text_url", fake_resolve_text_url)
    monkeypatch.setattr(aozora_scraper, "fetch_work_text", fake_fetch_work_text)


def test_run_ingest_creates_entries_for_each_curated_title(monkeypatch):
    _mock_scraper(monkeypatch)
    result = ingest.run_ingest(llm=FakeLLM())

    assert result.succeeded == 2
    assert result.skipped == []
    assert result.failed == []

    hints = ingest.list_all()
    assert len(hints) == 2
    assert {h.title for h in hints} == {"テスト作品一", "テスト作品二"}


def test_run_ingest_is_idempotent_without_force(monkeypatch):
    fetch_calls = []
    _mock_scraper(monkeypatch, fetch_calls=fetch_calls)

    ingest.run_ingest(llm=FakeLLM())
    ingest.run_ingest(llm=FakeLLM())

    assert len(ingest.list_all()) == 2
    assert len(fetch_calls) == 2  # 2回目は既存IDのため再取得されない


def test_run_ingest_force_refetches_and_reembeds(monkeypatch):
    fetch_calls = []
    _mock_scraper(monkeypatch, fetch_calls=fetch_calls)

    ingest.run_ingest(llm=FakeLLM())
    ingest.run_ingest(force=True, llm=FakeLLM())

    assert len(fetch_calls) == 4  # 2作品 x 2回とも再取得される
    assert len(ingest.list_all()) == 2  # 重複はしない(upsert)


def test_run_ingest_skips_title_not_found_in_index(monkeypatch):
    _mock_scraper(monkeypatch, index=[("テスト作品一", "https://example.com/cards/999/card1.html")])
    result = ingest.run_ingest(llm=FakeLLM())

    assert result.succeeded == 1
    assert len(result.skipped) == 1
    assert "テスト作品二" in result.skipped[0]


def test_run_ingest_uses_raw_cache_when_chroma_entry_missing(monkeypatch):
    fetch_calls = []
    _mock_scraper(
        monkeypatch,
        index=[("テスト作品一", "https://example.com/cards/999/card1.html")],
        fetch_calls=fetch_calls,
    )
    monkeypatch.setattr(
        ingest, "CURATED_WORKS", [{"person_id": "999", "author": "テスト作家", "titles": ["テスト作品一"]}]
    )

    class FailingLLM:
        def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
            raise RuntimeError("LLM一時的に失敗")

    result = ingest.run_ingest(llm=FailingLLM())
    assert result.succeeded == 0
    assert len(result.failed) == 1
    assert len(fetch_calls) == 1  # 1回目はネットワーク取得してキャッシュに保存される

    result2 = ingest.run_ingest(llm=FakeLLM())
    assert result2.succeeded == 1
    assert len(fetch_calls) == 1  # 2回目はキャッシュが使われ、再取得されない


def test_verbatim_guard_retries_on_quoted_descriptor(monkeypatch):
    _mock_scraper(monkeypatch)

    class QuotingThenParaphrasingLLM:
        def __init__(self):
            self.calls = 0

        def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
            self.calls += 1
            if self.calls % 2 == 1:
                return SAMPLE_TEXT[:50]  # わざと原文をそのまま引用する
            return "客観的な言い換え表現です。"

    llm = QuotingThenParaphrasingLLM()
    result = ingest.run_ingest(llm=llm)

    assert result.succeeded == 2
    assert llm.calls == 4  # 2作品 x (引用→リトライ)の2回ずつ
    for hint in ingest.list_all():
        assert hint.descriptor not in SAMPLE_TEXT


def test_build_literary_hint_returns_formatted_string(monkeypatch):
    _mock_scraper(monkeypatch)
    ingest.run_ingest(llm=FakeLLM(descriptor="静謐で内省的な文体"))

    from src.corpus.context import build_literary_hint

    hint = build_literary_hint("テスト作品一について教えて")
    assert "静謐で内省的な文体" in hint
    assert "テスト作家" in hint


def test_build_literary_hint_empty_when_no_corpus():
    from src.corpus.context import build_literary_hint

    assert build_literary_hint("何か") == ""
