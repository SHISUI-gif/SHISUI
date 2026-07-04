# クラウド移行手順: Vercel(フロント)+ Oracle Cloud(バックエンド)+ Groq(AI推論)

Macの蓋を閉じても志粋が動き続けられるようにするための、完全無料でのクラウド
移行手順。この手順の実行(アカウント作成・VM作成・SSH接続)は那由多さん自身の
認証情報が必要なため、Claude Codeが代行できない部分です。詰まったら遠慮なく
このターミナルで相談してください。

## 前提

- Groq APIキー(console.groq.com、無料・クレジットカード不要)
- Oracle Cloudアカウント(本人確認にクレジットカードが必要。プリペイド/バーチャル
  カードは不可。地域によっては審査に失敗することがあるので、失敗したら別の
  選択肢を相談してください)
- Vercelアカウント(GitHubアカウントでログイン可能)
- 既にGitHubにpush済みの`https://github.com/SHISUI-gif/SHISUI.git`

## Step 1: Groq APIキーを取得する

1. https://console.groq.com にアクセスし、Googleアカウント等でログイン
2. 左メニューの「API Keys」→「Create API Key」
3. `gsk_`から始まるキーをコピーしておく(後で使う)

## Step 2: Oracle Cloud Always Free VMを作る

1. https://www.oracle.com/cloud/free/ からサインアップ(クレジットカードでの
   本人確認あり。実際には課金されない)
2. コンソールにログインしたら「Compute」→「Instances」→「Create Instance」
3. イメージ: Ubuntu(最新LTS)を選択
4. シェイプ: 「Ampere」(ARMベース)を選び、**2 OCPU・12GB RAM**に収まるよう設定
   (2026年6月の変更でAlways Freeの上限がここまで縮小されているため、これを
   超えると課金対象になる点に注意)
5. SSH鍵を生成してダウンロード(接続に必須、無くさないこと)
6. インスタンス作成後、パブリックIPアドレスをメモしておく

## Step 3: VMに接続し、必要なものをインストールする

**重要な訂正**: 当初「Groqがembeddingsにも対応しているので、VM側にOllamaは
一切不要」という想定だったが、実際のAPIキーで検証したところGroqの
embeddings API(`nomic-embed-text-v1_5`)は404で使えないことが判明した
(`src/common/embeddings.py`のコメント参照)。そのため、**VM側にも軽量な
Ollamaを入れ、embedding専用モデル(`nomic-embed-text`)だけはローカルで
動かす**必要がある。生成・モデル振り分け・ツール判定はGroqに任せられるので、
VM側で動かすモデルはこの小さなembeddingモデル1つだけで済む(2 OCPU/12GB RAMで
十分収まる規模)。

```bash
ssh -i <ダウンロードした鍵> ubuntu@<パブリックIP>

# Python・git・その他必要なパッケージ
sudo apt update
sudo apt install -y python3.12 python3.12-venv git

# Ollama(embedding専用。生成モデルはpull不要、nomic-embed-textだけでよい)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text

git clone https://github.com/SHISUI-gif/SHISUI.git
cd SHISUI
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 4: `.env`を設定する

VM上の`.env`ファイルに以下を設定する(Macの`.env`をそのままコピーしてから、
下記の行を追記・上書きする)。`OLLAMA_HOST`はVM上のOllama(embedding専用)を
指すのでこれまで通りの既定値のままでよい:

```bash
USE_GROQ=true
GROQ_API_KEY=gsk_ここにStep1で取得したキー
```

## Step 5: 既存の記憶データを移行する(初回のみ、必要な場合だけ)

embeddingは常にローカルOllama(VM上のOllama)を使うため、**Mac上のデータを
そのままVMに持っていく場合、埋め込みモデルは変わらない(nomic-embed-text→
同じnomic-embed-text)ので、実は再埋め込みは不要**。`output/memory/`・
`output/corpus/`ディレクトリをそのままVMへコピーすれば動く。

`scripts/migrate_embeddings.py`は「埋め込みモデル自体を変える」場合専用
(例えば将来Groqや他社のembeddings APIが実際に使えるようになった場合)。
実行する場合は、新しいコレクションを完全に構築・件数検証してから古い
コレクションを削除する安全な設計になっている(delete-then-rebuildで
新皮質データを実際に失った事故があったため、build-then-swapに書き直し済み)。
それでも実行前には`output/memory/`・`output/corpus/`のバックアップを
取ってから行うこと。

## Step 6: バックエンドを常時起動しておく(systemdサービス化)

```bash
sudo tee /etc/systemd/system/shisui-api.service > /dev/null <<'EOF'
[Unit]
Description=Shisui FastAPI backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/SHISUI
ExecStart=/home/ubuntu/SHISUI/.venv/bin/python app.py api
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now shisui-api
sudo systemctl status shisui-api
```

## Step 7: 外部公開する(cloudflaredをVM側で動かす)

今Mac上でやっているのと同じ仕組みをVM側に移すだけでよい:

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/

# quick tunnelでよければこれだけで公開できる(URLは毎回変わる)
cloudflared tunnel --url http://localhost:8000
```

固定URLにしたい場合は、Cloudflareアカウント+ドメインを使ったnamed tunnelを
別途検討する(この手順書の範囲外、必要になったら相談してください)。

## Step 8: フロントエンドをVercelにデプロイする

1. https://vercel.com にGitHubアカウントでログイン
2. 「New Project」→ `SHISUI-gif/SHISUI` リポジトリを選択
3. Root Directoryを `frontend` に設定
4. 環境変数に `BACKEND_URL` を追加し、Step 7で得たFastAPIの公開URL
   (`https://xxxx.trycloudflare.com` 等)を設定する
5. デプロイ実行。完了すると`https://<プロジェクト名>.vercel.app`のような
   固定URLが発行される(これがVercelを使う一番のメリット — Cloudflareの
   quick tunnelと違い、毎回変わらない)

## 完了後の確認

- `https://<プロジェクト名>.vercel.app` にMacを閉じた状態でスマホからアクセスし、
  ログイン・チャット送信ができることを確認する
- 友達複数人での同時利用・会話の分離も、既存のマルチユーザーテストと同じ観点で
  確認する

## 既知の制約(完全無料を選んだことによるトレードオフ)

- **embeddingはGroqでは動かない**。当初「Groqがembeddingsにも対応しているので
  VM側にOllama不要」という想定で設計したが、実際のAPIキーで検証したところ
  `nomic-embed-text-v1_5`は404(利用不可)だった。そのためVM側にも軽量な
  Ollama(embedding専用モデルのみ)が必要(Step 3参照)。「完全にOllama不要」
  という当初の想定は誤りだったことをここに明記しておく
- Groq無料枠のレート制限(目安: 30 RPM / 6,000 TPM / 1,000〜14,400 RPD)に
  達すると、その時間帯は応答が返らなくなる。友達数人程度なら通常問題にならない
  想定だが、使用感に違和感があれば教えてほしい
- Groqが提供するモデル(Qwen3-32B等)は、今までローカルで使っていた
  qwen2.5:32b/qwen3-coder:30bと完全に同じではないため、応答の癖が変わる
  可能性がある
- Oracle CloudのAlways Freeティアは2026年6月に上限が縮小されており、今後も
  変更される可能性がある(定期的にOracleの発表を確認した方がよい)
