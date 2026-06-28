"""
立命館大学 入試情報サイト スクレイパー
対象: 2027年度 一般入試の変更点・注意点
"""

import logging
import random
import time
from datetime import date
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://admission.ritsumei.ac.jp"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
USER_AGENT = "Mozilla/5.0 (compatible; LearningBot/1.0)"
OUTPUT_FILE = f"books_{date.today().strftime('%Y%m%d')}.md"

# 一般選抜の主要ページを直接起点として追加
SEED_URLS = [
    BASE_URL,
    f"{BASE_URL}/admission/general/point.html",
    f"{BASE_URL}/admission/#general",
    f"{BASE_URL}/application/guide.html",
]

KEYWORDS_2027 = ["2027", "2027年度"]
KEYWORDS_GENERAL = ["一般入試", "一般選抜", "一般"]
# セクション本文に含まれていれば変更点・注意点と判断するキーワード
KEYWORDS_CHANGE = [
    "変更", "変わり", "新設", "廃止", "追加", "改定", "改訂",
    "注意", "ご注意", "重要", "必ず", "ポイント",
    "増え", "減り", "拡大", "縮小", "以降", "より",
    "今年度", "2027年度", "2027",
]

NON_HTML_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".png", ".jpg", ".jpeg", ".gif"}

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
        rp.read()
        logger.info("robots.txt を読み込みました")
    except Exception as e:
        logger.warning(f"robots.txt の読み込みに失敗: {e}（全URLを許可として扱います）")
    return rp


def is_allowed(rp: RobotFileParser, url: str) -> bool:
    return rp.can_fetch(USER_AGENT, url)


def fetch(session: requests.Session, url: str) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return BeautifulSoup(resp.text, "lxml")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"接続エラー: {url} — {e}")
        raise
    except requests.exceptions.Timeout as e:
        logger.error(f"タイムアウト: {url} — {e}")
        raise
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTPエラー: {url} — {e}")
        return None


def wait():
    delay = random.uniform(1, 3)
    logger.info(f"待機中 ({delay:.1f}秒)…")
    time.sleep(delay)


def is_html_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return not any(path.endswith(ext) for ext in NON_HTML_EXTS)


def is_target_link(text: str, href: str) -> bool:
    """一般選抜に関連するページへのリンクを収集（2027の有無は問わない）"""
    combined = text + href
    # URLパスに /admission/general/ を含む場合は無条件で対象
    if "/admission/general/" in href or "/admission/#general" in href:
        return True
    has_general = any(k in combined for k in KEYWORDS_GENERAL)
    return has_general


def collect_links(soup: BeautifulSoup, base: str, visited: set) -> list[dict]:
    links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript"):
            continue
        full_url = urljoin(base, href)
        parsed = urlparse(full_url)
        # フラグメントを除いたURLで重複排除
        url_no_frag = parsed._replace(fragment="").geturl()
        if urlparse(full_url).netloc != urlparse(base).netloc:
            continue
        if not is_html_url(full_url):
            continue
        if url_no_frag in visited or url_no_frag in seen:
            continue
        text = a.get_text(strip=True)
        if is_target_link(text, href):
            seen.add(url_no_frag)
            links.append({"url": url_no_frag, "text": text})
    return links


def is_change_section(heading: str, body: str) -> bool:
    """見出しまたは本文に変更点・注意点キーワードを含むか"""
    combined = heading + body
    return any(k in combined for k in KEYWORDS_CHANGE)


