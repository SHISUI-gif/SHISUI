"""自律リサーチ機能のメインロジック。

Tavily検索 + ローカルLLM(Ollama/Qwen)を組み合わせ、
Gensparkのようにテーマを自動で深掘り調査し、A4サイズ1枚相当のMarkdownレポートを生成する。

処理フロー:
  1. LLMがテーマを3〜5個の調査観点(サブクエリ)に分解する
  2. 各サブクエリについてTavilyでWeb検索を行い、情報源を収集する
  3. 収集した情報源をもとに、LLMがA4 1枚に収まる分量のMarkdownレポートを執筆する
  4. output/reports/ 配下にMarkdownファイルとして保存する
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from config.settings import REPORTS_DIR
from src.common.llm_client import OllamaClient
from src.research.web_search import SearchResult, WebSearchClient

DECOMPOSE_SYSTEM_PROMPT = (
    "あなたは優秀なリサーチアシスタントです。"
    "与えられたテーマを深く調査するための検索クエリを3〜5個、日本語で考えてください。"
    "出力は1行につき1クエリのみとし、番号や記号、説明文は付けないでください。"
)

REPORT_SYSTEM_PROMPT = (
    "あなたはプロのリサーチアナリストです。"
    "与えられた情報源だけを根拠に、日本語でA4用紙1枚(目安として1500〜2000文字程度)に"
    "収まる調査レポートをMarkdown形式で執筆してください。\n"
    "レポートは次の構成に従ってください。\n"
    "# {テーマ}\n"
    "## 概要\n"
    "## 主要なポイント (箇条書き3〜6項目)\n"
    "## 詳細解説\n"
    "## 出典\n"
    "出典セクションには使用した情報源のタイトルとURLを列挙してください。"
    "情報源に無い内容を推測で書き足さないでください。"
)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE).strip("_")
    return slug[:50] or "report"


class ResearchAgent:
    """テーマ入力から検索・要約・レポート生成までを自律的に行うエージェント。"""

    def __init__(self, llm: OllamaClient | None = None, search: WebSearchClient | None = None) -> None:
        self.llm = llm or OllamaClient()
        self.search = search or WebSearchClient()

    def _decompose_topic(self, topic: str) -> list[str]:
        raw = self.llm.chat(DECOMPOSE_SYSTEM_PROMPT, f"テーマ: {topic}")
        queries = [line.strip("-・ 　") for line in raw.splitlines() if line.strip()]
        return queries or [topic]

    def _collect_sources(self, queries: list[str], max_results_per_query: int) -> list[SearchResult]:
        sources: list[SearchResult] = []
        seen_urls: set[str] = set()
        for query in queries:
            for result in self.search.search(query, max_results=max_results_per_query):
                if result.url in seen_urls:
                    continue
                seen_urls.add(result.url)
                sources.append(result)
        return sources

    def _write_report(self, topic: str, sources: list[SearchResult]) -> str:
        sources_text = "\n\n".join(
            f"[{i + 1}] {s.title}\nURL: {s.url}\n内容: {s.content}"
            for i, s in enumerate(sources)
        )
        user_prompt = f"テーマ: {topic}\n\n以下は収集した情報源です。\n\n{sources_text}"
        return self.llm.chat(REPORT_SYSTEM_PROMPT, user_prompt)

    def run(self, topic: str, max_results_per_query: int = 5) -> Path:
        """テーマを渡してリサーチを実行し、生成したレポートのファイルパスを返す。"""
        queries = self._decompose_topic(topic)
        sources = self._collect_sources(queries, max_results_per_query)
        report_markdown = self._write_report(topic, sources)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = REPORTS_DIR / f"{timestamp}_{_slugify(topic)}.md"
        output_path.write_text(report_markdown, encoding="utf-8")
        return output_path
