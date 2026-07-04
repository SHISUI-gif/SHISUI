"""会話時に文学的感性コーパスから文体・情緒表現のヒントを検索し、
システムプロンプトへ注入する文字列を組み立てる。

src/memory/context.pyのbuild_recall_context()と同じ形式を踏襲する。
原文そのものではなく、LLMが生成した短いスタイル記述子のみを扱うため、
長い原文が会話コンテキストへそのまま混入することはない。
"""
from __future__ import annotations

from src.corpus import ingest


def build_literary_hint(query: str, top_k: int | None = None) -> str:
    """ユーザーの発言に関連する文体・情緒表現のヒントを検索し、システムプロンプトに連結できる文字列を返す。"""
    if not query.strip():
        # build_recall_context()と同じ理由(空文字列がembedding検索をクラッシュさせる)で早期リターンする
        return ""
    hints = ingest.search(query, top_k=top_k)
    if not hints:
        return ""

    lines = ["志粋の文学的感性の参考(そのまま引用せず、トーンやリズムだけを意識すること):"]
    for hint in hints:
        lines.append(f"- [{hint.author}『{hint.title}』の文体] {hint.descriptor}")
    return "\n".join(lines)
