"""夜間修行・夜間対話の外部メンターAIクライアント。

GeminiClient: 夜間修行(study_session.py)用。このプロジェクトで唯一、那由多さん
自身の課金が発生する外部連携。呼び出すたびに使用ログを残し、こっそり課金が
発生しないようにする。GEMINI_API_KEYが未設定の場合は明示的にエラーを出し、
黙って動かない。

OpenRouterMentorClient: 夜間対話(external_dialogue.py)用。OpenRouterの無料枠
(:freeモデル)を使うため課金は発生しないが、OPENROUTER_API_KEYが未設定の場合は
同様に明示的にエラーを出す(呼び出し側で事前にスキップ判定する)。
"""
from __future__ import annotations

from datetime import datetime

from google import genai
from google.genai import types

from config.settings import STUDY_LOG_FILE, settings
from src.common import openrouter_client


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


class OpenRouterMentorClient:
    """OpenRouter無料枠の「先輩AI」を、GeminiClientと同じ.ask()引数形で呼び出すラッパー。

    完全無料(:freeモデル)だが1日のリクエスト数上限がGeminiより厳しいため、
    夜間修行(Gemini)とは別枠の対話として使う。OPENROUTER_API_KEY未設定時は
    GeminiClientと同様に明示的にエラーを出し、黙って動かない
    (呼び出し側のrun_external_dialogue_session()がその前段でスキップ判定する)。
    """

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or settings.openrouter_api_key
        if not key:
            raise ValueError(
                "OPENROUTER_API_KEYが設定されていません。先輩AIとの夜間対話には"
                "OpenRouterのAPIキーが必要です。.envファイルを確認してください。"
            )
        self.model = model or settings.openrouter_free_mentor_model
        self._api_key = key

    def ask(self, system_instruction: str, prompt: str, temperature: float = 0.3) -> str:  # noqa: ARG002 - Ollama/Geminiと引数形を揃えるため受け取るが、openrouter_client.chat()は温度指定に非対応
        """先輩AIに1回問い合わせ、応答テキストを返す。"""
        response = openrouter_client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
        )
        return response["message"]["content"].strip()
