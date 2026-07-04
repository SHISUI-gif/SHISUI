"""質問内容に応じて、その場で最適なローカルモデルへ振り分けるルーター。

軽量な分類専用モデル(既定: qwen3:1.5b)で質問を CODING / REASONING / CHAT に
瞬時に分類し、それぞれに適したモデル(コーディング特化・推論特化・軽量雑談用)を
選ぶ。分類やモデル未取得などで失敗した場合は、既存の`settings.ollama_model`へ
安全にフォールバックする(ルーティング機能がチャット全体を止めないようにする)。

コーディング関連の質問は、分類LLMを呼ぶまでもなくキーワードだけで明白なことが
多い(「コード」「エラー」等)。この場合はLLM呼び出し(3〜4秒)を丸ごと省略して
即座にrouter_coding_modelへ振り分ける。キーワードに引っかからない場合のみ
LLM分類にフォールバックする(REASONING/CHATの判定はキーワードでは難しいため)。
"""
from __future__ import annotations

import re

import ollama

from config.settings import settings

CLASSIFICATION_PROMPT = """\
以下の質問を分析し、最適なモデルを選択せよ。
質問: {query}
選択肢:
- CODING: プログラミング、UI設計、システム開発関連
- REASONING: 論理的考察、哲学、深い洞察が必要な問い
- CHAT: 雑談、軽い調べ物
出力は以下の単語のみ: "CODING", "REASONING", "CHAT"
"""

_CATEGORY_TO_SETTING = {
    "CODING": "router_coding_model",
    "REASONING": "router_reasoning_model",
    "CHAT": "router_chat_model",
}

_CODING_KEYWORDS = re.compile(
    r"コード|プログラム|関数|バグ|エラー|実装|デバッグ|スクリプト|リファクタ|設計|"
    r"アーキテクチャ|API|バックエンド|フロントエンド|テスト|デプロイ",
    re.IGNORECASE,
)


def route_model(user_query: str) -> str:
    """質問内容に応じたモデル名を返す。ルーティング無効時・失敗時はsettings.ollama_modelを返す。"""
    if not settings.model_router_enabled:
        return settings.ollama_model

    if _CODING_KEYWORDS.search(user_query):
        return settings.router_coding_model

    try:
        decision = ollama.chat(
            model=settings.router_classifier_model,
            messages=[{"role": "user", "content": CLASSIFICATION_PROMPT.format(query=user_query)}],
        )
        category = decision["message"]["content"].strip().upper()
        setting_name = _CATEGORY_TO_SETTING.get(category)
        if setting_name is None:
            return settings.ollama_model
        return getattr(settings, setting_name)
    except Exception:  # noqa: BLE001
        # 分類モデル未取得・Ollama未起動などで失敗しても、通常の応答生成は止めない
        return settings.ollama_model
