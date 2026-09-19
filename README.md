# Storyweave

作品ごとの検討事項を「採用・検討中・没」として管理し、採用した内容だけを次の相談へ引き継ぐ、創作・SS相談専用のWebワークスペースです。ChatGPTの汎用クローンではなく、`Project → Thread → Session → Message` の構造を中心に設計します。
ローカルLLMとの接続を前提とした構成になっており、Uncensoredモデルを利用した自由な創作支援を目指しています。

## Quickstart (Docker Compose)

要件: Docker / Docker Compose、任意で OpenAI互換LLM (Ollama / llama.cpp / vLLM等)。

```bash
cp .env.example .env
# .env の OPENAI_BASE_URL / OPENAI_MODEL を手元のLLMに合わせて編集
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

ブラウザで `http://localhost:8080` を開きます。停止は `docker compose down` (volumeは残るためデータ保持)。

別ホスト公開用override (loopback既定、DB/Backendはホスト公開なし):

```bash
docker compose -f compose.yaml -f compose.server.yaml up -d --build
```

`.env` の `STORYWEAVE_BIND_ADDRESS` (例 `<server-ip>`) と `STORYWEAVE_HTTP_PORT` でbind先を変更します。

## v0.2 Structured Contextの方針

自宅LANまたはVPN (Tailscale等) 内での利用を想定しています。認証・マルチユーザー・公開インターネット向け運用は対象外です。LLMはアプリに内蔵せず、OpenAI互換HTTP APIへ接続します。

採用済みSessionの`adoption_summary`だけを、同じThreadの別SessionのLLMコンテキストへ投入します。`considering`、`rejected`、`superseded`は投入せず、`archived`は採用知識としての有効性と分離して扱います。

v0.2では、全Workspaceで再利用するGlobal Character Sheet、Threadから参照するCast、Thread LocalなScene Sheetを追加しました。Character FactはCastに明示されたCharacterのうち、`always_include`または現在・直近のUser発言で名前/Aliasが検出されたものだけを投入します。Scene Factは同じThreadのものだけを常時投入します。

Context Plannerは文字数Budget内で`Character → Scene → adopted Canon → Web → Recent History`を組み立てます。Canonが大きい場合だけThread Digestと関連性の高いadoption summaryへ圧縮します。Digestは`source_hash`でfreshnessを判定する派生Cacheであり、Character Fact、Scene Fact、`adoption_summary`が常にSource of Truthです。

## Architecture

```text
Browser (React / Vite)
        │ REST API / SSE
        ▼
FastAPI backend ── SQLAlchemy 2 / Alembic ── PostgreSQL
        │
        └── OpenAI-compatible LLM endpoint (Compose外部)
        └── stdio MCP SearXNG server (任意、Compose外部または同梱マウント)
```

BackendがProject、Thread、Session、Message、Sourceを永続化します。FrontendからDatabaseへ直接接続しません。Context Builder、URL fetchの安全対策、LLM接続はBackend側に置き、将来のプロバイダ差し替えに依存しない境界を保ちます。

## 使用技術

- Frontend: React、TypeScript、Vite
- Backend: Python (>=3.11)、FastAPI、SQLAlchemy 2系、Alembic
- Database: PostgreSQL 16
- LLM: OpenAI互換API (Ollama / llama.cpp / vLLM等)
- 開発・検証: Docker Compose または手元のNode.js / Python

## ディレクトリ構成

```text
.
├── backend/              # FastAPI、models、API、Context Builder、tests
├── frontend/             # React / TypeScript / Vite UI
├── mcp-searxng/          # stdio MCP web_search/fetch_page サーバ
├── compose.yaml          # frontend(nginx) / backend / postgres
├── compose.server.yaml   # サーバー公開用override
├── .env.example          # 環境変数のひな型 (秘密情報なし)
├── Makefile              # 短縮コマンド
└── README.md
```

v0.2ではベクトルDB、embedding、複雑なAgent Frameworkは導入していません。

## 環境変数

`.env.example`を`.env`にコピーして使います。`.env`はGitへコミットしないでください。

