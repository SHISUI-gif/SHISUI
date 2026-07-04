"""感情トーン検知(src/chat/emotion.py)をモックで検証する。

実際のOllama/Groqサーバーには接続せず、分類結果に応じたヒント選択・無効時の
スキップ・分類失敗時のフェイルオープンのロジックのみを検証する。
"""
import types

import ollama
import pytest

from src.chat import emotion


def _fake_settings(**overrides):
    base = dict(
        emotion_detection_enabled=True,
        router_classifier_model="qwen3:1.7b",
        use_groq=False,
        groq_classifier_model="llama-3.1-8b-instant",
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _fake_chat(category: str):
    def chat(model, messages):
        return {"message": {"content": category}}

    return chat


@pytest.mark.parametrize("category", ["ANXIOUS", "SAD", "FRUSTRATED", "HAPPY", "NEUTRAL"])
def test_detect_emotion_returns_category_for_each_valid_output(monkeypatch, category):
    monkeypatch.setattr(emotion, "settings", _fake_settings())
    monkeypatch.setattr(ollama, "chat", _fake_chat(category))

    assert emotion.detect_emotion("なんかテスト用の発言") == category


def test_detect_emotion_disabled_skips_classification_entirely(monkeypatch):
    monkeypatch.setattr(emotion, "settings", _fake_settings(emotion_detection_enabled=False))

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("無効時はollama.chatが呼ばれてはいけない")

    monkeypatch.setattr(ollama, "chat", _fail_if_called)

    assert emotion.detect_emotion("何か発言") is None


def test_detect_emotion_returns_none_on_classifier_error(monkeypatch):
    monkeypatch.setattr(emotion, "settings", _fake_settings())

    def _raise(*args, **kwargs):
        raise Exception("model 'qwen3:1.7b' not found")

    monkeypatch.setattr(ollama, "chat", _raise)

    assert emotion.detect_emotion("何か発言") is None


def test_detect_emotion_returns_none_for_unrecognized_output(monkeypatch):
    monkeypatch.setattr(emotion, "settings", _fake_settings())
    monkeypatch.setattr(ollama, "chat", _fake_chat("よくわからない返事"))

    assert emotion.detect_emotion("何か発言") is None


def test_detect_emotion_uses_groq_client_and_model_when_use_groq(monkeypatch):
    monkeypatch.setattr(emotion, "settings", _fake_settings(use_groq=True))

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("use_groq有効時はollama.chatが呼ばれてはいけない")

    monkeypatch.setattr(ollama, "chat", _fail_if_called)
    monkeypatch.setattr(emotion.groq_client, "chat", _fake_chat("HAPPY"))

    assert emotion.detect_emotion("やったー!") == "HAPPY"


def test_tone_hint_for_neutral_and_none_return_none():
    assert emotion.tone_hint_for("NEUTRAL") is None
    assert emotion.tone_hint_for(None) is None


@pytest.mark.parametrize("category", ["ANXIOUS", "SAD", "FRUSTRATED", "HAPPY"])
def test_tone_hint_for_each_category_returns_softened_nonempty_text(category):
    hint = emotion.tone_hint_for(category)
    assert hint
    assert "かもしれない" in hint
