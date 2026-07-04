# my-genspark

ローカル環境で完結するAIツール。自律型AIアシスタント「志粋(しすい)」として、以下の機能を持つ。

1. **自律リサーチ機能**: Tavily Search API + ローカルLLM(Ollama / Qwen系モデル)を組み合わせ、Gensparkのようにテーマをサブクエリに分解してWeb検索し、A4サイズ1枚相当のMarkdownレポートを自動生成する。
2. **議事録作成機能**: faster-whisper(文字起こし)+ pyannote.audio(話者分離)を使い、音声ファイルから話者ごとの文字起こしと要約(議事録)を完全ローカルで生成する。
3. **音声会話(Voice Chat)機能**: マイク入力 → Whisperで文字起こし → ローカルLLM(Qwen)で応答生成 → ローカルTTSでスピーカー出力、というリアルタイム音声対話をすべてローカルで行う。
4. **マルチエージェント討論・学習機能**: 提案者・批判者・ファシリテーターの3つのAIエージェント(LangGraphで構築)がテーマについて自律的に討論し、結論レポートを生成する。ユーザーが結論の正否と「お手本」の思考の連鎖をフィードバックすると、その内容はJSONに永続化され、次回以降の討論のコンテキストとしてAIに読み込まれる。
5. **記憶圧縮システム(Neuro-Memory Architecture)**: 志粋との会話を海馬(短期・生ログ)に記録し、1日1回の「睡眠モード」でQwenが好み・決定事項・事実だけを抽出して新皮質(長期・ベクトル記憶)へ圧縮する。以後の会話では関連する記憶を自動的に呼び出し、セッションをまたいだ文脈を保持する。
6. **文学的感性コーパス(Aozora Bunko)**: 青空文庫の厳選作品(夏目漱石・芥川龍之介・宮沢賢治・太宰治・中島敦)を取り込み、原文ではなくLLMが生成した短い「文体・情緒表現のスタイル記述子」だけをベクトルDBへ保存する。会話の雰囲気に応じてこれを検索し、文体・リズムのヒントとしてシステムプロンプトへ注入する。
7. **夜間修行(Autonomous Study Loop)**: 那由多さんがオフラインの間、志粋が自分の弱点(不確実だった発言・討論で誤りと指摘された結論)を分析し、外部メンターAI(Gemini)と深掘り討論して教訓を得る。教訓は新皮質へ通常の記憶として保存されるだけで、志粋のシステムプロンプト自体が自動で書き換わることはない。翌朝の会話で「昨夜学んだこと」を自然に話題にする。
8. **自律討論(Autonomous Debate)**: 夜間修行と同じ弱点分析を共用しつつ、外部メンターではなく既存のマルチエージェント討論機能(4)を使って、志粋が自分自身の弱点トピックについて提案者・批判者・ファシリテーターで自律的に討論する。夜間修行とは別のlaunchdジョブとして独立してスケジュールされる想定で、結論は新皮質と朝レポートへ保存される。ユーザー不在のためCLIでのフィードバック入力は行わない。
9. **青空文庫全体クロール**: 文学的感性コーパス(6)は厳選5作家だけだが、こちらは青空文庫の全作家(2000名以上)を1人ずつ順番に辿り、日次の「睡眠モード」のたびに少しずつ(既定10件/日)取り込んでいくチェックポイント式クローラー。原文を保存しない設計は(6)と完全に共通。ボランティア運営のサーバーへの配慮として、ゆっくり時間をかけて読み進める。

`shisui_app.py`(Gradioチャット、`src/common/persona.py`の「志粋の掟」に基づく人格を持ち、`src/common/tools.py`のツールコールで自律リサーチ機能を呼び出せる)と `python app.py voicechat` の両方が、この記憶システム・文学コーパス・夜間修行/自律討論レポートを共有する会話フロントエンドとなる。両者の中身(人格構築・記憶注入・ツールコール・ストリーミング応答)は`src/chat/shisui_chat.py`に集約されており、`src/api/main.py`(FastAPI)経由でGradio以外のフロントエンド(将来のNext.js UIなど)からも同じロジックを呼び出せる。

## ディレクトリ構成

