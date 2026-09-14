# PC向け作成ダイアログの拡大

`frontend/src/styles.css` に981px以上の画面向けルールを追加。
Project / Thread / Sessionの共通作成ダイアログを調整した。

- 幅430px → 640px、余白22px → 32px。
- 入力文字12px → 16px、見出し18px → 26px。
- ラベル14px、作成ボタン高さ46px。画面高さを超える内容はスクロール可能。
- 980px以下には今回の拡大ルールを適用しない。

検証: WSL Frontend 24テスト、本番ビルド、Compose config成功。
ブラウザーで1920 × 1080のSessionフォーム（640 × 約303px）、
1366 × 768のメモ付きThreadフォーム（640 × 約488px）、
390 × 690のスマホフォーム（幅350px、横はみ出しなし）を確認。
検証時には作成ボタンを送信せず、既存データを変更していない。

反映先は `http://192.168.11.7:18080/`。
CSSのみ転送し、ComposeのFrontendだけを再ビルド・更新。
バックアップは `/home/bap4/apps/storyweave/backups/20260914-desktop-dialog/` に
`styles.css` と `database.dump`、旧イメージは
`storyweave-frontend:before-desktop-dialog-20260914`。
復旧はCSSを戻してFrontendのみ再ビルドする。DB復元は不要。

開いている作成フォームの未保存入力は、ページ再読込で失われるため注意。
ユーザーの入力中タブには操作を行わず、独立した検証タブを使用した。
