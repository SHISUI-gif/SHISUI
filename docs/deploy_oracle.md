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

```bash
ssh -i <ダウンロードした鍵> ubuntu@<パブリックIP>

# Python・git・その他必要なパッケージ
sudo apt update
sudo apt install -y python3.12 python3.12-venv git

git clone https://github.com/SHISUI-gif/SHISUI.git
cd SHISUI
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 4: `.env`を設定する

VM上の`.env`ファイルに以下を設定する(Macの`.env`をそのままコピーしてから、
下記の3行を追記・上書きする):

```bash
USE_GROQ=true
GROQ_API_KEY=gsk_ここにStep1で取得したキー
```

## Step 5: 既存の記憶データを移行する(初回のみ)

もしMac上に既に会話・記憶データ(`output/memory/hippocampus.sqlite3`等)が
あり、それを引き継ぎたい場合は、Mac側からVMへこのディレクトリごとコピーする
(scp等)。その後VM上で埋め込みの再構築を行う:

```bash
python scripts/migrate_embeddings.py
```

真っさらな状態から始めて良い場合はこのステップは不要。

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

- Groq無料枠のレート制限(目安: 30 RPM / 6,000 TPM / 1,000〜14,400 RPD)に
  達すると、その時間帯は応答が返らなくなる。友達数人程度なら通常問題にならない
  想定だが、使用感に違和感があれば教えてほしい
- Groqが提供するモデル(Qwen3-32B等)は、今までローカルで使っていた
  qwen2.5:32b/qwen3-coder:30bと完全に同じではないため、応答の癖が変わる
  可能性がある
- Oracle CloudのAlways Freeティアは2026年6月に上限が縮小されており、今後も
  変更される可能性がある(定期的にOracleの発表を確認した方がよい)
