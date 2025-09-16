# scrapers/tasa_tw.py
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from scrapers.base import fetch_html
from pipelines.normalize import normalize, parse_to_iso
from pipelines.dedupe import make_hash
import re

BASE = "https://tasa-tw.org"
URL = "https://tasa-tw.org/news-zh/open-call-zh"
SOURCE = "tasa_tw"

# 要排除的索引標題與路徑（索引頁）
IDX_TITLES = {"獎項徵選","藝術進駐 open call","工作機會","即將到期","TASA 過去活動"}
DROP_LINK_SUBSTR = [
    "/news-zh/open-call-zh",
    "/news-zh/award-zh",
    "/news-zh/tasa-news",
    "/news-zh/past",
    "/news-zh/tasa-past-events",
]

DATE_RE = re.compile(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})(?:\s*(\d{1,2}:\d{2}))?")
RANGE_RE = re.compile(r"(自|自從)?\s*(20\d{2}[./-]\d{1,2}[./-]\d{1,2}).{0,10}至.{0,10}(20\d{2}[./-]\d{1,2}[./-]\d{1,2})")

def canon(url: str) -> str:
    u = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    path = u.path.rstrip("/") or "/"
    return urlunparse((u.scheme, u.netloc, path, u.params, urlencode(q, doseq=True), ""))

def extract_range(text: str):
    if not text: return "",""
    m = RANGE_RE.search(text)
    if m:
        return parse_to_iso(m.group(2)), parse_to_iso(m.group(3))
    ds = DATE_RE.findall(text)
    if len(ds) >= 2:
        return parse_to_iso(ds[0][0]), parse_to_iso(ds[-1][0])
    if len(ds) == 1:
        return "", parse_to_iso(ds[0][0])
    return "",""

async def _detail(link: str):
    html = await fetch_html(link, js=False)
    if not html or len(html) < 200:
        html = await fetch_html(link, js=True)
    s = BeautifulSoup(html, "lxml")
    title_node = s.select_one("h1") or s.title
    title = title_node.get_text(strip=True) if title_node else ""
    txt = s.get_text(" ", strip=True)
    start_iso, end_iso = extract_range(txt)
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
        if title_hint in IDX_TITLES:
            continue

        if link in seen:
            continue
        seen.add(link)

        real_title, start_iso, end_iso = await _detail(link)
        title = real_title or title_hint
        if not title:
            continue
        # 題名再保險過濾一次
        if any(x in title for x in ["過去活動","活動/新聞"]):
            continue

        item = normalize({
            "title": title,
            "organization": "台灣藝文空間連線",   # ← 正式名稱
            "category": "Open Call/徵件",
            "location": "Taiwan",
            "start_date": start_iso,
            "deadline_date": end_iso,
            "deadline": end_iso,
            "link": link,
            "source": SOURCE,
        })
        item["hash"] = make_hash(item["title"], item["source"], item["link"])
        rows.append(item)

    print(f"[DEBUG] {SOURCE}: {len(rows)}")
    return rows
