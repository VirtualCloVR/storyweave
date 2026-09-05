# Storyweave

作品ごとの検討事項を「採用・検討中・没」として管理し、採用した内容だけを次の相談へ引き継ぐ、創作・SS相談専用のWebワークスペースです。ChatGPTの汎用クローンではなく、`Project → Thread → Session → Message` の構造を中心に設計します。

## v0.1の方針

自宅LANまたはVPN（主にTailscale）内で利用する前提です。認証・マルチユーザー・公開インターネット向けの運用は対象外です。LLMはアプリに内蔵せず、Ollama、llama.cpp、vLLMなどが提供するOpenAI互換HTTP APIへ接続します。

採用済みSessionの`adoption_summary`だけを、同じThreadの別SessionのLLMコンテキストへ投入します。`considering`、`rejected`、`superseded`は投入せず、`archived`は採用知識としての有効性と分離して扱います。

## Architecture

```text
Browser (React / Vite)
        │ REST API / SSE
        ▼
FastAPI backend ── SQLAlchemy 2 / Alembic ── PostgreSQL
        │
        └── OpenAI-compatible LLM endpoint (Compose外部)
```

BackendがProject、Thread、Session、Message、Sourceを永続化します。FrontendからDatabaseへ直接接続しません。Context Builder、URL fetchの安全対策、LLM接続はBackend側に置き、将来のプロバイダ差し替えに依存しない境界を保ちます。

## 使用技術

- Frontend: React、TypeScript、Vite
- Backend: Python、FastAPI、SQLAlchemy 2系、Alembic
- Database: PostgreSQL
- LLM: OpenAI互換API（Ollama / llama.cpp / vLLM等）
- 開発・検証: Docker Compose または WSL2上のNode.js / Python

## ディレクトリ構成

```text
.
├── backend/              # FastAPI、models、API、Context Builder、tests
├── frontend/             # React / TypeScript / Vite UI
├── compose.yaml          # 開発用 frontend / backend / postgres
├── .env.example          # 環境変数のひな型（秘密情報なし）
├── Makefile              # WSLでの短縮コマンド
└── README.md
```

v0.1ではベクトルDB、embedding、複雑なAgent Frameworkは導入していません。

## 環境変数

`.env.example`を`.env`にコピーして、環境に合わせて変更します。`.env`はGitへコミットしないでください。

| 変数 | 用途 | 例 |
| --- | --- | --- |
| `DATABASE_URL` | BackendのPostgreSQL接続先 | `postgresql+psycopg://storyweave:storyweave@postgres:5432/storyweave` |
| `OPENAI_BASE_URL` | OpenAI互換APIのベースURL | `http://host.docker.internal:11434/v1` |
| `OPENAI_API_KEY` | APIキー（ローカルサーバーでは任意） | `local-dev` |
| `OPENAI_MODEL` | 利用モデル名 | `qwen3.8:27b` |
| `BACKEND_HOST` / `BACKEND_PORT` | Backendのbind先 | `0.0.0.0` / `8000` |
| `FRONTEND_HOST` / `FRONTEND_PORT` | Viteのbind先 | `0.0.0.0` / `5173` |
| `VITE_API_BASE_URL` | ブラウザから到達するAPI URL | `http://localhost:8000/api` |
| `CORS_ORIGINS` | 許可するFrontend origin（カンマ区切り） | `http://localhost:5173` |
| `SEED_ENABLED` | Development seedを有効化 | `false` |
| `URL_FETCH_ALLOWED_HOSTS` | URL fetch許可先。空の場合もpublic IPだけを許可 |  |
| `WEB_RETRIEVAL_PROVIDER` | `auto`はstdio MCPを優先し、利用不能時だけ内蔵検索へ切替 | `auto` |
| `MCP_SEARCH_COMMAND` | Backendコンテナ内でMCPサーバを起動するPython | `/usr/local/bin/python` |
| `MCP_SEARCH_SERVER_PATH` | stdio MCPサーバのコンテナ内パス | `/opt/mcp-searxng/server.py` |
| `MCP_FETCH_MAX_CHARS` | `fetch_page`から受け取る本文の上限 | `8000` |
| `LLM_TIMEOUT_SECONDS` | ローカルLLMの生成timeout | `180` |

## PostgreSQL起動

Docker Composeを使う場合は、PostgreSQLだけを起動できます。

```bash
cp .env.example .env
docker compose up -d postgres
docker compose ps
```

WSLからWindows側で稼働するPostgreSQLへ接続する場合は、`DATABASE_URL`のホストをWindows側の到達可能なアドレスへ変更します。通常はComposeの`postgres`サービスを使う方が再現しやすい構成です。

## Migration

WSLまたはBackendコンテナ内で実行します。

```bash
docker compose run --rm backend alembic upgrade head
# または
cd backend
alembic upgrade head
```

Development seedを使う場合だけ`SEED_ENABLED=true`でBackendを起動します。空のDBにだけ初期例が入り、`false`の本番環境では投入されません。

## Backend起動

