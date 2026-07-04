"""ローカルLLM(Ollama/Qwen)による議事録要約。"""
from __future__ import annotations

from src.common.llm_client import OllamaClient

SUMMARY_SYSTEM_PROMPT = (
    "あなたは優秀な議事録作成者です。"
    "話者ラベル付きの文字起こしテキストを読み、日本語のMarkdownで議事録をまとめてください。\n"
    "以下の構成に従ってください。\n"
    "## 会議サマリー\n"
    "## 主な議題\n"
    "## 決定事項\n"
    "## ToDo・アクションアイテム(担当者が読み取れる場合は明記)\n"
    "文字起こしに無い情報を推測で書き足さないでください。"
)


class MinutesSummarizer:
    """文字起こし全文から議事録サマリーを生成する。"""

    def __init__(self, llm: OllamaClient | None = None) -> None:
        self.llm = llm or OllamaClient()

    def summarize(self, labeled_transcript: str) -> str:
        return self.llm.chat(SUMMARY_SYSTEM_PROMPT, labeled_transcript)
