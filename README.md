# Python 業務自動化

Playwright を使って侍テラコヤの教材ページを PDF として一括保存するスクリプト群です。

## スクリプト一覧

| スクリプト | 対象コース | 保存先 |
|---|---|---|
| `scrape_terakoya_chapters.py` | Claude Code 全教材 | `Desktop/ClaudeCode教材/` |
| `scrape_specific_courses.py` | GAS・Docker・Git/GitHub（キーワード検索） | 各 `Desktop/教材名/` |
| `scrape_gas_direct.py` | GAS 4コース（直接URL指定） | `Desktop/GAS教材/` |

## セットアップ

**Python 3.12 以上が必要です。**

```bash
pip install -r requirements.txt
playwright install chromium
```

`.env` ファイルを作成して認証情報を記載します。

```
TERAKOYA_EMAIL=your_email@example.com
TERAKOYA_PASSWORD=your_password
```

## 実行

```bash
# Claude Code 教材
python scripts/scrape_terakoya_chapters.py

# GAS / Docker / Git・GitHub 教材
python scripts/scrape_specific_courses.py

# GAS 特定コース（直接URL指定）
python scripts/scrape_gas_direct.py
```

各スクリプトは headless Chromium で動作するため、実行中にブラウザウィンドウは表示されません。
進捗はターミナルのログで確認できます。

## 注意事項

- `.env` ファイルは Git 管理対象外です（`.gitignore` で除外済み）
- スクレイピング間隔は 1〜3 秒のランダム待機を設けています
- アクセス前に `robots.txt` を確認し、禁止 URL はスキップします
- `page.pdf()` は Chromium headless モード専用です
