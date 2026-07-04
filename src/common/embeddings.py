"""ローカルOllamaの埋め込みAPIをchromadbのEmbeddingFunctionとして実装したもの。

完全ローカルで動作し、外部クラウドの埋め込みサービスに一切依存しない。
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
