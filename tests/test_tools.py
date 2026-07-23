"""web_searchツール(src/common/tools.py)を検証する。

Tavily・DuckDuckGoの両方を組み合わせて検索し、どちらか片方が失敗しても
もう片方の結果で応答を続けること、両方失敗した場合のみ「見つからなかった」を
返すこと、同じURLが重複しないことを検証する。"""
from tavily.errors import InvalidAPIKeyError

from src.common import tools


class _FakeResult:
    def __init__(self, title, url, content):
        self.title = title
        self.url = url
        self.content = content


class _FakeClientRaisingOnSearch:
    def __init__(self, *args, **kwargs):
        pass

    def search(self, query, max_results=5):
        raise InvalidAPIKeyError("Unauthorized: missing or invalid API key.")


class _FakeEmptyClient:
    def __init__(self, *args, **kwargs):
        pass

    def search(self, query, max_results=5):
        return []


class _FakeSuccessClient:
    def __init__(self, results):
        self._results = results

    def __call__(self, *args, **kwargs):
        return self

    def search(self, query, max_results=5):
        return self._results


def test_execute_web_search_returns_not_found_when_both_sources_fail(monkeypatch):
    monkeypatch.setattr(tools, "WebSearchClient", lambda: _FakeClientRaisingOnSearch())
    monkeypatch.setattr(tools, "DuckDuckGoSearchClient", _FakeEmptyClient)

    result = tools.execute_web_search("テスト検索")

    assert "見つかりませんでした" in result


def test_execute_web_search_falls_back_to_duckduckgo_when_tavily_key_invalid(monkeypatch):
    """TAVILY_API_KEYが設定されているが無効な場合、例外を外に漏らさず、
    DuckDuckGoの結果だけで応答を続ける(以前はここが素通りしてクラッシュしていた)。"""
    monkeypatch.setattr(tools, "WebSearchClient", lambda: _FakeClientRaisingOnSearch())
    monkeypatch.setattr(
        tools,
        "DuckDuckGoSearchClient",
        _FakeSuccessClient([_FakeResult("DDG結果", "https://ddg.example.com", "内容A")]),
    )

    result = tools.execute_web_search("テスト検索")

    assert "DDG結果" in result
    assert "https://ddg.example.com" in result


def test_execute_web_search_falls_back_to_duckduckgo_when_tavily_key_missing(monkeypatch):
    def raise_value_error():
        raise ValueError("TAVILY_API_KEYが設定されていません。.envファイルを確認してください。")

    monkeypatch.setattr(tools, "WebSearchClient", raise_value_error)
    monkeypatch.setattr(
        tools,
        "DuckDuckGoSearchClient",
        _FakeSuccessClient([_FakeResult("DDG結果", "https://ddg.example.com", "内容A")]),
    )

    result = tools.execute_web_search("テスト検索")

    assert "DDG結果" in result


def test_execute_web_search_combines_both_sources(monkeypatch):
    monkeypatch.setattr(
        tools,
        "WebSearchClient",
        _FakeSuccessClient([_FakeResult("Tavily結果", "https://tavily.example.com", "内容T")]),
    )
    monkeypatch.setattr(
        tools,
        "DuckDuckGoSearchClient",
        _FakeSuccessClient([_FakeResult("DDG結果", "https://ddg.example.com", "内容D")]),
    )

    result = tools.execute_web_search("テスト検索")

    assert "Tavily結果" in result
    assert "DDG結果" in result


def test_execute_web_search_deduplicates_same_url_across_sources(monkeypatch):
    same_url = "https://example.com/article"
    monkeypatch.setattr(
        tools,
        "WebSearchClient",
        _FakeSuccessClient([_FakeResult("タイトルA", same_url, "内容A")]),
    )
    monkeypatch.setattr(
        tools,
        "DuckDuckGoSearchClient",
        _FakeSuccessClient([_FakeResult("タイトルB", same_url, "内容B")]),
    )

    result = tools.execute_web_search("テスト検索")

    assert result.count(same_url) == 1


class _FakeNewsClientRaisingOnInit:
    def __init__(self, *args, **kwargs):
        raise ValueError("CURRENTS_API_KEYが設定されていません。.envファイルを確認してください。")


class _FakeNewsClientRaisingOnFetch:
    def __init__(self, *args, **kwargs):
        pass

    def get_today_headlines(self, category=None, max_results=5):
        raise Exception("APIエラー")


class _FakeNewsClientSuccess:
    def __init__(self, articles):
        self._articles = articles

    def __call__(self, *args, **kwargs):
        return self

    def get_today_headlines(self, category=None, max_results=5):
        return self._articles


def test_execute_get_today_news_reports_missing_api_key(monkeypatch):
    monkeypatch.setattr(tools, "NewsClient", _FakeNewsClientRaisingOnInit)

    result = tools.execute_get_today_news()

    assert "CURRENTS_API_KEY" in result
    assert "取得できませんでした" in result


def test_execute_get_today_news_reports_fetch_failure_honestly(monkeypatch):
    monkeypatch.setattr(tools, "NewsClient", _FakeNewsClientRaisingOnFetch)

    result = tools.execute_get_today_news()

    assert "取得できなかった" in result


def test_execute_get_today_news_returns_formatted_headlines(monkeypatch):
    from src.research.news_client import NewsArticle

    article = NewsArticle(
        title="テストニュース", url="https://example.com", description="説明", published="2026-07-05"
    )
    monkeypatch.setattr(tools, "NewsClient", _FakeNewsClientSuccess([article]))

    result = tools.execute_get_today_news()

    assert "テストニュース" in result
    assert "https://example.com" in result


class _FakeWeatherClientRaising:
    def __init__(self, *args, **kwargs):
        pass

    def get_forecast_for_location(self, location_name=None):
        raise Exception("APIエラー")


class _FakeWeatherClientSuccess:
    def __init__(self, report):
        self._report = report

    def __call__(self, *args, **kwargs):
        return self

    def get_forecast_for_location(self, location_name=None):
        return self._report


def test_execute_get_weather_reports_failure_honestly(monkeypatch):
    monkeypatch.setattr(tools, "WeatherClient", _FakeWeatherClientRaising)

    result = tools.execute_get_weather()

    assert "取得できなかった" in result


def test_execute_get_weather_returns_formatted_report(monkeypatch):
    from src.research.weather_client import WeatherReport

    report = WeatherReport(
        location_name="東京",
        current_temperature=24.5,
        current_humidity=80,
        current_weather="小雨",
        current_wind_speed_kmh=12.0,
        daily_forecasts=[],
    )
    monkeypatch.setattr(tools, "WeatherClient", _FakeWeatherClientSuccess(report))

    result = tools.execute_get_weather()

    assert "東京" in result
    assert "24.5" in result
