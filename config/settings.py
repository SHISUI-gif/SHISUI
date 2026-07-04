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
    router_chat_model: str = os.getenv("ROUTER_CHAT_MODEL", "qwen3:8b")

    # 自己修復プロトコル(エラー検知→修正案生成→人間承認)。
    # コーディング特化のローカルモデルを使い、外部API(Gemini)には出さない。
    evolution_enabled: bool = os.getenv("EVOLUTION_ENABLED", "true").lower() == "true"
    evolution_fix_model: str = os.getenv("EVOLUTION_FIX_MODEL", "qwen3-coder:30b")

    # クラウド移行(Macの蓋を閉じても志粋が動き続けられるようにする選択肢)。
    # trueにすると、chat/embeddingの呼び出しをローカルOllamaではなくGroqの
    # 無料枠APIへ向ける。Ollamaより非力なサーバー(例: Oracle Cloud Always Free)
    # でもバックエンドを運用できるようにするための切り替えで、いつでもfalseに
    # 戻してローカルOllamaのみの運用に戻せる。
    use_groq: bool = os.getenv("USE_GROQ", "false").lower() == "true"
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    # GroqのEmbeddings APIはOllamaと同じnomic-embed-textファミリー(v1.5)を提供して
    # いるため、埋め込みベクトルの傾向が近く、移行時の影響が比較的小さい
    groq_embed_model: str = os.getenv("GROQ_EMBED_MODEL", "nomic-embed-text-v1_5")
    groq_classifier_model: str = os.getenv("GROQ_CLASSIFIER_MODEL", "llama-3.1-8b-instant")
    groq_coding_model: str = os.getenv("GROQ_CODING_MODEL", "qwen/qwen3-32b")
    groq_reasoning_model: str = os.getenv("GROQ_REASONING_MODEL", "qwen/qwen3-32b")
    groq_chat_model: str = os.getenv("GROQ_CHAT_MODEL", "qwen/qwen3-32b")


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