WSLのプロジェクトディレクトリ（`/mnt/d/OpenCodePJ002/storyweave`）から実行します。

```bash
cd /mnt/d/OpenCodePJ002/storyweave/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
alembic upgrade head
uvicorn app.main:app --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8000}" --reload
```

`GET /health`を開き、APIが起動していることを確認します。bind addressを`0.0.0.0`にすると、同一LANやTailscale経由から到達できるようになります。Windows Defender FirewallやTailscale ACLも別途確認してください。

## Frontend起動

```bash
cd /mnt/d/OpenCodePJ002/storyweave/frontend
npm ci
npm run dev -- --host "${FRONTEND_HOST:-0.0.0.0}" --port "${FRONTEND_PORT:-5173}"
```

FrontendのAPI向けURLなど、ブラウザへ公開してよい設定だけを`VITE_`接頭辞で管理します。LLM APIキーやDatabase URLをFrontendの環境変数へ置かないでください。

## Docker Compose起動

`compose.yaml`は`frontend`、`backend`、`postgres`の開発構成です。LLMサーバーはCompose外部にある前提です。

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

停止する場合は次を実行します。データを残すため、通常の停止ではvolumeを削除しません。

```bash
docker compose down
```

各コンテナのDockerfileを同梱しています。Backendコンテナは起動時に`alembic upgrade head`を実行してからAPIを開始します。

## ローカルLLM接続方法

LLMサーバーをホストOSまたは同一LAN上で起動し、OpenAI互換の`/v1`エンドポイントをBackendから到達可能にします。Compose上のBackendからWindowsホストのOllamaへ接続する例は次のとおりです。

```dotenv
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
OPENAI_API_KEY=local-dev
OPENAI_MODEL=qwen3.8:27b
```

WSL上でBackendを直接起動する場合は、Ollamaの待受アドレスとWSLからの名前解決に合わせて`http://127.0.0.1:11434/v1`またはホストのIPを指定します。Ollama、llama.cpp、vLLMの固有SDKをBackendへ持ち込まず、OpenAI互換のチャット呼び出しとして扱います。

### OpenAI互換API設定例

```dotenv
# OpenAI互換サーバーの例（URL末尾の /v1 はサーバー仕様に合わせる）
OPENAI_BASE_URL=http://192.168.1.20:8000/v1
OPENAI_API_KEY=replace-me
OPENAI_MODEL=Qwen3.8-27B
```

APIキーはログへ出力せず、Frontendへ渡しません。公開インターネット上のAPIを使う場合は、ネットワーク公開範囲、課金、利用規約を確認してください。

## Tailscale経由で利用する際の考え方

Tailscaleの自動設定は行いません。アプリをLAN/VPNから到達可能なホストで起動し、BackendとFrontendのbind address、Windows Firewall、Tailscale ACLを利用者のネットワーク方針に合わせて設定します。端末からはTailnet内のホスト名またはTailscale IPでFrontendへアクセスします。

インターネットへ直接公開する構成ではありません。認証はv0.1の対象外ですが、Tailnetの端末・ACL管理を前提にし、`CORS_ORIGINS`は実際に使うFrontend originだけを列挙してください。機密データを扱う場合は、Tailnet全体のアクセス権も確認してください。

## v0.1で実装済みの機能

- Project / Thread / Session / Message / Sourceの永続化とCRUD
- Sessionのstatus（採用、検討中、没、差し替え済み）、archive、pin管理
- Session単位のGFM Markdownチャット（表・リンク・コード対応）、履歴保持、エラー表示、SSE token streaming
- OpenAI互換LLMとの会話
- adopted Sessionのadoption_summaryの生成案表示、手動編集、保存
- 同一Thread内で採用済みsummaryだけを使う独立Context Builder
- Project、Thread、Session、summary、Messageの検索
- レスポンシブなPC 3ペイン相当UIとスマートフォンDrawer UI
- Health API、Alembic migration、Backend重要ロジックのテスト
- stdio MCPの`web_search`→`fetch_page`を使うWeb調査、回答ごとのSource保存、折りたたみURL表示
- MCP利用前のScheme、private IP、allowlist検査と、MCP検索0件時だけの内蔵検索フォールバック

## テスト

WSL上でBackendのContext Builder/APIテストとFrontendのコンポーネントテスト・本番ビルドを実行できます。

```bash
cd /mnt/d/OpenCodePJ002/storyweave/backend
source .venv/bin/activate
pytest -q

cd ../frontend
npm test
npm run build
```

## 今後追加予定の機能

PWA、認証・マルチユーザー、設定資料の編集支援、JavaScript描画ページ向け取得、より高度な検索を追加候補とします。v0.1ではAIによる設定資料の自動書換、embedding、ベクトルDB、原稿エディタ、Git連携、Agent Framework、公開Internet向け認証基盤は実装しません。

## ライセンス・運用メモ

個人のLAN/VPN利用を想定した開発用構成です。実運用のバックアップ、PostgreSQLの更新、LLMモデルのライセンス、Tailnetのアクセス権は利用環境の責任範囲で管理してください。
