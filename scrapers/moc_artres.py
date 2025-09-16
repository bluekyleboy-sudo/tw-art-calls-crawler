from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash
import re

BASE = "https://artres.moc.gov.tw"
URL  = "https://artres.moc.gov.tw/zh/calls/list"
SOURCE = "moc_artres"
KEYS = ["截止","收件","申請期限","申請時間","Deadline","至","Open Call","駐村","徵選"]
DATE_RE = re.compile(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}(?:\s*\d{1,2}:\d{2})?)")

def _kw(s): return any(k in (s or "") for k in KEYS)

async def _detail(link):
    # 先試純 HTML，失敗再用 JS
    try:
        html = await fetch_html(link, js=False)
    except Exception:
        html = await fetch_html(link, js=True)
    if not html or len(html) < 200:
        html = await fetch_html(link, js=True)
    s = BeautifulSoup(html, "lxml")
    title = (s.select_one("h1") or s.title)
    title = title.get_text(strip=True) if title else ""
    text = s.get_text(" ", strip=True)
    seg = None
    for k in KEYS:
        if k in text:
            i = text.find(k); seg = text[max(0,i-60): i+140]; break
    if not seg:
        m = DATE_RE.search(text); seg = m.group(0) if m else ""
    return title, seg

async def run():
    # A. 先嘗試純 HTML（快），若 403/失敗，再用 JS 載入
    try:
        html = await fetch_html(URL, js=False)
    except Exception:
        html = await fetch_html(URL, js=True)
    if not html or len(html) < 200:
        html = await fetch_html(URL, js=True)

    soup = BeautifulSoup(html, "lxml")
    a_tags = soup.select("a[href*='/calls/'], a[href*='/zh/calls/']")
    rows, seen = [], set()

    for a in a_tags:
        href = a.get("href",""); 
        if not href: 
            continue
        link = urljoin(BASE, href)
        if "/calls/" not in link or link in seen:
            continue
        seen.add(link)

        title = a.get_text(strip=True)
        t2, deadline_text = await _detail(link)
        title = t2 or title
        if not title:
            continue

        item = normalize({
            "title": title,
            "organization": "文化部 Art Residency 平台",
            "category": "駐村/徵選",
            "location": "Taiwan/International",
            "deadline_text": deadline_text,
            "link": link,
            "source": SOURCE,
        })
        item["hash"] = make_hash(item["title"], item["source"], item["link"])
        rows.append(item)

    print(f"[DEBUG] {SOURCE}: {len(rows)}")
    return rows
