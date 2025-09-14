from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

BASE = "https://artres.moc.gov.tw"
URL  = "https://artres.moc.gov.tw/zh/calls/list"
SOURCE = "moc_artres"

KEYS = ["截止", "收件", "申請期限", "申請時間", "至", "Deadline"]

async def run():
    # 需要 JS，等到卡片出現
    html = await fetch_html(URL, js=True, wait_selector="a[href*='/calls/']")
    soup = BeautifulSoup(html, "lxml")
    rows, seen = [], set()

    # 盡量廣撈，之後去重
    cards = soup.select(".card, .item, .list-item, .result-item, .calls-list .item, article, li")
    if not cards:
        cards = soup.find_all(["div","article","li"])

    for c in cards:
        a = c.select_one("a[href*='/zh/calls/']")
        if not a: 
            continue
        title = a.get_text(strip=True)
        link  = urljoin(BASE, a["href"])
        if not title or link in seen:
            continue
        seen.add(link)

        # 卡片周圍找截止字串
        deadline_text = None
        for sel in [".deadline", ".date", ".time", ".info", ".meta", "time", ".text", "p", "span"]:
            n = c.select_one(sel)
            if n:
                t = n.get_text(" ", strip=True)
                if any(k in t for k in KEYS):
                    deadline_text = t; break
        if not deadline_text:
            t = c.get_text(" ", strip=True)
            if any(k in t for k in KEYS):
                deadline_text = t

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