| 変数 | 用途 | 例 |
| --- | --- | --- |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_PORT` | PostgreSQL設定 | `storyweave` / `change-me` / `5432` |
| `DATABASE_URL` | BackendのPostgreSQL接続先 | `postgresql+psycopg://storyweave:change-me@postgres:5432/storyweave` |
| `OPENAI_BASE_URL` | OpenAI互換APIのベースURL | `http://host.docker.internal:11434/v1` |
| `OPENAI_API_KEY` | APIキー (ローカルサーバーでは任意) | `local-dev` |
| `OPENAI_MODEL` | 利用モデル名 | `your-model-name` |
| `BACKEND_HOST` / `BACKEND_PORT` | Backendのbind先 | `0.0.0.0` / `8000` |
| `FRONTEND_HOST` / `FRONTEND_PORT` | Frontend開発用bind / Compose公開ポート | `0.0.0.0` / `8080` |
| `VITE_API_BASE_URL` | ブラウザから到達するAPI URL (Composeでは同一オリジン) | `/api` |
| `VITE_BACKEND_TARGET` | Vite dev proxy転送先 (devのみ) | `http://localhost:8000` |
| `CORS_ORIGINS` | 許可するFrontend origin (カンマ区切り) | `http://localhost:5173,http://127.0.0.1:5173` |
| `SEED_ENABLED` | サンプルseedを有効化 (空DB時のみ) | `false` |
| `URL_FETCH_ALLOWED_HOSTS` | URL fetch許可先。空でもpublic IPのみ許可 |  |
| `URL_FETCH_TIMEOUT_SECONDS` / `URL_FETCH_MAX_BYTES` | fetch timeout/上限 | `10` / `2000000` |
| `WEB_RETRIEVAL_PROVIDER` | `auto`はstdio MCP優先、不可時のみ内蔵検索 | `auto` |
| `WEB_SEARCH_ENDPOINT` | 内蔵検索fallbackのendpoint | `https://html.duckduckgo.com/html/` |
| `MCP_SEARCH_COMMAND` | MCPサーバ起動用Python | `/usr/local/bin/python` |
| `MCP_SEARCH_SERVER_PATH` | stdio MCPサーバパス | `/opt/mcp-searxng/server.py` |
| `MCP_SEARCH_TIMEOUT_SECONDS` / `MCP_FETCH_MAX_CHARS` | MCP timeout/本文上限 | `20` / `8000` |
| `SEARXNG_URL` | Backendから到達するSearXNG。空でMCP検索無効 | `http://host.docker.internal:8080` |
| `LLM_TIMEOUT_SECONDS` | LLM生成timeout | `180` |
| `CONTEXT_BUDGET_CHARS` | Prompt全体の文字数Budget | `24000` |
| `CONTEXT_HISTORY_MAX_CHARS` | Recent Conversation上限 | `10000` |
| `CONTEXT_WEB_MAX_CHARS` | Web Context上限 | `5000` |
| `CONTEXT_DIGEST_TARGET_CHARS` | Canon Digest目標文字数 | `4000` |
| `STORYWEAVE_BIND_ADDRESS` / `STORYWEAVE_HTTP_PORT` | server override用bind | `127.0.0.1` / `18080` |

`config.py` の既定値はコンテナパス (`/usr/local/bin/python`, `/opt/mcp-searxng/server.py`) に合わせてあり、`.env` / Compose環境変数で上書きできます。`SEARXNG_URL` が空の場合はMCP検索を使わず、内蔵検索fallbackまたは検索なしで動作します。

## PostgreSQL起動

```bash
cp .env.example .env
docker compose up -d postgres
docker compose ps
```

別ホストのPostgreSQLを使う場合は`DATABASE_URL`を変更します。通常はComposeの`postgres`を使う方が再現しやすい構成です。

## Migration

```bash
docker compose run --rm backend alembic upgrade head
# または
cd backend
alembic upgrade head
```

`SEED_ENABLED=true`でBackendを起動すると、空のDBにだけ最小サンプル (Project `MyGO ワンライト` / Thread `愛音事故SS` / Session `交通事故描写の検討`) が入ります。`false`では投入されません。

## Backend起動 (Composeを使わない場合)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
alembic upgrade head
uvicorn app.main:app --host "${BACKEND_HOST:-0.0.0.0}" --port "${BACKEND_PORT:-8000}" --reload
```

`GET /api/health`で起動を確認します。

## Frontend起動 (Composeを使わない場合)

```bash
cd frontend
npm ci
npm run dev -- --host "${FRONTEND_HOST:-0.0.0.0}" --port "${FRONTEND_PORT:-5173}"
```

既定の`/api`はVite proxyが`VITE_BACKEND_TARGET` (既定`http://localhost:8000`) へ転送します。別のBackendを使う場合だけ`VITE_API_BASE_URL`で上書きしてください。Composeのnginx構成は常に同一オリジンの`/api`を使います。

