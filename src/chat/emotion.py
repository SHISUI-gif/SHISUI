"""ユーザーの発言から感情のトーンを分類し、志粋の返答トーンに反映するための分類器。

src/chat/model_router.pyのroute_model()と同じ形(軽量な分類専用モデルで単語1つを
出力させ、辞書引きし、失敗時はフェイルオープンする)を踏襲するが、目的が別
(モデル選択ではなく返答トーンの調整)なので別モジュールにしている。

「決めつけない」という志粋の既存方針(src/core/feedback_log.py参照)を尊重し、
判定結果は常に「〜かもしれない」という断定を避けた形でヒント文にする。
NEUTRAL・分類失敗・無効化時はすべて「何も注入しない」という同じ安全側の挙動になる。
"""
from __future__ import annotations

import ollama

from config.settings import settings
from src.common import groq_client

EMOTION_CLASSIFICATION_PROMPT = """\
以下のユーザーの発言から感情を分析せよ。
発言: {message}
選択肢:
- ANXIOUS: 不安、緊張、心配、焦りが感じられる
- SAD: 落ち込み、悲しみ、元気の無さが感じられる
- FRUSTRATED: 苛立ち、怒り、不満が感じられる
- HAPPY: 上機嫌、喜び、テンションの高さが感じられる
- NEUTRAL: 上記のどれにも当てはまらない、平常運転
出力は以下の単語のみ: "ANXIOUS", "SAD", "FRUSTRATED", "HAPPY", "NEUTRAL"
"""

# NEUTRALは意図的に含めない(該当ヒント無し=何も注入しない、が安全側の既定動作)
_EMOTION_TONE_HINTS: dict[str, str] = {
    "ANXIOUS": (
        "ユーザーは今、不安や緊張、焦りを感じているかもしれない。決めつけず、断定はせず、"
        "いつもよりゆっくり、安心感を持たせる優しいトーンで応答して。"
    ),
    "SAD": (
        "ユーザーは今、元気が無い/落ち込んでいるかもしれない。決めつけず、そっと寄り添い、"
        "無理に励ましすぎず、自然体で温かいトーンで応答して。"
    ),
    "FRUSTRATED": (
        "ユーザーは今、苛立ちや不満を感じているかもしれない。決めつけず、まずは受け止め、"
        "冷静かつ丁寧なトーンで応答して。"
    ),
    "HAPPY": (
        "ユーザーは今、上機嫌でテンションが高いかもしれない。その明るいエネルギーに合わせて、"
        "いつもより弾んだ軽快なトーンで応答して。"
    ),
}


def detect_emotion(user_message: str) -> str | None:
    """ユーザー発言の感情を分類する。

    無効時・分類失敗時・未知の出力の場合はすべてNoneを返す(何も注入しない=
    フェイルオープン)。route_model()と同じくsettings.use_groqに応じて分類先を切り替える。
    """
    if not settings.emotion_detection_enabled:
        return None

    client = groq_client if settings.use_groq else ollama
    classifier_model = (
        settings.groq_classifier_model if settings.use_groq else settings.router_classifier_model
    )

    try:
        response = client.chat(
            model=classifier_model,
            messages=[
                {
                    "role": "user",
                    "content": EMOTION_CLASSIFICATION_PROMPT.format(message=user_message),
                }
            ],
        )
        category = response["message"]["content"].strip().upper()
        return category if category in _EMOTION_TONE_HINTS or category == "NEUTRAL" else None
    except Exception:  # noqa: BLE001
        # 分類モデル未取得・Ollama未起動・Groq APIエラー等で失敗しても、通常の応答生成は止めない
        return None


def tone_hint_for(category: str | None) -> str | None:
    """カテゴリからシステムプロンプトに追記するトーンヒントを返す。NEUTRAL/Noneなら常にNone。"""
    return _EMOTION_TONE_HINTS.get(category) if category else None