```
my-genspark/
├── app.py                     # CLIエントリポイント (research / minutes / voicechat / debate / memory)
├── shisui_app.py               # 志粋のGradioチャットUI (ツールコール・記憶システム統合済み)
├── requirements.txt
├── .env.example                # 環境変数のサンプル(コピーして.envを作成する)
├── config/
│   └── settings.py             # .envを読み込み、全機能で共有する設定を提供する
├── src/
│   ├── common/
│   │   ├── llm_client.py        # Ollama(Qwen)呼び出しの共通クライアント
│   │   ├── persona.py           # 志粋の人格(志粋の掟)のシステムプロンプト
│   │   └── tools.py             # 志粋が使えるツール(web_search)の定義とレジストリ
│   ├── research/                # 1. 自律リサーチ機能
│   │   ├── web_search.py        # Tavily Search APIクライアント
│   │   └── report_generator.py  # サブクエリ分解 → 検索 → レポート執筆
│   ├── minutes/                  # 2. 議事録作成機能
│   │   ├── transcriber.py        # faster-whisperによる文字起こし
│   │   ├── diarizer.py           # pyannote.audioによる話者分離
│   │   ├── summarizer.py         # 議事録サマリー生成
│   │   └── minutes_generator.py  # 上記を統合し議事録Markdownを出力
│   ├── voicechat/                # 3. 音声会話機能
│   │   ├── audio_io.py           # マイク録音(プッシュトゥトーク方式)
│   │   ├── tts.py                # pyttsx3によるローカル音声合成
│   │   └── voice_chat_agent.py   # 聞く→考える→話すのリアルタイムループ
│   ├── debate/                   # 4. マルチエージェント討論・学習機能 / 8. 自律討論
│   │   ├── agents.py             # 提案者/批判者/ファシリテーターの役割定義
│   │   ├── graph.py              # LangGraphによる討論ステートグラフ(ASAL式早期収束判定つき)
│   │   ├── feedback_store.py     # ユーザーフィードバックのJSON永続化・文脈学習
│   │   ├── debate_agent.py       # 討論実行・レポート生成・フィードバックCLI
│   │   └── autonomous.py         # 自律討論: 弱点分析→討論→新皮質保存(ユーザー入力待ちなし)
│   ├── memory/                   # 5. 記憶圧縮システム(Neuro-Memory Architecture)
│   │   ├── hippocampus.py        # 海馬レイヤー: SQLiteによる短期・生ログ記憶
│   │   ├── neocortex.py          # 新皮質レイヤー: ChromaDBによる長期・ベクトル記憶
│   │   ├── sleep.py              # 睡眠モード: 海馬→新皮質への圧縮・supersede処理
│   │   ├── context.py            # 会話時に関連記憶を検索しプロンプトへ注入
│   │   └── scheduler.py          # 睡眠モードの1日1回自動トリガー
│   ├── corpus/                   # 6. 文学的感性コーパス / 9. 青空文庫全体クロール
│   │   ├── curated_list.py       # 厳選作家・作品リスト(6)
│   │   ├── aozora_scraper.py     # 礼儀正しいスクレイピング・ルビ/注記除去・全作家一覧取得
│   │   ├── ingest.py             # スタイル記述子生成・ChromaDBへの取り込み(6・9で共用)
│   │   ├── context.py            # 会話時に文体ヒントを検索しプロンプトへ注入
│   │   ├── full_archive.py       # 9: チェックポイント式に全作家・全作品を少しずつ取り込む
│   │   └── scheduler.py          # 9: 青空文庫全体クロールの1日1回自動トリガー
│   ├── study/                    # 7. 夜間修行(Autonomous Study Loop)
│   │   ├── mentor_client.py      # メンターAI(Gemini)クライアント、使用ログ付き
│   │   ├── weakness_finder.py    # 弱点分析(海馬の⚠️発言 + 討論の誤り指摘から抽出、8とも共用)
│   │   ├── study_session.py      # メンターとの深掘り討論 → 新皮質への教訓保存
│   │   └── report.py             # 翌朝の会話に注入する未読レポートの管理(7・8で共用)
│   ├── chat/
│   │   └── shisui_chat.py        # 志粋の「頭脳」。Gradio/FastAPI共通の会話ロジック本体
│   └── api/
│       └── main.py               # FastAPIバックエンド (将来のNext.js等フロントエンド向け)
├── scripts/
│   ├── com.shisui.study.plist    # 夜間修行を深夜2時に自動実行するlaunchd設定のひな形
│   └── com.shisui.debate.plist   # 自律討論を深夜3時に自動実行するlaunchd設定のひな形
├── output/
│   ├── reports/                  # 生成されたリサーチレポート(Markdown)
│   ├── minutes/                  # 生成された議事録(Markdown)
│   ├── debate/                   # 討論レポート(Markdown)とフィードバック履歴(JSON)
│   ├── memory/                   # hippocampus.sqlite3 / neocortex_chroma/ / last_sleep_date.txt
│   ├── corpus/                   # literary_chroma/ / raw_cache/
│   └── study/                    # sessions.json / gemini_usage.log / launchd_*.log
├── data/audio/                   # 議事録化したい音声ファイルの置き場
└── tests/                        # pytestによる自動テスト
```

