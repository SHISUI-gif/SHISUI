"""ニュース取得(src/research/news_client.py)を検証する。

実際のCurrents APIには接続せず、requests.getをモック化する。
"""
import types

import pytest

from src.research import news_client


def _fake_response(json_body: dict, status_ok: bool = True):
    class _Resp:
        def raise_for_status(self):
            if not status_ok:
                raise Exception("HTTPエラー")

        def json(self):
            return json_body

    return _Resp()


def test_news_client_requires_api_key(monkeypatch):
    monkeypatch.setattr(news_client, "settings", types.SimpleNamespace(currents_api_key=""))

    with pytest.raises(ValueError):
        news_client.NewsClient()


def test_get_today_headlines_returns_parsed_articles(monkeypatch):
    monkeypatch.setattr(
        news_client.requests,
        "get",
        lambda url, params, timeout: _fake_response(
            {
                "news": [
                    {
                        "title": "テストニュース1",
                        "url": "https://example.com/1",
                        "description": "説明1",
                        "published": "2026-07-05",
                    },
                    {
                        "title": "テストニュース2",
                        "url": "https://example.com/2",
                        "description": "説明2",
                        "published": "2026-07-05",
                    },
                ]
            }
        ),
    )

    client = news_client.NewsClient(api_key="test-key")
    articles = client.get_today_headlines(max_results=5)

    assert len(articles) == 2
    assert articles[0].title == "テストニュース1"
    assert articles[0].url == "https://example.com/1"


def test_get_today_headlines_respects_max_results(monkeypatch):
    monkeypatch.setattr(
        news_client.requests,
        "get",
        lambda url, params, timeout: _fake_response(
            {"news": [{"title": f"ニュース{i}", "url": "", "description": "", "published": ""} for i in range(10)]}
        ),
    )

    client = news_client.NewsClient(api_key="test-key")
    articles = client.get_today_headlines(max_results=3)

    assert len(articles) == 3


def test_format_headlines_for_llm_handles_empty_list():
    assert "見つかりませんでした" not in news_client.format_headlines_for_llm([])
    assert news_client.format_headlines_for_llm([]) == "現在、取得できるニュースはありませんでした。"


def test_format_headlines_for_llm_includes_title_and_url():
    article = news_client.NewsArticle(
        title="テスト見出し", url="https://example.com", description="説明文", published="2026-07-05"
    )
    formatted = news_client.format_headlines_for_llm([article])

    assert "テスト見出し" in formatted
    assert "https://example.com" in formatted
