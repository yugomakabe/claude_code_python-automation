# -*- coding: utf-8 -*-
"""
GAS関連コース 直接URL指定PDF保存
保存先: C:\\Users\\yugom\\Desktop\\GAS教材
"""

import logging
import os
import random
import time
from urllib.robotparser import RobotFileParser

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

BASE_URL = "https://terakoya.sejuku.net"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
USER_AGENT = "Mozilla/5.0 (compatible; LearningBot/1.0)"
OUTPUT_DIR = "C:\\Users\\yugom\\Desktop\\GAS教材"

TARGET_URLS = [
    "https://terakoya.sejuku.net/programs/192/chapters",
    "https://terakoya.sejuku.net/programs/109/chapters",
    "https://terakoya.sejuku.net/programs/194/chapters",
    "https://terakoya.sejuku.net/programs/195/chapters",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_robots() -> RobotFileParser:
    rp = RobotFileParser()
    rp.set_url(ROBOTS_URL)
    try:
        resp = requests.get(ROBOTS_URL, timeout=10, headers={"User-Agent": USER_AGENT})
        rp.parse(resp.text.splitlines())
        logger.info("robots.txt 読み込み完了")
    except Exception as e:
        logger.warning(f"robots.txt 読み込み失敗（全許可扱い）: {e}")
    return rp


def wait(label: str = ""):
    delay = random.uniform(1, 3)
    logger.info(f"待機 {delay:.1f}秒" + (f" [{label}]" if label else "") + "…")
    time.sleep(delay)


def safe_name(s: str, maxlen: int = 60) -> str:
    for ch in r'\/:*?"<>|':
        s = s.replace(ch, "_")
    return s.strip()[:maxlen]


def login(page) -> bool:
    logger.info("ログインモーダルを開きます")
    try:
        page.wait_for_selector("header, nav", timeout=15000)
    except PlaywrightTimeout:
        logger.error("ヘッダー描画タイムアウト")
        return False

    time.sleep(1)
    clicked = page.evaluate("""() => {
        let target = null;
        document.querySelectorAll('*').forEach(el => {
            if (el.children.length > 3) return;
            const t = (el.textContent || '').trim();
            if (t === 'ログインする' || t === 'ログイン') target = el;
        });
        if (target) { target.click(); return true; }
        return false;
    }""")
    if not clicked:
        logger.error("ログインボタンが見つかりません")
        return False

    try:
        page.wait_for_selector('input[name="email"]', timeout=10000)
    except PlaywrightTimeout:
        logger.error("ログインフォームの表示タイムアウト")
        return False

    wait("フォーム入力前")
    page.fill('input[name="email"]', os.getenv("TERAKOYA_EMAIL", ""))
    page.fill('input[name="password"]', os.getenv("TERAKOYA_PASSWORD", ""))
    time.sleep(1.5)

    clicked = False
    for btn in page.query_selector_all("button"):
        try:
            text = btn.inner_text().strip()
        except Exception:
            continue
        if "Google" not in text and "ログイン" in text:
            btn.click()
            clicked = True
            break

    if not clicked:
        logger.error("ログイン送信ボタンが見つかりません")
        return False

    try:
        page.wait_for_function(
            """() => !document.querySelector('input[name="email"]')""",
            timeout=15000,
        )
    except PlaywrightTimeout:
        logger.error("ログイン後の遷移タイムアウト")
        return False

    logger.info(f"ログイン完了: {page.url}")
    return True


def collect_links(page) -> list[dict]:
    items = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].map(a => ({
            text: (a.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 120),
            href: a.href || ''
        })).filter(l => l.href && !l.href.endsWith('#'));
    }""")
    results, seen = [], set()
    for l in items:
        if l["href"] in seen or BASE_URL not in l["href"]:
            continue
        seen.add(l["href"])
        results.append(l)
    return results


def save_pdf(page, url: str, path: str, rp: RobotFileParser) -> bool:
    if not rp.can_fetch(USER_AGENT, url):
        logger.warning(f"  robots.txt スキップ: {url}")
        return False
    try:
        page.goto(url, timeout=30000, wait_until="networkidle")
        time.sleep(1.5)
        page.pdf(path=path, print_background=True, format="A4")
        logger.info(f"  PDF保存: {os.path.basename(path)}")
        return True
    except PlaywrightTimeout as e:
        logger.error(f"  タイムアウト: {url} — {e}")
    except Exception as e:
        logger.error(f"  エラー: {url} — {e}")
    return False


def scrape_program(page, program_url: str, rp: RobotFileParser) -> int:
    # コース概要ページからタイトルを取得してフォルダ名に使う
    try:
        page.goto(program_url, timeout=30000, wait_until="networkidle")
        time.sleep(2)
    except Exception as e:
        logger.error(f"コースページ取得失敗: {e}")
        return 0

    title = page.title().split("|")[0].strip() or program_url.split("/")[-2]
    course_dir = os.path.join(OUTPUT_DIR, safe_name(title))
    os.makedirs(course_dir, exist_ok=True)
    logger.info(f"\n=== コース: {title} ===")
    logger.info(f"保存先: {course_dir}")

    wait("概要ページ")
    save_pdf(page, program_url, os.path.join(course_dir, "00_overview.pdf"), rp)

    all_links = collect_links(page)
    lesson_links = [l for l in all_links if "/lessons/" in l["href"]]
    if not lesson_links:
        lesson_links = [
            l for l in all_links
            if "/chapters/" in l["href"] and l["href"] != program_url
        ]
    logger.info(f"  レッスンリンク: {len(lesson_links)}件")

    if not lesson_links:
        logger.warning("  レッスンリンクが見つかりませんでした")
        return 0

    saved = 0
    for i, lesson in enumerate(lesson_links, 1):
        wait(f"レッスン {i}/{len(lesson_links)}")
        fname = f"{i:02d}_{safe_name(lesson['text']) or 'lesson'}.pdf"
        if save_pdf(page, lesson["href"], os.path.join(course_dir, fname), rp):
            saved += 1

    logger.info(f"  → {saved}/{len(lesson_links)} 件保存完了")
    return saved


def main():
    logger.info("=== GAS コース 直接URL指定 PDFダウンロード開始 ===")

    email = os.getenv("TERAKOYA_EMAIL", "")
    password = os.getenv("TERAKOYA_PASSWORD", "")
    if not email or not password or "your_email" in email:
        logger.error(".env に TERAKOYA_EMAIL / TERAKOYA_PASSWORD を設定してください")
        return

    rp = load_robots()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    wait("ブラウザ起動前")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        try:
            page.goto(BASE_URL, timeout=30000)
        except Exception as e:
            logger.error(f"接続エラー: {e}")
            browser.close()
            return

        if not login(page):
            browser.close()
            return

        wait("コース取得開始前")

        total = 0
        for url in TARGET_URLS:
            total += scrape_program(page, url, rp)

        browser.close()

    logger.info(f"\n=== 完了: 合計 {total} レッスンを PDF で保存 ===")
    logger.info(f"保存先: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
