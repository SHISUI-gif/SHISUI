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
