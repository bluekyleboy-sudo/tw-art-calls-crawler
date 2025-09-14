from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

BASE = "https://artemperor.tw"
URL  = "https://artemperor.tw/resources"
SOURCE = "artemperor"

KEYS = ["徵件", "補助", "申請", "Open Call", "徵選", "駐村", "展覽", "招募", "截止", "收件", "至", "Deadline"]

async def run():
    # 這頁有時候也靠 JS，保守起見 js=True 並等待列表 a 出現
    html = await fetch_html(URL, js=True, wait_selector="a[href*='/resources/']")
    soup = BeautifulSoup(html, "lxml")
    rows, seen = [], set()

    blocks = soup.select(".resource-item, .list-item, article, .card, .item, li, .resources a[href]")
    if not blocks:
        blocks = soup.find_all(["article","div","li","a"])

    for b in blocks:
        a = b if b.name == "a" else b.select_one("a[href]")
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

        text_all = (b.get_text(" ", strip=True) if b.name != "a" else title) or ""
        # if not any(k in text_all for k in KEYS):
            # 很可能是分類或導覽，不像徵件/資源，略過
            ＃continue

        deadline_text = None
        for sel in [".deadline", ".date", ".meta", "time", "p", "span"]:
            n = (b.select_one(sel) if hasattr(b, "select_one") else None)
            if n:
                t = n.get_text(" ", strip=True)
                if any(k in t for k in KEYS):
                    deadline_text = t; break
        if not deadline_text and any(k in text_all for k in KEYS):
            deadline_text = text_all

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
