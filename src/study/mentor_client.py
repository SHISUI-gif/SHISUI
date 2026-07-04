"""夜間修行のメンターAI(Gemini API)クライアント。

このプロジェクトで唯一、那由多さん自身の課金が発生する外部連携。
呼び出すたびに使用ログを残し、こっそり課金が発生しないようにする。
GEMINI_API_KEYが未設定の場合は明示的にエラーを出し、黙って動かない。
"""
from __future__ import annotations

from datetime import datetime

from google import genai
from google.genai import types

from config.settings import STUDY_LOG_FILE, settings


class GeminiClient:
    """メンターAI(Gemini)を、OllamaClient.chat()と同じ引数形で呼び出すラッパー。"""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or settings.gemini_api_key
        if not key:
            raise ValueError(
                "GEMINI_API_KEYが設定されていません。夜間修行にはメンターAI(Gemini)の"
                "APIキーが必要です。.envファイルを確認してください。"
            )
        self.model = model or settings.gemini_model
        self._client = genai.Client(api_key=key)

    def ask(self, system_instruction: str, prompt: str, temperature: float = 0.3) -> str:
        """メンターに1回問い合わせ、応答テキストを返す。呼び出しごとに使用ログを残す。"""
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
            ),
        )
        self._log_usage(prompt)
        return response.text

    def _log_usage(self, prompt: str) -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        STUDY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with STUDY_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp}\tmodel={self.model}\tprompt_chars={len(prompt)}\n")
