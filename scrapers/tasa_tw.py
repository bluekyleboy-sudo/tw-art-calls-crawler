# scrapers/tasa_tw.py
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash
from pipelines.normalize import parse_to_iso
import re

BASE = "https://tasa-tw.org"
URL = "https://tasa-tw.org/news-zh/open-call-zh"
SOURCE = "tasa_tw"

IDX_TITLES = {"獎項徵選","藝術進駐 open call","工作機會","即將到期"}
DROP_LINK_SUBSTR = ["/news-zh/tasa-news", "/news-zh/past"]
DATE_RE = re.compile(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})(?:\s*(\d{1,2}:\d{2}))?")

def canon(url: str) -> str:
    u = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    path = u.path.rstrip("/") or "/"
    return urlunparse((u.scheme, u.netloc, path, u.params, urlencode(q, doseq=True), ""))

def extract_range(text: str):
    """從內文抓 start/end（盡量），抓不到就回空"""
    if not text: return "",""
    # 「自 A 至 B」或「A 至 B」
    m = re.search(r"(自|自從)?\s*(20\d{2}[./-]\d{1,2}[./-]\d{1,2}).{0,10}至.{0,10}(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", text)
    if m:
        return parse_to_iso(m.group(2)), parse_to_iso(m.group(3))
    dates = DATE_RE.findall(text)
    if len(dates) >= 2:
        return parse_to_iso(dates[0][0]), parse_to_iso(dates[-1][0])
    if len(dates) == 1:
        # 只有一個日期，視為截止
        return "", parse_to_iso(dates[0][0])
    return "",""

async def _detail(link: str):
    html = await fetch_html(link, js=False)
    if not html or len(html) < 200:
        html = await fetch_html(link, js=True)
    s = BeautifulSoup(html, "lxml")
    title_node = s.select_one("h1") or s.title
    title = title_node.get_text(strip=True) if title_node else ""
    text = s.get_text(" ", strip=True)
    start_iso, end_iso = extract_range(text)
    return title, start_iso, end_iso

async def run():
    html = await fetch_html(URL, js=False)
    soup = BeautifulSoup(html, "lxml")
    a_tags = soup.select("a[href*='/news-zh/'], a[rel='bookmark'], article a[href]")
    if not a_tags:
        html = await fetch_html(URL, js=True)
        soup = BeautifulSoup(html, "lxml")
        a_tags = soup.select("a[href]")

    rows, seen = [], set()
    for a in a_tags:
        href = a.get("href","")
        if not href: 
            continue
        link = canon(urljoin(BASE, href))
        if BASE not in link:
            continue
        if any(x in link for x in DROP_LINK_SUBSTR):
            continue

        title_hint = a.get_text(strip=True)
        if title_hint in IDX_TITLES:   # 移除索引頁
            continue

        if link in seen:
            continue
        seen.add(link)

        t2, start_iso, end_iso = await _detail(link)
        title = t2 or title_hint
        if not title:
            continue

        item = normalize({
            "title": title,
            "organization": "台灣藝文空間連線",   # ← 修正名稱
            "category": "Open Call/徵件",
            "location": "Taiwan",
            "start_date": start_iso,
            "deadline_date": end_iso,
            "deadline": end_iso,       # 保留相容欄位
            "link": link,
            "source": SOURCE,
        })
        item["hash"] = make_hash(item["title"], item["source"], item["link"])
        rows.append(item)

    print(f"[DEBUG] {SOURCE}: {len(rows)}")
    return rows