Frontendの`VITE_`変数はブラウザ公開前提の設定のみに使います。LLM APIキーやDatabase URLをFrontend側に置かないでください。

## Docker Compose起動

`compose.yaml`は`frontend` (nginx静的配信) / `backend` / `postgres`構成です。LLMサーバーとSearXNGはCompose外部サービスを指定できます。

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
docker compose logs -f backend
docker compose down
```

Backendコンテナは起動時に`alembic upgrade head`を実行してからAPIを開始します。

## ローカルLLM接続方法

LLMサーバーをホストOSまたは同一LAN上で起動し、OpenAI互換のエンドポイントをBackendから到達可能にします。Compose上のBackendからホストのOllamaへ接続する例:

```dotenv
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
OPENAI_API_KEY=local-dev
OPENAI_MODEL=your-model-name
```

別の例 (URL末尾の`/v1`はサーバー仕様に合わせる):

```dotenv
OPENAI_BASE_URL=http://<llm-host>:8000/v1
OPENAI_API_KEY=replace-me
OPENAI_MODEL=your-model-name
```

APIキーはログへ出力せず、Frontendへ渡しません。Ollama、llama.cpp、vLLMの固有SDKをBackendへ持ち込まず、OpenAI互換チャット呼び出しとして扱います。

## Web検索 (SearXNG / MCP) について

任意機能です。`SEARXNG_URL`と`MCP_SEARCH_COMMAND`/`MCP_SEARCH_SERVER_PATH`が有効な場合のみstdio MCPの`web_search`→`fetch_page`を使います。未設定の場合は内蔵検索fallbackまたは検索なしで動作します。MCP利用前にはScheme・private IP・allowlist検査を行います。

`backend/scripts/`のsmoke/seedスクリプトはローカル開発用ヘルパーです。通常利用には不要で、`--api-base`または`STORYWEAVE_API`でBackendを指定できます。

## LAN/VPN経由で利用する際の考え方

Tailscale等の自動設定は行いません。アプリをLAN/VPNから到達可能なホストで起動し、bind address、Firewall、ACLを利用者のネットワーク方針に合わせて設定します。

インターネットへ直接公開する構成ではありません。認証はv0.2の対象外のため、到達可能なネットワーク範囲の管理を前提にし、`CORS_ORIGINS`は実際に使うFrontend originだけを列挙してください。

## v0.2で実装済みの機能

- Project / Thread / Session / Message / Sourceの永続化とCRUD
- Sessionのstatus (採用、検討中、没、差し替え済み)、archive、pin管理
- Session単位のGFM Markdownチャット、履歴保持、エラー表示、SSE token streaming
- OpenAI互換LLMとの会話
- adopted Sessionのadoption_summaryの生成案表示、手動編集、保存
- 同一Thread内で採用済みsummaryだけを使う独立Context Builder
- Project、Thread、Session、summary、Messageの検索
- レスポンシブなPC 3ペイン相当UIとスマートフォンDrawer UI
- Health API、Alembic migration、Backend重要ロジックのテスト
- stdio MCPの`web_search`→`fetch_page`を使うWeb調査、回答ごとのSource保存、折りたたみURL表示
- MCP利用前のScheme、private IP、allowlist検査と、MCP検索0件時だけの内蔵検索フォールバック
- Global Character Library (AliasとKey/Value Fact)、Thread Cast参照、Thread Local Scene Sheet
- DeterministicなNFKC/casefold/substring Character選択とcompact KV serialization
- Context Budget、Canon Digest cache、lexical Relevant Canon、失敗時のdeterministic fallback
- Character/Scene/Canon/History/Webの投入内容とサイズを確認できるContext Inspector/Preview API

## テスト

```bash
cd backend
python3 -m pytest -q

cd ../frontend
npm test
npm run build
```

## License

MIT License

Copyright (c) 2026 Virtual CloVR

詳細は`LICENSE`を参照してください。

サンプルseed内の作品名等 (`MyGO ワンライト`等) は動作確認用の例示であり、各権利者に帰属します。

## 運用メモ

個人のLAN/VPN利用を想定した開発用構成です。実運用のバックアップ、PostgreSQLの更新、LLMモデルのライセンス、ネットワークのアクセス権は利用環境の責任範囲で管理してください。
