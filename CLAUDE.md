# Python業務自動化 学習プロジェクト

## プロジェクト概要

Playwright を使ったWebスクレイピングを中心とした業務自動化の学習リポジトリ。
現在は侍テラコヤ（terakoya.sejuku.net）の Claude Code 教材を PDF として保存するスクリプトを運用している。

## 環境

- 言語: Python 3.14（Windows 11）
- ブラウザ自動化: Playwright（Chromium）
- パッケージ管理: pip（グローバル環境、.venv は非使用）

```
python-automation/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env                  # 認証情報（Git管理外）
├── scripts/
│   ├── scrape_terakoya.py            # コース概要ページをPDF保存
│   └── scrape_terakoya_chapters.py   # 全コースの全レッスンをPDF保存（メイン）
└── pdf_output/           # scrape_terakoya.py の出力先（Git管理外）
```

## スクリプト仕様

### scrape_terakoya_chapters.py（メインスクリプト）

- ログイン後、`/home` と `/programs` から Claude Code 関連コースを収集
- 各コースの全レッスンを A4 PDF としてフルページ保存
- 保存先: `C:\Users\yugom\Desktop\ClaudeCode教材\[コース名]\`
- ファイル名: `00_overview.pdf`、`01_レッスン名.pdf`、…
- headless=True（ブラウザウィンドウは非表示）

### scrape_terakoya.py

- ログイン後、Claude Code 関連ページをページタイトルでPDF保存
- 保存先: `pdf_output/`（リポジトリ内、Git管理外）
- headless=False（ブラウザウィンドウ表示あり）

## 実行方法

```bash
# 依存パッケージのインストール（初回のみ）
pip install -r requirements.txt
playwright install chromium

# メインスクリプト実行
python scripts/scrape_terakoya_chapters.py
```

## 認証情報（.env）

```
TERAKOYA_EMAIL=your_email@example.com
TERAKOYA_PASSWORD=your_password
```

## 技術的な注意点

### React SPA のログイン
テラコヤは React SPA のため、Playwright の標準セレクタ（`text=` 等）が効かない場合がある。
「ログインする」ボタンは `page.evaluate()` でJS経由クリック、送信ボタンは `query_selector_all("button")` でテキストフィルタして `element.click()` する。

### page.pdf() は headless 必須
`page.pdf()` は Chromium の headless モードでのみ動作する。`headless=False` にすると実行時エラーになる。

### Python 3.12+ の文字列エスケープ制限
ドキュメント文字列内の Windowsパス（`\U`、`\D` 等）は Python 3.12 以降でSyntaxWarning、3.14 ではSyntaxError になる。バックスラッシュは `\\` でエスケープするか raw文字列を使う。

### robots.txt 準拠
全スクリプトでアクセス前に `RobotFileParser` で確認し、禁止URLはスキップする。

## 依存パッケージ

| パッケージ | 用途 |
|---|---|
| playwright | Chromiumブラウザ自動化 |
| python-dotenv | .env 読み込み |
| requests | robots.txt 取得 |
| pyee / greenlet | playwright の内部依存 |
