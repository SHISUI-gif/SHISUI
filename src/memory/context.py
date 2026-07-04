"""会話時に新皮質(長期記憶)から関連記憶を検索し、プロンプトへ注入する文字列を組み立てる。

src/debate/feedback_store.pyのbuild_context()と同じ「フォーマット済み文字列を返し、
システムプロンプトへ連結する」スタイルに揃えている。
"""
from __future__ import annotations

from src.memory import neocortex


def build_recall_context(query: str, top_k: int | None = None) -> str:
    """ユーザーの発言に関連する長期記憶を検索し、システムプロンプトに連結できる文字列を返す。"""
    if not query.strip():
        # 空文字列をembedding検索に渡すと、chromadb側で空の埋め込みが返り
        # IndexErrorでクラッシュする(Ollama埋め込みAPIが空文字を空リストで返すため)
        return ""
    matches = neocortex.search(query, top_k=top_k)
    if not matches:
        return ""

    lines = ["志粋が覚えている関連情報(必要に応じて自然に会話へ活かすこと):"]
    for match in matches:
        lines.append(f"- [{match.category}] {match.text}")
    return "\n".join(lines)
