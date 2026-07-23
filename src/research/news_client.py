"""Currents API(無料枠、1日1000リクエスト・クレジットカード不要)を使った
今日のニュース取得クライアント。

src/research/web_search.pyのWebSearchClient/DuckDuckGoSearchClientと同じ
考え方(APIキー未設定・API側の不調を例外で表面化させ、呼び出し側が
静かにスキップできるようにする)を踏襲する。専用のPython SDKは使わず、
シンプルなREST APIなので標準の`requests`で直接叩く。
"""
from __future__ import annotations

from dataclasses import dataclass

import requests

from config.settings import settings

_LATEST_NEWS_URL = "https://api.currentsapi.services/v1/latest-news"


@dataclass
class NewsArticle:
    title: str
    url: str
    description: str
    published: str


class NewsClient:
    """Currents APIのラッパー。"""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.currents_api_key
        if not key:
            raise ValueError(
                "CURRENTS_API_KEYが設定されていません。.envファイルを確認してください。"
            )
        self._api_key = key

    def get_today_headlines(
        self, category: str | None = None, language: str = "ja", max_results: int = 5
    ) -> list[NewsArticle]:
        """今日の主要ニュースを取得する。categoryは省略可(例: "politics_government")。"""
        params: dict = {"apiKey": self._api_key, "language": language}
        if category:
            params["category"] = category

        response = requests.get(_LATEST_NEWS_URL, params=params, timeout=10)
        response.raise_for_status()
        body = response.json()

        articles = [
            NewsArticle(
                title=item.get("title", ""),
                url=item.get("url", ""),
                description=item.get("description", ""),
                published=item.get("published", ""),
            )
            for item in body.get("news", [])
        ]
        return articles[:max_results]


def format_headlines_for_llm(articles: list[NewsArticle]) -> str:
    """ニュース記事一覧を、LLMに読ませるテキスト形式に整形する。"""
    if not articles:
        return "現在、取得できるニュースはありませんでした。"
    return "\n\n".join(
        f"[{i + 1}] {a.title}\n{a.description}\nURL: {a.url}" for i, a in enumerate(articles)
    )