def extract_change_sections(soup: BeautifulSoup, url: str) -> dict:
    title = soup.title.string.strip() if soup.title else "（タイトル不明）"

    main = (
        soup.find("main")
        or soup.find(id="main")
        or soup.find(id="content")
        or soup.find("article")
        or soup.find("div", class_=lambda c: c and "content" in c)
        or soup.body
    )
    if not main:
        return {"url": url, "title": title, "sections": []}

    headings = main.find_all(["h1", "h2", "h3", "h4"])
    sections = []
    for h in headings:
        h_text = h.get_text(strip=True)
        if not h_text:
            continue
        body_parts = []
        for sib in h.find_next_siblings():
            if sib.name in ("h1", "h2", "h3", "h4"):
                break
            text = sib.get_text(separator=" ", strip=True)
            if text:
                body_parts.append(text)
        body = " ".join(body_parts)[:600]

        if is_change_section(h_text, body):
            sections.append({"heading": h_text, "body": body})

    # 見出しが一切ない場合は本文全体を変更キーワードでチェック
    if not headings:
        body_text = main.get_text(separator="\n", strip=True)
        if any(k in body_text for k in KEYWORDS_CHANGE):
            sections.append({"heading": "（本文）", "body": body_text[:800]})

    return {"url": url, "title": title, "sections": sections}


def build_markdown(pages: list[dict]) -> str:
    today = date.today().strftime("%Y年%m月%d日")
    lines = [
        "# 立命館大学 2027年度 一般入試 変更点・注意点まとめ",
        "",
        f"収集日: {today}  ",
        f"対象サイト: {BASE_URL}",
        "",
        "> 各セクションは「変更・注意・重要・ポイント」等のキーワードを含む箇所のみ抽出しています。",
        "",
        "---",
        "",
    ]

    if not pages:
        lines.append("対象ページが見つかりませんでした。")
        return "\n".join(lines)

    for i, page in enumerate(pages, 1):
        lines.append(f"## {i}. {page['title']}")
        lines.append("")
        lines.append(f"URL: {page['url']}  ")
        lines.append("")
        for sec in page["sections"]:
            lines.append(f"### {sec['heading']}")
            lines.append("")
            if sec["body"]:
                lines.append(sec["body"])
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    logger.info("=== スクレイピング開始（変更点・注意点モード）===")

    rp = load_robots(ROBOTS_URL)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    candidate_links: list[dict] = []
    visited: set[str] = set()
    pages: list[dict] = []

    # 起点ページを順に取得：変更点抽出 + リンク収集を同時に行う
    for seed in SEED_URLS:
        if not is_allowed(rp, seed):
            logger.warning(f"robots.txt によりスキップ: {seed}")
            continue
        logger.info(f"起点ページ取得: {seed}")
        try:
            soup = fetch(session, seed)
        except requests.exceptions.RequestException:
            logger.error(f"起点ページへの接続失敗: {seed}")
            continue
        if not soup:
            continue
        visited.add(seed)

        # 起点ページ自体から変更点セクションを抽出
        info = extract_change_sections(soup, seed)
        if info["sections"]:
            if not any(p["url"] == seed for p in pages):
                pages.append(info)
                logger.info(f"  → 変更点セクション {len(info['sections'])}件 抽出（起点）")

        new_links = collect_links(soup, BASE_URL, visited)
        for lk in new_links:
            if lk["url"] not in {l["url"] for l in candidate_links}:
                candidate_links.append(lk)
        wait()

    logger.info(f"候補リンク合計: {len(candidate_links)}件")

    for link in candidate_links:
        url = link["url"]
        if url in visited:
            continue
        visited.add(url)

        if not is_allowed(rp, url):
            logger.warning(f"robots.txt によりスキップ: {url}")
            continue

        wait()
        logger.info(f"取得中: {url}  [{link['text']}]")

        try:
            soup = fetch(session, url)
        except requests.exceptions.RequestException:
            logger.error(f"接続エラーのためスキップ: {url}")
            continue
        if not soup:
            continue

        info = extract_change_sections(soup, url)
        if info["sections"]:
            pages.append(info)
            logger.info(f"  → 変更点セクション {len(info['sections'])}件 抽出")
        else:
            logger.info("  → 変更点・注意点セクションなし（スキップ）")

        if len(pages) >= 15:
            logger.info("取得上限(15ページ)に達したため終了します")
            break

    md_content = build_markdown(pages)
    output_path = f"C:\\Users\\yugom\\学習\\claude_code\\python-automation\\{OUTPUT_FILE}"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    logger.info(f"=== 完了: {OUTPUT_FILE} に {len(pages)}ページ分を保存しました ===")


if __name__ == "__main__":
    main()
