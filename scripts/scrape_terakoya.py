# -*- coding: utf-8 -*-
"""
Playwright スクレイパー - テラコヤオンライン
対象: https://terakoya.sejuku.net
取得: Claude Code に関する教材ページを PDF 保存
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

CLAUDE_KEYWORDS = ["claude", "Claude Code", "claude code"]
OUTPUT_DIR = os.path.join(
    "C:\\Users\\yugom\\学習\\claude_code\\python-automation", "pdf_output"
)

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
        logger.info("robots.txt を読み込みました")
    except Exception as e:
        logger.warning(f"robots.txt の読み込みに失敗（全URLを許可として扱います）: {e}")
    return rp


def wait(label: str = ""):
    delay = random.uniform(1, 3)
    logger.info(f"待機中 ({delay:.1f}秒){' [' + label + ']' if label else ''}…")
    time.sleep(delay)


def safe_filename(title: str) -> str:
    for ch in r'\/:*?"<>|':
        title = title.replace(ch, "_")
    return title[:80].strip()


def is_claude_related(text: str) -> bool:
    lower = text.lower()
    return any(k.lower() in lower for k in CLAUDE_KEYWORDS)


def login(page) -> bool:
    """ログインモーダルを開いて認証する。成功したら True を返す。"""
    logger.info("ログインモーダルを開きます")

    # ヘッダー描画を待つ
    try:
        page.wait_for_selector("header, nav", timeout=15000)
    except PlaywrightTimeout:
        logger.error("ヘッダーの描画タイムアウト")
        return False
    time.sleep(1)

    # 「ログインする」DIVをJS経由でクリック（React SPAのためtext=セレクタは使わない）
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
        logger.error("ログインボタンが見つかりませんでした")
        return False

    # モーダル内のメールアドレス欄が出るまで待機
    try:
        page.wait_for_selector('input[name="email"]', timeout=10000)
    except PlaywrightTimeout:
        logger.error("ログインフォームの表示タイムアウト")
        return False

    wait("フォーム入力前")

    email = os.getenv("TERAKOYA_EMAIL", "")
    password = os.getenv("TERAKOYA_PASSWORD", "")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', password)

    logger.info("認証情報を入力しました。ログインボタンをクリックします")

    # React SPAのためPlaywrightのelement.click()でマウスイベントを正しく発火させる
    # 「ログイン」テキストを持つボタンをPython側でフィルタしてクリック
    clicked = False
    buttons = page.query_selector_all("button")
    for btn in buttons:
        try:
            text = btn.inner_text().strip()
        except Exception:
            continue
        # 「ログイン」を含み「Google」を含まないボタンが送信ボタン
        if "Google" not in text and "ログイン" in text:
            btn.click()
            clicked = True
            logger.info(f"クリック: {text!r}")
            break

    if not clicked:
        logger.error("ログイン送信ボタンが見つかりませんでした")
        return False

    # ログイン後の遷移を待つ（メールアドレス欄が消えるまで）
    try:
        page.wait_for_function(
            """() => !document.querySelector('input[name="email"]')""",
            timeout=15000,
        )
    except PlaywrightTimeout:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "debug_login_fail.png"))
        logger.error("ログイン後の遷移タイムアウト（debug_login_fail.png を確認）")
        return False

    logger.info(f"ログイン完了: {page.url}")
    return True


def collect_claude_links_from_page(page) -> list[dict]:
    """現在のページから Claude Code 関連リンクを収集する（重複なし）。"""
    links_data = page.evaluate("""() => {
        return [...document.querySelectorAll('a')].map(a => ({
            text: (a.textContent || '').trim().slice(0, 100),
            href: a.href || ''
        })).filter(l => l.href && !l.href.startsWith('#'));
    }""")
    results = []
    seen = set()
    for l in links_data:
        href = l["href"]
        text = l["text"]
        if href in seen or BASE_URL not in href:
            continue
        if is_claude_related(text) or is_claude_related(href):
            seen.add(href)
            results.append({"url": href, "text": text})
            logger.info(f"  候補: [{text[:60]}] {href}")
    return results


def find_claude_pages(page, rp: RobotFileParser) -> list[dict]:
    """複数の教材ページから Claude Code 関連リンクを収集する。"""
    # ログイン後は /home にいるのでまずそこのリンクをスキャン
    logger.info("現在のページ(/home)からリンクを収集")
    claude_links = collect_claude_links_from_page(page)
    seen_urls = {l["url"] for l in claude_links}

    # 追加で確認する教材系ページ（正しいURL）
    extra_pages = [
        f"{BASE_URL}/curriculum",
        f"{BASE_URL}/programs",
        f"{BASE_URL}/lessons",
    ]
    for url in extra_pages:
        if not rp.can_fetch(USER_AGENT, url):
            logger.warning(f"robots.txt によりスキップ: {url}")
            continue
        try:
            logger.info(f"追加スキャン: {url}")
            page.goto(url, timeout=20000, wait_until="networkidle")
            time.sleep(2)
            # 404ページ判定：URLが変わっていないのにコンテンツが404か確認
            actual_path = page.evaluate("() => window.location.pathname")
            if "404" in page.title() or actual_path != url.replace(BASE_URL, ""):
                logger.warning(f"  → 404またはリダイレクト（スキップ）")
                continue
            logger.info(f"  → タイトル: {page.title()}")
            new_links = collect_claude_links_from_page(page)
            for l in new_links:
                if l["url"] not in seen_urls:
                    seen_urls.add(l["url"])
                    claude_links.append(l)
        except Exception as e:
            logger.warning(f"  → アクセス失敗: {e}")

    wait("教材リンク収集完了後")
    return claude_links


def save_as_pdf(page, title: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = safe_filename(title) + ".pdf"
    path = os.path.join(OUTPUT_DIR, filename)
    page.pdf(
        path=path,
        format="A4",
        print_background=True,
        margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"},
    )
    return path


def main():
    logger.info("=== テラコヤ スクレイピング開始 ===")

    email = os.getenv("TERAKOYA_EMAIL", "")
    password = os.getenv("TERAKOYA_PASSWORD", "")
    if not email or not password or "your_email" in email:
        logger.error(".env に TERAKOYA_EMAIL と TERAKOYA_PASSWORD を設定してください")
        return

    rp = load_robots()
    if not rp.can_fetch(USER_AGENT, BASE_URL):
        logger.error(f"robots.txt によりアクセス禁止: {BASE_URL}")
        return

    wait("ブラウザ起動前")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        # トップページを開く
        try:
            logger.info(f"トップページへ移動: {BASE_URL}")
            page.goto(BASE_URL, timeout=30000)
        except PlaywrightTimeout as e:
            logger.error(f"タイムアウト: {e}")
            browser.close()
            return
        except Exception as e:
            logger.error(f"接続エラー: {e}")
            browser.close()
            return

        # ログイン
        if not login(page):
            page.screenshot(path=os.path.join(OUTPUT_DIR, "debug_login_fail.png") if os.path.exists(OUTPUT_DIR) else "debug_login_fail.png")
            browser.close()
            return

        wait("教材ページ移動前")

        # Claude Code 関連ページを探す
        claude_links = find_claude_pages(page, rp)
        logger.info(f"Claude Code 関連リンク: {len(claude_links)} 件")

        if not claude_links:
            logger.warning("Claude Code 関連の教材が見つかりませんでした")
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            page.screenshot(path=os.path.join(OUTPUT_DIR, "debug_no_results.png"), full_page=True)
            logger.info("現在のページのスクリーンショットを保存しました")
            browser.close()
            return

        # 各ページを PDF 保存
        saved_count = 0
        for link in claude_links:
            url = link["url"]
            if not rp.can_fetch(USER_AGENT, url):
                logger.warning(f"robots.txt によりスキップ: {url}")
                continue

            wait(f"PDF保存前")
            try:
                logger.info(f"取得中: {url}")
                page.goto(url, timeout=30000, wait_until="networkidle")
                time.sleep(1)
                title = page.title() or link["text"] or "untitled"
                pdf_path = save_as_pdf(page, title)
                logger.info(f"  → PDF保存: {pdf_path}")
                saved_count += 1
            except PlaywrightTimeout as e:
                logger.error(f"タイムアウト: {url} — {e}")
            except Exception as e:
                logger.error(f"エラー: {url} — {e}")

        browser.close()

    logger.info(f"=== 完了: {saved_count} 件の PDF を保存しました ===")
    logger.info(f"保存先: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
