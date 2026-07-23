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

from src.research.news_client import NewsClient, format_headlines_for_llm
from src.research.weather_client import WeatherClient, format_weather_for_llm
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


GET_TODAY_NEWS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_today_news",
        "description": (
            "ユーザーに「今日のニュース」「最近の出来事」などを聞かれたときに、"
            "実際の最新ニュースを取得する。このツールを使わずにニュースの中身を"
            "答えることは絶対にしないこと(知識にない出来事を作り話してしまうため)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": (
                        "絞り込みたい分野があれば指定(例: politics_government, "
                        "economy_business_finance, science_technology, sport)。"
                        "指定が無ければ主要なニュース全般を取得する。"
                    ),
                },
            },
            "required": [],
        },
    },
}


def execute_get_today_news(category: str | None = None) -> str:
    """get_today_newsツールコールを実行し、LLMに読ませるテキスト形式のニュース一覧を返す。

    CURRENTS_API_KEY未設定・API側の不調(レート制限・ネットワーク不調等)の場合は、
    その旨を伝える文字列を返す(志粋が「取得できなかった」と正直に言えるようにするため、
    黙って空文字列にはしない)。
    """
    try:
        client = NewsClient()
    except ValueError:
        return "ニュース取得機能(CURRENTS_API_KEY)が設定されていないため、今日のニュースを取得できませんでした。"

    try:
        articles = client.get_today_headlines(category=category)
    except Exception as exc:  # noqa: BLE001
        return f"ニュースの取得に失敗しました({exc})。正直に「取得できなかった」と伝えること。"

    return format_headlines_for_llm(articles)


GET_WEATHER_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "ユーザーに「今日の天気」「明日の天気」などを聞かれたときに、"
            "実際の天気予報を取得する。このツールを使わずに気温・天気・降水確率"
            "などを答えることは絶対にしないこと(知らない数値を作り話してしまうため)。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "地名(例: 東京、大阪)。指定が無ければ既定の地域(東京)の天気を取得する。",
                },
            },
            "required": [],
        },
    },
}


def execute_get_weather(location: str | None = None) -> str:
    """get_weatherツールコールを実行し、LLMに読ませるテキスト形式の天気予報を返す。

    Open-Meteoは無料・APIキー不要のため「未設定」で失敗することは無いが、
    API側の不調(ネットワーク不調・地名が見つからない等)の場合は、その旨を
    伝える文字列を返す(志粋が「取得できなかった」と正直に言えるようにするため)。
    """
    try:
        report = WeatherClient().get_forecast_for_location(location_name=location)
    except Exception as exc:  # noqa: BLE001
        return f"天気の取得に失敗しました({exc})。正直に「取得できなかった」と伝えること。"

    return format_weather_for_llm(report)


# ツール名 -> 実行関数 のレジストリ。新しいツールを追加する際はここに登録する。
AVAILABLE_TOOLS = {
    "web_search": execute_web_search,
    "get_today_news": execute_get_today_news,
    "get_weather": execute_get_weather,
}

ALL_TOOL_SCHEMAS = [WEB_SEARCH_TOOL_SCHEMA, GET_TODAY_NEWS_TOOL_SCHEMA, GET_WEATHER_TOOL_SCHEMA]