## セットアップ

### 1. Python仮想環境と依存パッケージ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- `faster-whisper` / `pyannote.audio` / `torch` はモデル本体が大きいため、初回インストール・初回実行時のモデルダウンロードに時間がかかる。
- 音声ファイルの読み込みには `ffmpeg` がシステムにインストールされている必要がある(`brew install ffmpeg` など)。
- `sounddevice`(マイク録音)はPortAudioに依存する。多くの環境ではpipのwheelに同梱されるが、認識されない場合は `brew install portaudio` を実行する。
- `pyttsx3` はmacOSでは内部的に `pyobjc` を利用する。

### 2. 環境変数

```bash
cp .env.example .env
```

`.env` を編集し、以下を設定する。

| 変数名 | 用途 |
|---|---|
| `TAVILY_API_KEY` | Tavily Search APIキー(自律リサーチ機能で必須) |
| `OLLAMA_HOST` | Ollamaの接続先(既定: `http://localhost:11434`) |
| `OLLAMA_MODEL` | 使用するローカルLLM名(Qwen系モデルを想定。既定: `qwen2.5`) |
| `HUGGINGFACE_TOKEN` | pyannote.audioの話者分離モデル利用に必要(議事録機能で必須) |
| `WHISPER_MODEL_SIZE` | faster-whisperのモデルサイズ(既定: `large-v3`) |
| `WHISPER_DEVICE` | `cpu` または `cuda`(既定: `cpu`) |
| `DEBATE_FEEDBACK_CONTEXT_LIMIT` | 討論時に読み込む直近フィードバックの件数(既定: `8`) |
| `OLLAMA_EMBED_MODEL` | 新皮質(長期記憶)の埋め込みに使うOllamaモデル(既定: `nomic-embed-text`) |
| `MEMORY_RETENTION_DAYS` | 海馬(短期記憶)の生ログ保持日数(既定: `7`) |
| `MEMORY_RECALL_TOP_K` | 会話時に新皮質から呼び出す関連記憶の件数(既定: `5`) |
| `MEMORY_SIMILARITY_THRESHOLD` | 新皮質メモリをsupersede(置き換え)扱いにする類似度のしきい値(既定: `0.85`) |

### 3. Ollama側の準備

```bash
ollama pull qwen2.5
ollama pull nomic-embed-text   # 記憶圧縮システムの埋め込み用
ollama serve
```

### 4. pyannote.audioの利用規約への同意

Hugging Faceで以下2つのモデルページの利用規約に同意しておく必要がある。

- `pyannote/speaker-diarization-3.1`
- `pyannote/segmentation-3.0`

## 使い方

### 1. 自律リサーチ

```bash
python app.py research "生成AIが労働市場に与える影響"
python app.py research "生成AIが労働市場に与える影響" --max-results 8
```

`output/reports/` にMarkdownレポートが生成される。

### 2. 議事録作成

```bash
python app.py minutes data/audio/meeting.wav
```

`output/minutes/` に話者別文字起こしと要約を含むMarkdownが生成される。

### 3. 音声会話

```bash
python app.py voicechat
```

Enterキーを押して話しかけ、もう一度Enterキーで発話終了。AIの応答がスピーカーから再生される。「終了」「exit」などと話すと会話を終了する。

### 4. マルチエージェント討論

```bash
python app.py debate "週4日勤務制を導入すべきか"
python app.py debate "週4日勤務制を導入すべきか" --rounds 4
```

提案者・批判者・ファシリテーターが討論し、`output/debate/` に結論レポートが生成される。実行後、結論の妥当性についてCLI上でフィードバック(正しい/正しくない、正しい場合のお手本の思考の連鎖)を入力でき、内容は `output/debate/feedback_history.json` に保存される。次回以降の討論では、この履歴がエージェントのコンテキストとして自動的に読み込まれる。自動実行やテストでフィードバック入力をスキップしたい場合は `--skip-feedback` を付ける。

### 5. 記憶圧縮システム

`shisui_app.py`や`voicechat`での会話は自動的に海馬(SQLite)へ記録され、1日1回(セッション開始時に未実行なら自動実行)、Qwenが「好み・決定事項・事実」を抽出して新皮質(ChromaDB)へ圧縮する。新しい記憶が既存の記憶と類似度`MEMORY_SIMILARITY_THRESHOLD`以上で被った場合は、古い方をsuperseded(置き換え済み)としてマークし、矛盾した記憶が積み重ならないようにする。

