"""プロジェクト全体の設定を一元管理するモジュール。

.envファイルから環境変数を読み込み、Settingsオブジェクトとして提供する。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "output" / "reports"
MINUTES_DIR = BASE_DIR / "output" / "minutes"
DEBATE_DIR = BASE_DIR / "output" / "debate"
FEEDBACK_FILE = DEBATE_DIR / "feedback_history.json"
MEMORY_DIR = BASE_DIR / "output" / "memory"
HIPPOCAMPUS_DB_PATH = MEMORY_DIR / "hippocampus.sqlite3"
NEOCORTEX_DB_DIR = MEMORY_DIR / "neocortex_chroma"
SLEEP_MARKER_FILE = MEMORY_DIR / "last_sleep_date.txt"
CORPUS_DIR = BASE_DIR / "output" / "corpus"
LITERARY_CHROMA_DIR = CORPUS_DIR / "literary_chroma"
RAW_CACHE_DIR = CORPUS_DIR / "raw_cache"
STUDY_DIR = BASE_DIR / "output" / "study"
STUDY_LOG_FILE = STUDY_DIR / "gemini_usage.log"
STUDY_SESSIONS_FILE = STUDY_DIR / "sessions.json"
AOZORA_ARCHIVE_PROGRESS_FILE = CORPUS_DIR / "full_archive_progress.json"
AOZORA_ARCHIVE_MARKER_FILE = CORPUS_DIR / "last_archive_crawl_date.txt"
EVOLUTION_DIR = BASE_DIR / "output" / "evolution"
ERROR_LOG_FILE = EVOLUTION_DIR / "error_log.json"
FEEDBACK_LOG_FILE = EVOLUTION_DIR / "feedback_log.json"
USER_FEEDBACK_FILE = EVOLUTION_DIR / "user_feedback.json"
PENDING_PATCHES_DIR = EVOLUTION_DIR / "pending"
STUDY_MARKER_FILE = STUDY_DIR / "last_study_date.txt"
DEBATE_AUTONOMOUS_MARKER_FILE = DEBATE_DIR / "last_autonomous_debate_date.txt"
ACTIVITY_DIR = BASE_DIR / "output" / "activity"
ACTIVITY_LOG_FILE = ACTIVITY_DIR / "activity_log.json"

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    # 自律リサーチ機能
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5")

    # 議事録作成機能
    huggingface_token: str = os.getenv("HUGGINGFACE_TOKEN", "")
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "large-v3")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")

    # マルチエージェント討論・学習機能
    debate_feedback_context_limit: int = int(os.getenv("DEBATE_FEEDBACK_CONTEXT_LIMIT", "8"))
    # 埋め込みの新規性が収束したら、max_rounds前でも討論を早期終了する(ASALの収束判定を参考)
    debate_min_rounds_before_novelty_check: int = int(
        os.getenv("DEBATE_MIN_ROUNDS_BEFORE_NOVELTY_CHECK", "2")
    )
    debate_novelty_similarity_threshold: float = float(
        os.getenv("DEBATE_NOVELTY_SIMILARITY_THRESHOLD", "0.92")
    )

    # 記憶圧縮システム(Neuro-Memory Architecture)
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    memory_retention_days: int = int(os.getenv("MEMORY_RETENTION_DAYS", "7"))
    memory_recall_top_k: int = int(os.getenv("MEMORY_RECALL_TOP_K", "5"))
    memory_similarity_threshold: float = float(os.getenv("MEMORY_SIMILARITY_THRESHOLD", "0.85"))
    # アバター解除判定の対象期間。「その日話した内容だけ」だと話題が1日に
    # 集中しなかった場合に永久にチャンスを逃すため、複数日分の会話を毎回まとめて見る。
    avatar_unlock_lookback_days: int = int(os.getenv("AVATAR_UNLOCK_LOOKBACK_DAYS", "3"))

    # 文学的感性コーパス(Aozora Bunko)
    literary_hint_top_k: int = int(os.getenv("LITERARY_HINT_TOP_K", "2"))

    # 夜間修行(Autonomous Study Loop)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    study_dialogue_turns: int = int(os.getenv("STUDY_DIALOGUE_TURNS", "3"))
    study_weak_topics_count: int = int(os.getenv("STUDY_WEAK_TOPICS_COUNT", "2"))

    # 青空文庫全体の段階的な取り込み(睡眠モードで少しずつ読み進める)
    aozora_archive_daily_limit: int = int(os.getenv("AOZORA_ARCHIVE_DAILY_LIMIT", "10"))

    # モデルルーティング(質問内容に応じて最適なローカルモデルを選ぶ)
    model_router_enabled: bool = os.getenv("MODEL_ROUTER_ENABLED", "true").lower() == "true"
    # Qwen3の実際のラインナップは0.6b/1.7b/4b/8b/14b/30b/32b/235bのみ(1.5b/7bは存在しない)
    router_classifier_model: str = os.getenv("ROUTER_CLASSIFIER_MODEL", "qwen3:1.7b")
    router_coding_model: str = os.getenv("ROUTER_CODING_MODEL", "qwen3-coder:30b")
    router_reasoning_model: str = os.getenv("ROUTER_REASONING_MODEL", "deepseek-r1:8b")
    # あいさつ・一言確認等の軽い雑談は、Qwen3 8Bよりさらに小さいqwen3:1.7bに任せる。
    # 当初Phi-3.5 Mini(2.2GB)を試したが、システムプロンプト付きで実際に検証したところ
    # 日本語のカジュアルな口調が崩れ、支離滅裂で過度に丁寧な文章になったため不採用。
    # qwen3:1.7bは分類器としても既に実績があり、日本語のカジュアルな返答も自然だった。
    router_simple_model: str = os.getenv("ROUTER_SIMPLE_MODEL", "qwen3:1.7b")
    # 内容のある雑談はGemma 2 9Bへ(Qwen3 8Bより自然な会話文になる傾向があるため変更)
    router_chat_model: str = os.getenv("ROUTER_CHAT_MODEL", "gemma2:9b")

    # ニュース学習(Currents API、無料枠1日1000リクエスト・クレジットカード不要)。
    # (1) 会話中にユーザーが求めたら今日のニュースを調べて紹介するツール、
    # (2) 夜間修行で「社会」トピックとして時事ニュースも学ぶ、の両方で使う。
    # 未設定(空文字列)ならどちらの機能も無効になる(必須ではない)。
    currents_api_key: str = os.getenv("CURRENTS_API_KEY", "")
    study_news_topics_count: int = int(os.getenv("STUDY_NEWS_TOPICS_COUNT", "1"))

    # 天気予報(Open-Meteo API、完全無料・APIキー不要)。
    # ユーザーが地名を指定しない場合や、地名からの位置特定に失敗した場合の
    # 既定地点(那由多さんの利用地域である東京がデフォルト)。
    weather_default_latitude: float = float(os.getenv("WEATHER_DEFAULT_LATITUDE", "35.6762"))
    weather_default_longitude: float = float(os.getenv("WEATHER_DEFAULT_LONGITUDE", "139.6503"))
    weather_default_location_name: str = os.getenv("WEATHER_DEFAULT_LOCATION_NAME", "東京")

    # 感情トーン検知(ユーザーの発言の感情を分類し、志粋の返答トーンに反映する)。
    # 分類モデルはROUTER_CLASSIFIER_MODEL(またはGroq利用時はGROQ_CLASSIFIER_MODEL)を共用する。
    emotion_detection_enabled: bool = os.getenv("EMOTION_DETECTION_ENABLED", "true").lower() == "true"

    # 自己修復プロトコル(エラー検知→修正案生成)。
    # コーディング特化のモデルを使う。use_groq時はローカルの重いコーディングモデルの
    # 代わりにgroq_coding_modelを使う(VM等、ローカルにqwen3-coder:30bが無い環境向け)。
    evolution_enabled: bool = os.getenv("EVOLUTION_ENABLED", "true").lower() == "true"
    evolution_fix_model: str = os.getenv("EVOLUTION_FIX_MODEL", "qwen3-coder:30b")
    # 2026-07-27、那由多さんの明示的な同意により全自動適用に変更(それまでは
    # 修正案の生成だけ自動・適用は`evolution apply`での人間承認が必須だった)。
    # 生成されたパッチはテストが全件通った場合のみコミットされ、失敗時は
    # 作業ツリーを破棄して何も適用しない。falseにすれば元の「提案のみ」に戻せる。
    evolution_auto_apply: bool = os.getenv("EVOLUTION_AUTO_APPLY", "true").lower() == "true"

    # クラウド移行(Macの蓋を閉じても志粋が動き続けられるようにする選択肢)。
    # trueにすると、chatの呼び出し(生成・モデル振り分け・ツール判定)をローカル
    # Ollamaではなく Groqの無料枠APIへ向ける。いつでもfalseに戻してローカル
    # Ollamaのみの運用に戻せる。
    # 注意: embeddingはこのフラグの対象外(常にローカルOllama)。GroqのSDKは
    # embeddings.create()を公開しているが、実際のAPIキーで検証した結果
    # nomic-embed-text-v1_5は404(利用不可)だった(src/common/embeddings.py参照)。
    # 過去にembeddingもGroq化した状態で移行スクリプトを実行し、新皮質の記憶
    # データを実際に失った事故があるため、安易にembeddingをGroqへ向けないこと。
    use_groq: bool = os.getenv("USE_GROQ", "false").lower() == "true"
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_classifier_model: str = os.getenv("GROQ_CLASSIFIER_MODEL", "llama-3.1-8b-instant")
    groq_coding_model: str = os.getenv("GROQ_CODING_MODEL", "qwen/qwen3.6-27b")
    groq_reasoning_model: str = os.getenv("GROQ_REASONING_MODEL", "qwen/qwen3.6-27b")
    groq_chat_model: str = os.getenv("GROQ_CHAT_MODEL", "qwen/qwen3.6-27b")

    # OpenRouter(無料枠、コーディング質問だけ限定で使う)。
    # OpenRouterの無料枠(:freeモデル)は1日50〜1000リクエストとGroqよりかなり
    # 少ないため、雑談等の一般的な会話には向かない(1ターンで複数回LLM呼び出しが
    # 走るため、すぐ枯渇する)。コーディング質問だけ、より大きなモデル
    # (Qwen3 Coder 480B)に逃がす限定用途で使う。未設定(空文字列)なら
    # 従来通りOllama/Groqでコーディング質問も処理する。
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_coding_model: str = os.getenv("OPENROUTER_CODING_MODEL", "qwen/qwen3-coder:free")

    # 夜間トリガー(睡眠・自律学習・自律討論を「夜眠っている間」だけ動かす)
    night_mode_start_hour: int = int(os.getenv("NIGHT_MODE_START_HOUR", "23"))
    night_mode_end_hour: int = int(os.getenv("NIGHT_MODE_END_HOUR", "6"))
    night_mode_end_minute: int = int(os.getenv("NIGHT_MODE_END_MINUTE", "30"))
    night_mode_check_interval_seconds: int = int(
        os.getenv("NIGHT_MODE_CHECK_INTERVAL_SECONDS", "600")
    )

    # オーナー権限(那由多さんだけが操作できる機能を区別するための識別子)
    owner_user_name: str = os.getenv("OWNER_USER_NAME", "那由多")


settings = Settings()

for directory in (
    REPORTS_DIR,
    MINUTES_DIR,
    DEBATE_DIR,
    MEMORY_DIR,
    CORPUS_DIR,
    RAW_CACHE_DIR,
    STUDY_DIR,
    PENDING_PATCHES_DIR,
    ACTIVITY_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)
