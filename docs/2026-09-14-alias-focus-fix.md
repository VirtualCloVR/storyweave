# Character Alias入力でフォーカスが外れる問題

2026-09-14、`http://192.168.11.7:18080/` に修正反映済み。

## 原因と修正

`frontend/src/StructuredContext.tsx` のAlias行のReact keyが
入力値を含む `${alias}-${index}` だった。文字が変わるたびにinputが
再マウントされ、フォーカスを失う。入力値に依存しない `key={index}` に修正。
このリストには並べ替え操作がなく、入力値は親のdraftで制御している。

## 検証

- 修正前の公開画面で `Anon` を連続入力すると `A` だけ入り、フォーカス消失を再現。
- 新しい回帰テストは修正前に `toHaveFocus()` で失敗し、修正後に成功。
  既存Aliasへの複数文字追加、新規Aliasへの英字入力、クリア、日本語compositionイベントで、
  同じinputとフォーカスが保持されることを検証。
- WSL Frontend全24テスト、本番ビルド、サーバー用Compose config成功。
- 反映後の公開画面を390 × 690で確認。未保存の新規Aliasへ `Anon`、続けて `ちゃん` を入力し、
  `Anonちゃん` と入力フォーカスの継続をDOMのactive状態で確認。
  検証データは保存せずにフォームを閉じた。iPhone実機のキーボードは未検証。
- Frontendのみ更新。Backend/Postgresは継続稼働し、database/llmともhealth=ok。

## 反映と復旧

サーバーに転送した変更は `frontend/src/StructuredContext.tsx` のみ。
バックアップは `/home/bap4/apps/storyweave/backups/20260914-alias-focus/` に
修正前の `StructuredContext.tsx` と `database.dump` を保存。
旧イメージは `storyweave-frontend:before-alias-focus-20260914`。

復旧時はバックアップのTSXを元の場所へ戻し、
`docker compose -f compose.yaml -f compose.server.yaml up -d --build --no-deps frontend` を実行する。
今回の変更にはDB復元・マイグレーションは不要。git commit/pushはしていない。

開いているページを再読込すると修正が読み込まれる。
