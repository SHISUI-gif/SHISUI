"""web_searchツール(src/common/tools.py)が、Tavily側のエラーで
チャット全体をクラッシュさせないことを検証する。"""
from tavily.errors import InvalidAPIKeyError

from src.common import tools


class _FakeClientRaisingOnSearch:
    def __init__(self, *args, **kwargs):
        pass

    def search(self, query, max_results=5):
        raise InvalidAPIKeyError("Unauthorized: missing or invalid API key.")


def test_execute_web_search_handles_invalid_api_key_gracefully(monkeypatch):
    """TAVILY_API_KEYが設定されているが無効な場合、例外を外に漏らさず
    案内メッセージを返す(以前はここが素通りしてstream_shisui_eventsごと落ちていた)。"""
    monkeypatch.setattr(tools, "WebSearchClient", lambda: _FakeClientRaisingOnSearch())

    result = tools.execute_web_search("テスト検索")

    assert "検索機能は現在利用できません" in result


def test_execute_web_search_handles_missing_api_key(monkeypatch):
    def raise_value_error():
        raise ValueError("TAVILY_API_KEYが設定されていません。.envファイルを確認してください。")

    monkeypatch.setattr(tools, "WebSearchClient", raise_value_error)

    result = tools.execute_web_search("テスト検索")

    assert "検索機能は現在利用できません" in result


def test_execute_web_search_returns_results_on_success(monkeypatch):
    class _FakeResult:
        def __init__(self, title, url, content):
            self.title = title
            self.url = url
            self.content = content

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, query, max_results=5):
            return [_FakeResult("タイトル", "https://example.com", "内容")]

    monkeypatch.setattr(tools, "WebSearchClient", lambda: _FakeClient())

    result = tools.execute_web_search("テスト検索")

    assert "タイトル" in result
    assert "https://example.com" in result
