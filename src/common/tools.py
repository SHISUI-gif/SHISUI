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

from src.research.web_search import WebSearchClient

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

    Tavily側のエラー(APIキー未設定・無効・利用上限超過など)はここで必ず吸収し、
    会話全体を止めずに「検索は使えなかった」というテキストをLLMに渡すだけに留める。
    以前はWebSearchClient()の初期化時(キー未設定)しか捕捉しておらず、
    キーが「設定されているが無効」な場合(TavilyのInvalidAPIKeyErrorなど)が
    素通りしてチャット全体をクラッシュさせていた。
    """
    try:
        client = WebSearchClient()
    except ValueError as exc:
        return f"検索機能は現在利用できません({exc})"

    try:
        results = client.search(query, max_results=max_results)
    except (
        MissingAPIKeyError,
        InvalidAPIKeyError,
        ForbiddenError,
        BadRequestError,
        UsageLimitExceededError,
        TavilyTimeoutError,
    ) as exc:
        return f"検索機能は現在利用できません({exc})"

    if not results:
        return f"「{query}」に関する検索結果は見つかりませんでした。"

    return "\n\n".join(
        f"[{i + 1}] {r.title}\nURL: {r.url}\n内容: {r.content}"
        for i, r in enumerate(results)
    )


# ツール名 -> 実行関数 のレジストリ。新しいツールを追加する際はここに登録する。
AVAILABLE_TOOLS = {
    "web_search": execute_web_search,
}

ALL_TOOL_SCHEMAS = [WEB_SEARCH_TOOL_SCHEMA]
