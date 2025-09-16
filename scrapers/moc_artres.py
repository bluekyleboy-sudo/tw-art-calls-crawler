from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

BASE = "https://artres.moc.gov.tw"
URL = "https://artres.moc.gov.tw/zh/calls/list"
SOURCE = "moc_artres"
KEYS = ["截止", "收件", "申請期限", "申請時間", "Deadline", "至", "Open Call", "駐村", "徵選"]

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
        wait_selector="a[href*='/calls/'], a[href*='/zh/calls/']"
    )
    soup = BeautifulSoup(html, "lxml")
    rows, seen = [], set()

    # 卡片/列表
    cards = soup.select("a[href*='/calls/'], a[href*='/zh/calls/']")
    for a in cards:
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or not href:
            continue
        link = urljoin(BASE, href)
        if link in seen:
            continue
        seen.add(link)

        # 嘗試在父層附近找截止訊息
        deadline_text = None
        parent = a.find_parent(["div","li","article"]) or a
        for sel in [".deadline",".date",".time",".info",".meta","time","p","span"]:
            n = parent.select_one(sel) if hasattr(parent, "select_one") else None
            if n:
                t = n.get_text(" ", strip=True)
                if _kw(t):
                    deadline_text = t; break

        if not deadline_text:
            deadline_text = await _scrape_detail(link)

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
