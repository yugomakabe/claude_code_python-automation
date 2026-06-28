# -*- coding: utf-8 -*-
"""
侍テラコヤ 特定コース一括PDF保存スクリプト

保存対象:
  GAS コース群  → C:\\Users\\yugom\\Desktop\\GAS教材
  Docker コース → C:\\Users\\yugom\\Desktop\\Docker教材
  Git/GitHub    → C:\\Users\\yugom\\Desktop\\Git・GitHub教材
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

# ── 対象コースグループ定義 ────────────────────────────────────────────────────
# keywords: コース名に含まれるキーワード（いずれか一致で対象）
COURSE_GROUPS = [
    {
        "label": "GAS",
        "keywords": ["GAS", "生成AIの基礎"],
        "output_dir": "C:\\Users\\yugom\\Desktop\\GAS教材",
    },
    {
        "label": "Docker",
        "keywords": ["Docker"],
        "output_dir": "C:\\Users\\yugom\\Desktop\\Docker教材",
    },
    {
        "label": "Git/GitHub",
        "keywords": ["Git", "GitHub"],
        "output_dir": "C:\\Users\\yugom\\Desktop\\Git・GitHub教材",
    },
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── ユーティリティ ────────────────────────────────────────────────────────────

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
    msg = f"待機 {delay:.1f}秒" + (f" [{label}]" if label else "")
    logger.info(f"{msg}…")
    time.sleep(delay)


def safe_name(s: str, maxlen: int = 60) -> str:
    for ch in r'\/:*?"<>|':
        s = s.replace(ch, "_")
    return s.strip()[:maxlen]


def match_group(text: str) -> dict | None:
    """コース名がどのグループに属するか返す。どれにも合わなければ None。"""
    lower = text.lower()
    for group in COURSE_GROUPS:
        if any(kw.lower() in lower for kw in group["keywords"]):
            return group
    return None


# ── ログイン ──────────────────────────────────────────────────────────────────

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


# ── コース探索 ────────────────────────────────────────────────────────────────

def collect_all_links(page) -> list[dict]:
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


def find_target_programs(page, rp: RobotFileParser) -> dict[str, list[dict]]:
    """/home と /programs から対象コースを収集し、グループ別に分類して返す。"""
    result: dict[str, list[dict]] = {g["label"]: [] for g in COURSE_GROUPS}
    seen: set[str] = set()

    for url in [f"{BASE_URL}/home", f"{BASE_URL}/programs"]:
        if not rp.can_fetch(USER_AGENT, url):
            continue
        try:
            page.goto(url, timeout=25000, wait_until="networkidle")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"アクセス失敗 {url}: {e}")
            continue

        for l in collect_all_links(page):
            href, text = l["href"], l["text"]
            if href in seen:
                continue
            if "/programs/" not in href or "/chapters" not in href:
                continue
            group = match_group(text)
            if group is None:
                continue
            seen.add(href)
            result[group["label"]].append({"url": href, "name": text})
            logger.info(f"  [{group['label']}] {text[:70]}")

        wait()

    return result


# ── レッスン保存 ──────────────────────────────────────────────────────────────

def find_lesson_links(page, program_url: str) -> list[dict]:
    try:
        page.goto(program_url, timeout=30000, wait_until="networkidle")
        time.sleep(2)
    except Exception as e:
        logger.error(f"章一覧ページ取得失敗: {e}")
        return []

    all_links = collect_all_links(page)
    lesson_links = [l for l in all_links if "/lessons/" in l["href"]]
    if not lesson_links:
        lesson_links = [
            l for l in all_links
            if "/chapters/" in l["href"] and l["href"] != program_url
        ]
    logger.info(f"  レッスンリンク: {len(lesson_links)}件")
    return lesson_links


def save_page_as_pdf(page, url: str, path: str, rp: RobotFileParser) -> bool:
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


def scrape_program(page, program: dict, output_dir: str, rp: RobotFileParser) -> int:
    course_dir = os.path.join(output_dir, safe_name(program["name"]))
    os.makedirs(course_dir, exist_ok=True)
    logger.info(f"\n=== コース: {program['name']} ===")
    logger.info(f"保存先: {course_dir}")

    wait("概要ページ")
    save_page_as_pdf(page, program["url"], os.path.join(course_dir, "00_overview.pdf"), rp)

    lesson_links = find_lesson_links(page, program["url"])
    if not lesson_links:
        logger.warning("  レッスンリンクが見つかりませんでした")
        return 0

    saved = 0
    for i, lesson in enumerate(lesson_links, 1):
        wait(f"レッスン {i}/{len(lesson_links)}")
        fname = f"{i:02d}_{safe_name(lesson['text']) or 'lesson'}.pdf"
        if save_page_as_pdf(page, lesson["href"], os.path.join(course_dir, fname), rp):
            saved += 1

    logger.info(f"  → {saved}/{len(lesson_links)} 件保存完了")
    return saved


# ── メイン ────────────────────────────────────────────────────────────────────

def main():
    logger.info("=== 侍テラコヤ 特定コース一括PDFダウンロード開始 ===")

    email = os.getenv("TERAKOYA_EMAIL", "")
    password = os.getenv("TERAKOYA_PASSWORD", "")
    if not email or not password or "your_email" in email:
        logger.error(".env に TERAKOYA_EMAIL / TERAKOYA_PASSWORD を設定してください")
        return

    rp = load_robots()
    for g in COURSE_GROUPS:
        os.makedirs(g["output_dir"], exist_ok=True)

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

        wait("コース一覧取得前")

        grouped = find_target_programs(page, rp)

        for group in COURSE_GROUPS:
            label = group["label"]
            programs = grouped[label]
            logger.info(f"\n{'='*50}")
            logger.info(f"グループ [{label}]: {len(programs)} コース発見")

        total_saved = 0
        for group in COURSE_GROUPS:
            for prog in grouped[group["label"]]:
                count = scrape_program(page, prog, group["output_dir"], rp)
                total_saved += count

        browser.close()

    logger.info(f"\n=== 完了: 合計 {total_saved} レッスンを PDF で保存 ===")
    for g in COURSE_GROUPS:
        logger.info(f"  [{g['label']}] → {g['output_dir']}")


if __name__ == "__main__":
    main()
