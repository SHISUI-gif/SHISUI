"""ローカルOllama(Qwen系モデル想定)を利用するためのLLMクライアント。

自律リサーチ機能と議事録要約機能の両方から共通で利用する。
"""
from __future__ import annotations

import ollama

from config.settings import settings


class OllamaClient:
    """Ollamaで動作するローカルLLM (例: qwen2.5) を呼び出すクライアント。"""

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
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
        response = self._client.chat(
            model=self.model,
            messages=messages,
            options={"temperature": temperature},
        )
        return response["message"]["content"].strip()
