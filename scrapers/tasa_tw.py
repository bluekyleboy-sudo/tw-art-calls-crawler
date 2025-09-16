# scrapers/tasa_tw.py  ← 直接整檔覆蓋這份

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash
import re

BASE = "https://tasa-tw.org"
URL = "https://tasa-tw.org/news-zh/open-call-zh"
SOURCE = "tasa_tw"

# 拿來偵測截止/申請等關鍵字（抓就近的日期字串或備援）
KEYS = ["截止", "收件", "申請", "報名", "至", "Deadline", "Open Call"]
DATE_RE = re.compile(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}(?:\s*\d{1,2}:\d{2})?)")

def _kw(s: str | None) -> bool:
    return any(k in (s or "") for k in KEYS)

def canon(url: str) -> str:
    """把連結規一化：去掉 utm_*、移除尾端斜線與 fragment，避免同文不同參數重複。"""
    u = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    path = u.path.rstrip("/") or "/"
    return urlunparse((u.scheme, u.netloc, path, u.params, urlencode(q, doseq=True), ""))

async def _detail(link: str):
    """有些截止日在內文；抓內頁並回傳標題與一小段含關鍵字或日期的文字"""
    html = await fetch_html(link, js=False)
    if not html or len(html) < 200:
        html = await fetch_html(link, js=True)
    s = BeautifulSoup(html, "lxml")
    title_node = s.select_one("h1") or s.title
    title = title_node.get_text(strip=True) if title_node else ""
    text = s.get_text(" ", strip=True)
    seg = None
    for k in KEYS:
        if k in text:
            i = text.find(k)
            seg = text[max(0, i - 60): i + 120]
            break
    if not seg:
        m = DATE_RE.search(text)
        seg = m.group(0) if m else ""
    return title, seg

async def run():
    # 先不用等 selector：直接純 HTML 抓；若抓不到再退回用 JS
    html = await fetch_html(URL, js=False)
    soup = BeautifulSoup(html, "lxml")
    a_tags = soup.select("a[href*='/news-zh/'], a[rel='bookmark'], article a[href]")
    if not a_tags:
        html = await fetch_html(URL, js=True)
        soup = BeautifulSoup(html, "lxml")
        a_tags = soup.select("a[href]")

    rows, seen = [], set()
    for a in a_tags:
        href = a.get("href", "")
        if not href:
            continue
        link = urljoin(BASE, href)
        if BASE not in link:
            continue

        # —— 連結正規化，避免同一篇文章不同 query 造成重複 —— #
        link = canon(link)
        if link in seen:
            continue
        seen.add(link)

        # —— 過濾非徵件頁（活動/新聞、過去活動等）—— #
        title_hint = a.get_text(strip=True)
        if any(x in link for x in ["/news-zh/tasa-news", "/news-zh/past"]):
            continue
        if any(x in (title_hint or "") for x in ["活動/新聞", "過去活動"]):
            continue

        # 進內頁補齊標題與截止字串
        t2, deadline_text = await _detail(link)
        title = t2 or title_hint
        if not title:
            continue

        item = normalize({
            "title": title,
            "organization": "TASA 台灣聲響藝術",
            "category": "Open Call/徵件",
            "location": "Taiwan",
            "deadline_text": deadline_text,
            "link": link,
            "source": SOURCE,
        })
        item["hash"] = make_hash(item["title"], item["source"], item["link"])
        rows.append(item)

    print(f"[DEBUG] {SOURCE}: {len(rows)}")
    return rows
