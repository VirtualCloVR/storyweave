# スマホのThread一覧が1件に見える問題

## 調査結果

写真の対象は `http://192.168.11.7:18080/`、Compose配置先は
`/home/bap4/apps/storyweave`。2026-09-14に確認・修正反映済み。

`MyGO!!!!!` のThreadは削除・上書きされていなかった。調査時のAPIは
「あらりつ拒食症ss」「らなたき年齢操作ss」「愛音生誕祭ss」の3件を返した。
作成APIは新規レコードを追加し、一覧APIは更新日時の降順で全件を返す。

原因はモバイルCSSでProject/Thread欄をドロワーの高さ44%、Session欄を56%に
固定していたこと。390 × 690のChromeで、ThreadボタンのY座標は271、310、349、
各高さ36px、Project/Thread欄の下端は約336pxだった。古い項目が欄の下に隠れ、
その欄だけのスクロールが必要だった。iPhone実機のSafariでは未検証。

## 修正

`frontend/src/styles.css` の980px以下の画面向けルールを追加。
ドロワー全体を縦スクロールさせ、Project/Thread欄とSession欄は内容に応じた高さにする。
スマホの余白を縮め、640px以下ではドロワーの上端を54pxのヘッダーに合わせた。
データ保存処理とデスクトップの3ペイン構成は変更していない。

## 検証

- WSL Backend: 45 tests passed。追加テストはThread連続作成で既存Thread、Session、採用要約が保持されることを検証。
- WSL Frontend: 23 tests passed。本番ビルドとサーバー用Compose configも成功。
- ローカル専用Project `検証用 Thread一覧 2026-09-14` でUIから3件のThreadを作成。
  以前のThreadへの切替、再読込後の3件保持を確認。この検証Projectはローカルに残している。
- 390 × 690で3件すべて表示。390 × 500でもドロワーが163pxスクロールし、
  下端のSession作成ボタンからフォームを開けた。デスクトップ表示も確認。
- 公開サーバーでも390 × 690で対象の3件すべてが表示範囲内にあり、クリック可能と確認。
  「愛音生誕祭ss」を選択し、既存Sessionが表示されることを確認。
- 反映前後のDB data-only dumpを比較し、データ変更なし
  （pg_dumpのランダムなrestrict/unrestrict行は比較から除外）。
- 反映後 `/api/health`: database=ok、llm=ok。
  Frontendのみ更新し、Backend/Postgresの稼働継続と公開bind `192.168.11.7:18080` を確認。

## 反映と復旧

サーバーへ転送した変更ファイルは `frontend/src/styles.css` のみ。
`docker compose -f compose.yaml -f compose.server.yaml up -d --build --no-deps frontend` で反映。
既存のv0.2作業ツリーを保ち、git commit/pushは行っていない。

バックアップ: `/home/bap4/apps/storyweave/backups/20260914-thread-navigation/`

- `styles.css`: 修正前CSS
- `database.dump`: pg_dump custom format
- `data-before.sql` / `data-after.sql`: 反映前後のデータ照合用
- 旧Frontendイメージ: `storyweave-frontend:before-thread-navigation-20260914`

表示修正を戻す場合は、上記CSSを `frontend/src/styles.css` へ戻し、Frontendのみ再ビルドする。
この修正にはDB復元・マイグレーションは不要。

ユーザー側では開いているページを再読込すると新しいCSSが読み込まれる。
