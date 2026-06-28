# Python業務自動化 学習プロジェクト

## プロジェクト概要

Playwright を使った侍テラコヤ（terakoya.sejuku.net）教材のPDF一括保存を中心とした自動化リポジトリ。
ログイン・robots.txt準拠・headlessスクレイピングの実践学習。

## 環境

- 言語: Python 3.14（Windows 11）
- ブラウザ自動化: Playwright（Chromium、headless）
- パッケージ管理: pip（グローバル環境、.venv は非使用）

## ディレクトリ構成

```
python-automation/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env                         # 認証情報（Git管理外）
├── scripts/
│   ├── scrape_terakoya.py               # Claude Code コース概要をPDF保存（旧版）
│   ├── scrape_terakoya_chapters.py      # Claude Code 全レッスンをPDF保存
│   ├── scrape_specific_courses.py       # キーワードで複数コースグループを保存
│   └── scrape_gas_direct.py             # GAS 4コースを直接URL指定で保存
└── pdf_output/                  # scrape_terakoya.py の出力先（Git管理外）
```

## スクリプト仕様

### scrape_terakoya_chapters.py
- `/home` と `/programs` から Claude Code 関連コースを収集（キーワード: "claude", "Claude Code"）
- 各コースの全レッスンを A4 PDF で保存
- 保存先: `C:\\Users\\yugom\\Desktop\\ClaudeCode教材\\[コース名]\\`
- ファイル構成: `00_overview.pdf`、`01_レッスン名.pdf`、…

### scrape_specific_courses.py
- `COURSE_GROUPS` 定義に従い、キーワードマッチで複数グループを一括処理
- 現在の対象と保存先:

| グループ | キーワード | 保存先 |
|---|---|---|
| GAS | "生成AIの基礎" | `C:\\Users\\yugom\\Desktop\\GAS教材\\` |
| Docker | "Docker" | `C:\\Users\\yugom\\Desktop\\Docker教材\\` |
| Git/GitHub | "Git", "GitHub" | `C:\\Users\\yugom\\Desktop\\Git・GitHub教材\\` |

- 注意: コース名に "GAS" が含まれないコースはこのスクリプトでは検出できない

### scrape_gas_direct.py
- `TARGET_URLS` に列挙したURLを直接スクレイピング
- GAS の 4コース（program/192, 109, 194, 195）用
- 保存先: `C:\\Users\\yugom\\Desktop\\GAS教材\\`
- ページタイトルからフォルダ名を自動生成

### scrape_terakoya.py（旧版）
- ページタイトルをファイル名にして `pdf_output/` へ保存
- headless=False（ウィンドウ表示あり）— 旧実装のため参照用

## 実行方法

```bash
# 初回セットアップ
pip install -r requirements.txt
playwright install chromium

# Claude Code 全教材
python scripts/scrape_terakoya_chapters.py

# GAS / Docker / Git 教材（キーワード検索）
python scripts/scrape_specific_courses.py

# GAS 特定4コース（直接URL指定）
python scripts/scrape_gas_direct.py
```

## 認証情報（.env）

```
TERAKOYA_EMAIL=your_email@example.com
TERAKOYA_PASSWORD=your_password
```

## 技術的な注意点

### React SPA のログイン
テラコヤは React SPA のため、Playwright の `text=` セレクタが効かない。
「ログインする」DIV は `page.evaluate()` で JS 経由クリック、送信ボタンは
`query_selector_all("button")` でテキストフィルタして `element.click()` する。
フォーム入力後に `time.sleep(1.5)` を入れて React の state 更新（ボタン有効化）を待つ。

### page.pdf() は headless 必須
`page.pdf()` は Chromium headless モードでのみ動作。`headless=False` にすると実行時エラー。

### Python 3.12+ の文字列エスケープ制限
ドキュメント文字列内の Windows パス（`\U`、`\D` 等）は Python 3.14 で SyntaxError。
バックスラッシュは `\\` でエスケープするか、raw 文字列（`r"..."`）を使う。

### robots.txt 準拠
全スクリプトで `RobotFileParser` によるアクセス可否チェックを実施。禁止 URL はスキップ。

### キーワードマッチの限界
`scrape_specific_courses.py` はコース名の部分一致で振り分けるため、
コース名にキーワードを含まない場合は検出されない（例: "GAS" を含まない GAS コース）。
その場合は `scrape_gas_direct.py` のように直接 URL を指定して対応する。

## 依存パッケージ

| パッケージ | 用途 |
|---|---|
| playwright | Chromium ブラウザ自動化 |
| python-dotenv | .env 読み込み |
| requests | robots.txt 取得 |
| pyee / greenlet | playwright の内部依存 |
