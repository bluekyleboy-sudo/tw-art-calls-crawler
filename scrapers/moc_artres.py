from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

BASE = "https://artres.moc.gov.tw"
URL  = "https://artres.moc.gov.tw/zh/calls/list"
SOURCE = "moc_artres"

# 這站通常有 JS 動態產生卡片，直接用 js=True
async def run():
    html = await fetch_html(URL, js=True)
    soup = BeautifulSoup(html, "lxml")
    rows = []

    # 常見卡片容器：.call-card / .card / .item 之類，盡量寬鬆
    cards = soup.select(".call, .card, .item, .list-item, .result-item, .calls-list .item")
    if not cards:
        # 後備：找所有含連結與「申請/駐村/徵件」關鍵詞的塊
        cards = [d for d in soup.find_all("div") if d.find("a") and any(
            k in d.get_text(" ", strip=True) for k in ["駐村","徵件","申請","Open Call","徵選"]
        )]

    for c in cards:
        a = c.select_one("a[href]")
        if not a:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        link = urljoin(BASE, a["href"])

        # 取日期/截止資訊：常見 class 或文字關鍵
        deadline_text = None
        for sel in [".deadline", ".date", ".time", ".info", ".meta", "time"]:
            node = c.select_one(sel)
            if node:
                t = node.get_text(" ", strip=True)
                if any(k in t for k in ["截止","收件","至","Deadline","申請期限","申請時間"]):
                    deadline_text = t
                    break
        if not deadline_text:
            # 搜索整個卡片文字（最後手段）
            t = c.get_text(" ", strip=True)
            if any(k in t for k in ["截止","收件","至","Deadline","申請期限","申請時間"]):
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

    return rows
