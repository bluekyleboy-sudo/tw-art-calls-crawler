from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

BASE = "https://artemperor.tw"
URL  = "https://artemperor.tw/resources"
SOURCE = "artemperor"

# 該頁通常是資源列表（包含徵件/補助），用純 HTML 抓取，若未載到可改 js=True
async def run():
    html = await fetch_html(URL, js=False)
    soup = BeautifulSoup(html, "lxml")
    rows = []

    # 嘗試多種常見容器
    blocks = soup.select(".resource-item, .list-item, article, .card, .item, li")
    if not blocks:
        blocks = soup.find_all(["article","div","li"])

    for b in blocks:
        a = b.select_one("a[href]")
        if not a:
            continue
        title = a.get_text(strip=True)
        if not title:
            continue
        link = urljoin(BASE, a["href"])

        # 過濾非資源/徵件：若該塊沒有「徵件/補助/申請/展覽」等字就跳過（寬鬆）
        text_all = b.get_text(" ", strip=True)
        if not any(k in text_all for k in ["徵件","補助","申請","Open Call","徵選","駐村","展覽", "藝術家招募"]):
            # 可能是其他分類導覽，略過
            continue

        # 抓日期/截止字串
        deadline_text = None
        for sel in [".deadline", ".date", ".meta", "time"]:
            node = b.select_one(sel)
            if node:
                t = node.get_text(" ", strip=True)
                if any(k in t for k in ["截止","收件","至","Deadline","申請期限","申請時間"]):
                    deadline_text = t
                    break
        if not deadline_text:
            # 就近用整塊文字
            if any(k in text_all for k in ["截止","收件","至","Deadline","申請期限","申請時間"]):
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

    return rows
