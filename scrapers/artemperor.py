from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash
import re

BASE = "https://artemperor.tw"
URL  = "https://artemperor.tw/resources"
SOURCE = "artemperor"
KEYS = ["徵件","補助","申請","Open Call","徵選","駐村","展覽","招募","截止","收件","至","Deadline"]
def _kw(s): return any(k in (s or "") for k in KEYS)
DATE_RE = re.compile(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2}(?:\s*\d{1,2}:\d{2})?)")

async def _detail(link):
    html = await fetch_html(link, js=False)
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
    html = await fetch_html(URL, js=False)
    soup = BeautifulSoup(html, "lxml")
    a_tags = soup.select("a[href*='/resources/']")
    if not a_tags:
        html = await fetch_html(URL, js=True)
        soup = BeautifulSoup(html, "lxml")
        a_tags = soup.select("a[href*='/resources/']")

    rows, seen = [], set()
    for a in a_tags:
        href = a.get("href",""); 
        if not href: continue
        link = urljoin(BASE, href)
        if "/resources/" not in link: continue
        if link in seen: continue
        seen.add(link)

        title = a.get_text(strip=True)
        t2, deadline_text = await _detail(link)
        title = t2 or title
        if not title: continue

        item = normalize({
            "title": title,
            "organization": "典藏｜Art Emperor",
            "category": "資源/徵件/補助",
            "location": "Taiwan/International",
            "deadline_text": deadline_text,
            "link": link,
            "source": SOURCE,
        })
        item["hash"] = make_hash(item["title"], item["source"], item["link"])
        rows.append(item)

    print(f"[DEBUG] {SOURCE}: {len(rows)}")
    return rows
