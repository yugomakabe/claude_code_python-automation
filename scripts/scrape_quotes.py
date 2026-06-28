"""
Playwright スクレイパー
対象: https://quotes.toscrape.com/js （JavaScript描画ページ）
取得: 名言テキスト・著者名
出力: quotes_YYYYMMDD.md / quotes_YYYYMMDD.png
"""

import logging
import random
import time
from datetime import date
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TARGET_URL = "https://quotes.toscrape.com/js"
BASE_URL = "https://quotes.toscrape.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
USER_AGENT = "Mozilla/5.0 (compatible; LearningBot/1.0)"

today_str = date.today().strftime("%Y%m%d")
OUTPUT_DIR = "C:\\Users\\yugom\\学習\\claude_code\\python-automation"
MD_FILE = f"{OUTPUT_DIR}\\quotes_{today_str}.md"
PNG_FILE = f"{OUTPUT_DIR}\\quotes_{today_str}.png"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_robots(url: str) -> RobotFileParser:
    rp = RobotFileParser()
    rp.set_url(url)
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": USER_AGENT})
        rp.parse(resp.text.splitlines())
        logger.info("robots.txt を読み込みました")
    except Exception as e:
        logger.warning(f"robots.txt の読み込みに失敗（全URLを許可として扱います）: {e}")
    return rp


def wait():
    delay = random.uniform(1, 3)
    logger.info(f"待機中 ({delay:.1f}秒)…")
    time.sleep(delay)


def build_markdown(quotes: list[dict]) -> str:
    today_label = date.today().strftime("%Y年%m月%d日")
    lines = [
        "# 名言集 | quotes.toscrape.com",
        "",
        f"収集日: {today_label}  ",
        f"対象URL: {TARGET_URL}",
        "",
        f"取得件数: {len(quotes)}件",
        "",
        "---",
        "",
    ]
    for i, q in enumerate(quotes, 1):
        lines.append(f"## {i}.")
        lines.append("")
        lines.append(f"> {q['text']}")
        lines.append("")
        lines.append(f"— **{q['author']}**")
        lines.append("")
        if q.get("tags"):
            tags = " ".join(f"`{t}`" for t in q["tags"])
            lines.append(f"タグ: {tags}")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def main():
    logger.info("=== Playwright スクレイピング開始 ===")

    # robots.txt チェック
    rp = load_robots(ROBOTS_URL)
    if not rp.can_fetch(USER_AGENT, TARGET_URL):
        logger.error(f"robots.txt によりアクセス禁止: {TARGET_URL}")
        return

    wait()

    with sync_playwright() as pw:
        # headless=False でブラウザを画面に表示
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        try:
            logger.info(f"ページ移動: {TARGET_URL}")
            page.goto(TARGET_URL, timeout=30000)

            # JavaScriptで描画される名言要素を待機
            logger.info("JS描画の完了を待機中…")
            page.wait_for_selector("div.quote", timeout=15000)
            logger.info("描画完了")

            wait()

            # スクリーンショット保存
            page.screenshot(path=PNG_FILE, full_page=True)
            logger.info(f"スクリーンショット保存: {PNG_FILE}")

            # 名言データ取得
            quotes = []
            quote_elements = page.query_selector_all("div.quote")
            logger.info(f"{len(quote_elements)} 件の名言を検出")

            for el in quote_elements:
                text_el = el.query_selector("span.text")
                author_el = el.query_selector("small.author")
                tag_els = el.query_selector_all("a.tag")

                text = text_el.inner_text().strip().strip("“”") if text_el else ""
                author = author_el.inner_text().strip() if author_el else ""
                tags = [t.inner_text().strip() for t in tag_els]

                if text and author:
                    quotes.append({"text": text, "author": author, "tags": tags})

            logger.info(f"名言取得完了: {len(quotes)}件")

        except PlaywrightTimeout as e:
            logger.error(f"タイムアウトエラー: {e}")
            browser.close()
            return
        except Exception as e:
            logger.error(f"接続エラー: {e}")
            browser.close()
            return

        browser.close()

    if not quotes:
        logger.error("名言を取得できませんでした。終了します。")
        return

    # Markdown 保存
    md_content = build_markdown(quotes)
    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"Markdown 保存: {MD_FILE}")

    logger.info("=== 完了 ===")


if __name__ == "__main__":
    main()
