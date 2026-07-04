"""志粋が使えるツール(関数呼び出し)の定義。

掟【4】(正確性とハルシネーション対策)にある「システム内の自律検索機能を用いて
最新情報を確認する」を、Ollamaのtool calling機能を通じて実際に実行可能にする。
既存の自律リサーチ機能(src/research/web_search.py)のWeb検索をツールとして再利用する。
"""
from __future__ import annotations

from tavily.errors import (
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    TimeoutError as TavilyTimeoutError,
    UsageLimitExceededError,
)

from src.research.web_search import DuckDuckGoSearchClient, WebSearchClient

WEB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "最新の出来事や、自分の知識だけでは不確実・不正確になりうる事実確認が"
            "必要なときに、Web検索で根拠となる情報を取得する。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索したい内容(日本語または英語のクエリ)",
                },
            },
            "required": ["query"],
        },
    },
}


def execute_web_search(query: str, max_results: int = 5) -> str:
    """web_searchツールコールを実行し、LLMに読ませるテキスト形式の検索結果を返す。

    Tavily(要APIキー)とDuckDuckGo(APIキー不要)の両方から検索して結果を
    合わせる。Tavilyだけだと情報量が乏しいことがあるための補完。どちらか
    片方が失敗しても(キー未設定・無効・利用上限超過・ネットワーク不調など)、
    もう片方の結果だけで応答を続ける(両方失敗した時だけ「検索できなかった」と返す)。
    """
    results = []

    try:
        client = WebSearchClient()
        results.extend(client.search(query, max_results=max_results))
    except ValueError:
        pass  # TAVILY_API_KEY未設定。DuckDuckGoの結果だけで進める
    except (
        MissingAPIKeyError,
        InvalidAPIKeyError,
        ForbiddenError,
        BadRequestError,
        UsageLimitExceededError,
        TavilyTimeoutError,
    ):
        pass

    try:
        results.extend(DuckDuckGoSearchClient().search(query, max_results=max_results))
    except Exception:  # noqa: BLE001
        pass  # DuckDuckGo側の不調(レート制限・ネットワーク等)もTavilyの結果を活かして続行

    if not results:
        return f"「{query}」に関する検索結果は見つかりませんでした(検索機能が利用できないか、該当情報がありませんでした)。"

    # 同じページが両方の検索エンジンでヒットすることがあるため、URLで重複を除く
    seen_urls = set()
    unique_results = []
    for r in results:
        if r.url in seen_urls:
            continue
        seen_urls.add(r.url)
        unique_results.append(r)

    return "\n\n".join(
        f"[{i + 1}] {r.title}\nURL: {r.url}\n内容: {r.content}"
        for i, r in enumerate(unique_results)
    )


# ツール名 -> 実行関数 のレジストリ。新しいツールを追加する際はここに登録する。
AVAILABLE_TOOLS = {
    "web_search": execute_web_search,
}

ALL_TOOL_SCHEMAS = [WEB_SEARCH_TOOL_SCHEMA]
