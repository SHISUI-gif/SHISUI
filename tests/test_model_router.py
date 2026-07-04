"""モデルルーター(src/chat/model_router.py)をモックで検証する。

実際のOllamaサーバーには接続せず、分類結果に応じた振り分け・無効時のフォールバック・
分類失敗時のフォールバックのロジックのみを検証する。settings はfrozen dataclassの
ため、SimpleNamespaceで差し替えてテストする。
"""
import types

import ollama
import pytest

from src.chat import model_router


def _fake_settings(**overrides):
    base = dict(
        model_router_enabled=True,
        router_classifier_model="qwen3:1.5b",
        router_coding_model="qwen3-coder:30b",
        router_reasoning_model="deepseek-r1:8b",
        router_chat_model="qwen3:7b",
        ollama_model="qwen2.5:32b",
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _fake_chat(category: str):
    def chat(model, messages):
        return {"message": {"content": category}}

    return chat


def test_route_model_codes_to_coding_model(monkeypatch):
    monkeypatch.setattr(model_router, "settings", _fake_settings())
    monkeypatch.setattr(ollama, "chat", _fake_chat("CODING"))

    assert model_router.route_model("このUIをTailwindで書き直して") == "qwen3-coder:30b"


def test_route_model_routes_to_reasoning_model(monkeypatch):
    monkeypatch.setattr(model_router, "settings", _fake_settings())
    monkeypatch.setattr(ollama, "chat", _fake_chat("REASONING"))

    assert model_router.route_model("自由意志は存在すると思う?") == "deepseek-r1:8b"


def test_route_model_routes_to_chat_model(monkeypatch):
    monkeypatch.setattr(model_router, "settings", _fake_settings())
    monkeypatch.setattr(ollama, "chat", _fake_chat("CHAT"))

    assert model_router.route_model("おはよう!") == "qwen3:7b"


def test_route_model_disabled_skips_classification_entirely(monkeypatch):
    monkeypatch.setattr(model_router, "settings", _fake_settings(model_router_enabled=False))

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("ルーティング無効時はollama.chatが呼ばれてはいけない")

    monkeypatch.setattr(ollama, "chat", _fail_if_called)

    assert model_router.route_model("何か質問") == "qwen2.5:32b"


def test_route_model_falls_back_on_unexpected_category(monkeypatch):
    monkeypatch.setattr(model_router, "settings", _fake_settings())
    monkeypatch.setattr(ollama, "chat", _fake_chat("よくわからない返事"))

    assert model_router.route_model("何か質問") == "qwen2.5:32b"


def test_route_model_falls_back_when_classifier_model_missing(monkeypatch):
    monkeypatch.setattr(model_router, "settings", _fake_settings())

    def _raise(*args, **kwargs):
        raise Exception("model 'qwen3:1.5b' not found")

    monkeypatch.setattr(ollama, "chat", _raise)

    assert model_router.route_model("何か質問") == "qwen2.5:32b"


def test_route_model_coding_keyword_skips_classification_entirely(monkeypatch):
    """明白にコーディング関連なキーワードがあれば、分類LLM呼び出し(3〜4秒)を
    丸ごと省略して即座にrouter_coding_modelへ振り分ける。"""
    monkeypatch.setattr(model_router, "settings", _fake_settings())

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("キーワードで即決できる場合はollama.chatが呼ばれてはいけない")

    monkeypatch.setattr(ollama, "chat", _fail_if_called)

    assert model_router.route_model("このバグを直して") == "qwen3-coder:30b"
    assert model_router.route_model("認証周りのアーキテクチャを設計して") == "qwen3-coder:30b"
