# scrapers/artemperor.py
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize, parse_to_iso
from pipelines.dedupe import make_hash
import re

BASE = "https://artemperor.tw"
URL  = "https://artemperor.tw/resources"
SOURCE = "artemperor"

DATE_RE = re.compile(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})(?:\s*(\d{1,2}:\d{2}))?")
RANGE_RE = re.compile(r"(自|自從)?\s*(20\d{2}[./-]\d{1,2}[./-]\d{1,2}).{0,14}至.{0,14}(20\d{2}[./-]\d{1,2}[./-]\d{1,2})")

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

def clean_tail(t: str) -> str:
    # 移除「— 非池中藝術網」等尾綴
    return re.sub(r"[–—\-﹣]\s*非池中藝術網.*$", "", t).strip()

def pick_title(soup: BeautifulSoup, fallback: str):
    og = soup.select_one("meta[property='og:title']")
    if og and og.get("content"):
        t = clean_tail(og["content"].strip())
        if t: return t
    h1 = soup.select_one("h1")
    if h1 and h1.get_text(strip=True):
        return clean_tail(h1.get_text(strip=True))
    if soup.title and soup.title.get_text(strip=True):
        return clean_tail(soup.title.get_text(strip=True))
    return clean_tail(fallback)

async def _detail(link: str, idx_title: str):
    html = await fetch_html(link, js=False)
    if not html or len(html) < 200:
        html = await fetch_html(link, js=True)
    s = BeautifulSoup(html, "lxml")
    real_title = pick_title(s, idx_title)
    text = s.get_text(" ", strip=True)
    start_iso, end_iso = extract_range(text)
    return real_title, start_iso, end_iso

async def run():
    html = await fetch_html(URL, js=False)
    soup = BeautifulSoup(html, "lxml")
    a_tags = soup.select("a[href*='/resources/']")
    if not a_tags:
        html = await fetch_html(URL, js=True)
        soup = BeautifulSoup(html, "lxml")
        a_tags = soup.select("a[href*='/resources/']")

    rows, seen = [], set()
    for a in a_tags:
        href = a.get("href","")
        if not href: continue
        link = urljoin(BASE, href)
        if "/resources/" not in link: continue
        if link in seen: continue
        seen.add(link)

        idx_title = a.get_text(strip=True)
        real_title, start_iso, end_iso = await _detail(link, idx_title)
        if not real_title: 
            continue

        item = normalize({
            "title": real_title,
            "organization": "典藏｜Art Emperor",
            "category": "資源/徵件/補助",
            "location": "Taiwan/International",
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
