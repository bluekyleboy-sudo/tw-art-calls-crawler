from bs4 import BeautifulSoup
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

URL = "https://example.com/calls"   # ← 換成實際列表頁
SOURCE = "example_html"

async def run():
    html = await fetch_html(URL, js=False)
    soup = BeautifulSoup(html, "lxml")
    rows = []

    for card in soup.select(".call-item"):            # ← 依網站改
        a = card.select_one("a.title")                # ← 依網站改
        if not a: 
            continue
        title = a.get_text(strip=True)
        link  = a["href"]
        if link and link.startswith("/"):
            link = "https://example.com" + link       # 根域名自行替換
        deadline_text = None
        dnode = card.select_one(".deadline")          # ← 依網站改
        if dnode:
            deadline_text = dnode.get_text(" ", strip=True)

        item = normalize({
            "title": title,
            "organization": "（網站名稱）",          # 可寫死或另抓
            "category": "徵件/補助/駐村",            # 依該站類型
            "location": "Taiwan",
            "deadline_text": deadline_text,
            "link": link,
            "source": SOURCE,
            "posted_at": "",                          # 有就填
        })
        item["hash"] = make_hash(item["title"], item["source"], item["link"])
        rows.append(item)

    return rows
