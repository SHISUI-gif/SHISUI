"""ローカルOllama(Qwen系モデル想定)、またはsettings.use_groq有効時はGroqを
利用するためのLLMクライアント。

自律リサーチ機能・議事録要約・睡眠モード・夜間修行・自律討論・青空文庫クロール
など、単発のsystem/user往復で使うほぼ全ての機能から共通で利用する。
"""
from __future__ import annotations

import groq
import ollama

from config.settings import settings
from src.common import groq_client


class OllamaClient:
    """Ollamaで動作するローカルLLM (例: qwen2.5) を呼び出すクライアント。

    settings.use_groq有効時は、埋め込み専用のOllamaしか無い環境(例: Oracle
    Cloud VM)でも動くようGroq経由に切り替える(2026-07-28、sleep.py等が
    このクライアント経由でローカルの重いモデル(qwen2.5:32b)を直接呼んで
    おり、VM上では常に404で睡眠モード・夜間修行・自律討論が一度も成功して
    いなかった実障害への対処。groq_client.pyの「Ollamaと同じ呼び出し形に
    見せかける」アダプターパターンをここでも踏襲する)。
    呼び出し側が明示的にmodelを渡さない限り、Groq時はsettings.groq_chat_model
    を使う(用途を問わない汎用の1往復チャットのため、既定のチャットモデルが
    最も妥当)。
    """

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self._use_groq = settings.use_groq
        if self._use_groq:
            self.model = model or settings.groq_chat_model
        else:
            self.model = model or settings.ollama_model
            self._client = ollama.Client(host=host or settings.ollama_host)

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        """system/userプロンプトを渡してLLMの応答テキストを取得する。"""
        return self.chat_messages(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )

    def chat_messages(self, messages: list[dict], temperature: float = 0.3) -> str:
        """複数ターンの会話履歴(role/contentのリスト)を渡してLLMの応答テキストを取得する。

        音声会話モジュールのように文脈を保持したまま連続で対話する場合に使う。
        """
        if self._use_groq:
            # Groqアダプターはthink/keep_alive同様temperatureの概念も持たない
            # (既存のGroq呼び出し箇所全てで同様に無視している、この関数固有の
            # 制約ではない)。shisui_chat.py・evolution.pyと同じ3段フォールバック
            # (Groq無料枠のTPD上限はモデルごとに独立したプールのため)。
            candidates = [self.model, settings.groq_fallback_chat_model, settings.groq_second_fallback_chat_model]
            response = None
            for i, candidate_model in enumerate(candidates):
                try:
                    response = groq_client.chat(model=candidate_model, messages=messages)
                    break
                except groq.RateLimitError:
                    if i == len(candidates) - 1:
                        raise
        else:
            response = self._client.chat(
                model=self.model,
                messages=messages,
                options={"temperature": temperature},
            )
        return response["message"]["content"].strip()
