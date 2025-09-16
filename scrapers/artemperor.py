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

def extract_range(text: str):
    if not text: return "",""
    m = re.search(r"(自|自從)?\s*(20\d{2}[./-]\d{1,2}[./-]\d{1,2}).{0,14}至.{0,14}(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", text)
    if m:
        return parse_to_iso(m.group(2)), parse_to_iso(m.group(3))
    dates = DATE_RE.findall(text)
    if len(dates) >= 2:
        return parse_to_iso(dates[0][0]), parse_to_iso(dates[-1][0])
    if len(dates) == 1:
        return "", parse_to_iso(dates[0][0])
    return "",""

def pick_better_title(soup: BeautifulSoup, fallback: str):
    # 優先 og:title → h1 → 內容區第一個 h2/strong/b 有關鍵詞的文字
    og = soup.select_one("meta[property='og:title']")
    if og and og.get("content"):
        t = og["content"].strip()
        if t and t != fallback:
            return t
    h1 = soup.select_one("h1")
    if h1 and h1.get_text(strip=True) and h1.get_text(strip=True) != fallback:
        return h1.get_text(strip=True)

    content = soup.select_one("article, .content, .post, .entry, .post-content, .article")
    if content:
        for sel in ["h2","strong","b","p"]:
            node = content.select_one(sel)
            if node:
                txt = node.get_text(" ", strip=True)
                # 常見尾詞視為標題
                if any(txt.endswith(suf) for suf in ["徵件","招募","補助","駐村","Open Call","計畫","計劃","獎助"]):
                    return txt
                if len(txt) > 6:
                    return txt
    # 最後備援：title 標籤
    if soup.title and soup.title.get_text(strip=True):
        t = soup.title.get_text(strip=True)
        if t:
            return t
    return fallback

async def _detail(link: str, idx_title: str):
    html = await fetch_html(link, js=False)
    if not html or len(html) < 200:
        html = await fetch_html(link, js=True)
    s = BeautifulSoup(html, "lxml")
    real_title = pick_better_title(s, idx_title)
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
