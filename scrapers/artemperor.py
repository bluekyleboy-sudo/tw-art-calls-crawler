from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

BASE = "https://artemperor.tw"
URL = "https://artemperor.tw/resources"
SOURCE = "artemperor"
KEYS = ["徵件","補助","申請","Open Call","徵選","駐村","展覽","招募","截止","收件","至","Deadline"]

def _kw(text: str) -> bool:
    return any(k in (text or "") for k in KEYS)

async def _scrape_detail(link: str):
    html = await fetch_html(link, js=True)
    soup = BeautifulSoup(html, "lxml")
    txt = soup.get_text(" ", strip=True)
    for k in KEYS:
        if k in txt:
            i = txt.find(k)
            return txt[max(0, i-60): i+120]
    import re
    m = re.search(r"(\d{4}[./-]\d{1,2}[./-]\d{1,2}(\s*\d{1,2}:\d{2})?)", txt)
    return m.group(0) if m else None

async def run():
    html = await fetch_html(
        URL, js=True,
        wait_selector="a[href*='/resources/']"
    )
    soup = BeautifulSoup(html, "lxml")
    rows, seen = [], set()

    blocks = soup.select(".resource-item, .list-item, article, .card, .item, li, .resources a[href]")
    if not blocks:
        blocks = soup.find_all(["article","div","li","a"])

    for b in blocks:
        a = b if getattr(b, "name", "") == "a" else b.select_one("a[href]")
        if not a:
            continue
        href = a.get("href","")
        if "/resources/" not in href:
            continue
        title = a.get_text(strip=True)
        link  = urljoin(BASE, href)
        if not title or link in seen:
            continue
        seen.add(link)

        text_all = (b.get_text(" ", strip=True) if getattr(b, "name", "") != "a" else title) or ""

        # 不做丟棄過濾；若附近沒有，就抓內頁
        deadline_text = None
        for sel in [".deadline",".date",".meta","time","p","span"]:
            n = (b.select_one(sel) if hasattr(b, "select_one") else None)
            if n:
                t = n.get_text(" ", strip=True)
                if _kw(t):
                    deadline_text = t; break
        if not deadline_text and _kw(text_all):
            deadline_text = text_all
        if not deadline_text:
            deadline_text = await _scrape_detail(link)

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
