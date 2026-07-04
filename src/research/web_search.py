"""Tavily Search APIを使ったWeb検索クライアント。"""
from __future__ import annotations

from dataclasses import dataclass

from tavily import TavilyClient

from config.settings import settings


@dataclass
class SearchResult:
    title: str
    url: str
    content: str


class WebSearchClient:
    """Tavily Search APIのラッパー。"""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.tavily_api_key
        if not key:
            raise ValueError(
                "TAVILY_API_KEYが設定されていません。.envファイルを確認してください。"
            )
        self._client = TavilyClient(api_key=key)

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """クエリでWeb検索を行い、上位の結果を返す。"""
        response = self._client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
        )
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", ""),
            )
            for item in response.get("results", [])
        ]