```bash
# 睡眠モード(要約・圧縮)を今すぐ手動実行する
python app.py memory sleep

# 新皮質(長期記憶)に保存されている記憶を一覧表示する
python app.py memory list
```

自動トリガーはOSのアイドル検知ではなく「1日1回、まだ実行していなければ実行する」という簡易版のため、真のアイドル検知や決まった時刻での実行がしたい場合は`python app.py memory sleep`をmacOSの`launchd`やcronに登録するとよい。

### 6. 文学的感性コーパス

```bash
# 青空文庫の厳選作品を取り込み、文体・情緒表現のスタイル記述子を生成する(初回は数分かかる)
python app.py corpus ingest

# キャッシュ・既存メモリを無視して再取得・再生成する
python app.py corpus ingest --force

# 取り込み済みのスタイル記述子を一覧表示する
python app.py corpus list
```

原文そのものは新皮質にも会話コンテキストにも一切保存・注入されない。取得した本文サンプルはLLMが「文体・語彙・リズムのみを2文以内・引用禁止」で言い換えたスタイル記述子だけを保存し、生成結果が原文からの逐語引用になっていないかも自動チェックする。

### 7. 夜間修行(Autonomous Study Loop)

```bash
# 夜間修行を今すぐ手動実行する (要 GEMINI_API_KEY)
python app.py study run

# 直近の夜間修行の結果を表示する
python app.py study report
```

海馬の`⚠️`付き発言(掟4の不確実性マーカー)と、討論機能で「誤り」と指摘された結論から弱点トピックを抽出し、メンターAI(Gemini)と数往復の深掘り討論を行う。得られた教訓は新皮質へ通常の記憶として保存されるだけで、`src/common/persona.py`などのシステムプロンプト自体が自動で書き換わることはない。翌朝、`shisui_app.py`や`voicechat`での最初の会話に「昨夜学んだこと」が自然に注入される(1回表示すると既読化される)。

**本当に深夜に自動実行したい場合**(推奨、要 那由多さんの確認):

```bash
cp scripts/com.shisui.study.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.shisui.study.plist
```

Macが完全スリープ中は発火しない場合があるため、その場合は次回起動時などに手動で`python app.py study run`を実行すればよい。無効化するには`launchctl unload ~/Library/LaunchAgents/com.shisui.study.plist`。

### 8. 自律討論

```bash
# 弱点トピックについて志粋が自律的に討論する(要 Ollama起動、外部APIは不要)
python app.py debate-autonomous
```

夜間修行と同じ弱点分析を共用しつつ、外部メンターの代わりに既存のマルチエージェント討論機能(4)を使う。ユーザー不在のため`--skip-feedback`相当(CLIでのフィードバック入力なし)で動作し、結論は`output/debate/`のレポートと新皮質、朝レポートへ保存される。夜間修行とはリソース競合を避けるため別のlaunchdジョブとして独立させている。

```bash
cp scripts/com.shisui.debate.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.shisui.debate.plist
```

### 9. 青空文庫全体クロール

```bash
# 本日分(既定10件)を取り込む(手動・launchd両対応)
python app.py corpus archive-crawl

# 進捗を確認する
python app.py corpus archive-status
```

初回実行時に青空文庫の全作家一覧(2000名以上)を1度だけ取得し、以降は作家→作品の順に1つずつ辿るチェックポイントを`output/corpus/full_archive_progress.json`に保存する。`shisui_app.py`/`voicechat`の起動時に(睡眠モードと同様)1日1回自動実行され、`AOZORA_ARCHIVE_DAILY_LIMIT`(既定10)件ずつ進む。原文の非保存・スタイル記述子のみの方針は厳選版(6)と完全に共通で、同じ`literary_corpus`へ蓄積される。

### 10. API層(将来のフロントエンド向け)

```bash
python app.py api            # http://127.0.0.1:8000 で起動 (既定ポート、--portで変更可)
```

`GET /api/health` で疎通確認、`POST /api/chat`(`{"message": str, "history": [...]}`)で志粋との会話をストリーミングで取得できる。中身は`shisui_app.py`と全く同じ`src/chat/shisui_chat.py`の関数を呼んでいるため、記憶・文学コーパス・ツールコール・朝レポートは両方のフロントエンドで共有される。GradioのUI(port 7860)とは独立しているため、同時に起動しておいて問題ない。

## テスト

```bash
python -m pytest tests/
```
