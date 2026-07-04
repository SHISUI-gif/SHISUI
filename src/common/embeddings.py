"""ローカルOllamaの埋め込みAPIをchromadbのEmbeddingFunctionとして実装したもの。

`settings.use_groq`が有効な場合でも、埋め込みだけは常にローカルOllamaを使う。
GroqのPython SDKは`client.embeddings.create()`を公開しており、型ヒント上は
`nomic-embed-text-v1_5`が使えるように見えるが、実際にこのプロジェクトのAPI
キーで試したところ404(モデルが存在しない/アクセス権が無い)で失敗することを
確認済み(`client.models.list()`で確認しても埋め込み系モデルは1つも一覧に
出てこない)。過去にGroq側へ条件分岐していたことがあり、その状態で移行
スクリプトを実行して既存の新皮質データを実際に失った事故があったため、
「Groqのembeddingsは使わない」という判断を後から覆さないこと。
記憶システム(src/memory/neocortex.py)と文学的感性コーパス(src/corpus/)の
両方が同じ実装を共有する。
"""
from __future__ import annotations

import ollama
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction

from config.settings import settings


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """chromadbのEmbeddingFunctionを、Ollamaのembeddings APIで実装したもの。"""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.ollama_embed_model

    def __call__(self, input: Documents) -> Embeddings:
        return [ollama.embeddings(model=self.model, prompt=text)["embedding"] for text in input]

    @staticmethod
    def name() -> str:
        return "ollama_embedding_function"

    def get_config(self) -> dict:
        return {"model": self.model}

    @staticmethod
    def build_from_config(config: dict) -> "OllamaEmbeddingFunction":
        return OllamaEmbeddingFunction(model=config.get("model"))
