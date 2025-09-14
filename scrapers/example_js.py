from bs4 import BeautifulSoup
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

URL = "https://example-js.com/calls"   # ← 換成實際列表頁
SOURCE = "example_js"

async def run():
    html = await fetch_html(URL, js=True)   # ← 這裡用 js=True
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for card in soup.select("div.card"):
        a = card.select_one("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        link  = a["href"]
        if link.startswith("/"):
            link = "https://example-js.com" + link

        deadline_text = None
        d = card.find(string=lambda s: s and ("截止" in s or "收件" in s))
        if d:
            deadline_text = str(d)

        item = normalize({
            "title": title,
            "organization": "（JS 站名）",
            "category": "徵件",
            "location": "Taiwan",
            "deadline_text": deadline_text,
            "link": link,
            "source": SOURCE,
        })
        item["hash"] = make_hash(item["title"], item["source"], item["link"])
        rows.append(item)
    return rows
