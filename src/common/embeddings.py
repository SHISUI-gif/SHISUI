"""埋め込みAPIをchromadbのEmbeddingFunctionとして実装したもの。

既定はローカルOllamaで完全ローカルに動作するが、`settings.use_groq`が
trueの場合はGroqの無料枠embeddings API(`nomic-embed-text-v1_5`、Ollama版と
同じモデルファミリー)を使う。Macの蓋を閉じても志粋が動けるようにする
クラウド移行の選択肢のため(config/settings.py参照)。
記憶システム(src/memory/neocortex.py)と文学的感性コーパス(src/corpus/)の
両方が同じ実装を共有する。
"""
from __future__ import annotations

import ollama
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction

from config.settings import settings
from src.common import groq_client


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """chromadbのEmbeddingFunctionを、Ollama(既定)またはGroqのembeddings APIで実装したもの。"""

    def __init__(self, model: str | None = None) -> None:
        default_model = settings.groq_embed_model if settings.use_groq else settings.ollama_embed_model
        self.model = model or default_model

    def __call__(self, input: Documents) -> Embeddings:
        client = groq_client if settings.use_groq else ollama
        return [client.embeddings(model=self.model, prompt=text)["embedding"] for text in input]

    @staticmethod
    def name() -> str:
        return "ollama_embedding_function"

    def get_config(self) -> dict:
        return {"model": self.model}

    @staticmethod
    def build_from_config(config: dict) -> "OllamaEmbeddingFunction":
        return OllamaEmbeddingFunction(model=config.get("model"))
