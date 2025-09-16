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
    # 這頁有時靠 JS，把 js=True 並等待列表連結出現
    html = await fetch_html(URL, js=True, wait_selector="a[href*='/resources/']")
    soup = BeautifulSoup(html, "lxml")
    rows, seen = [], set()

    blocks = soup.select(".resource-item, .list-item, article, .card, .item, li, .resources a[href]")
    if not blocks:
        blocks = soup.find_all(["article","div","li","a"])

    for b in blocks:
        a = b if getattr(b, "name", "") == "a" else b.select_one("a[href]")
        if not a:
            continue
        href = a.get("href", "")
        if "/resources/" not in href:
            continue
        title = a.get_text(strip=True)
        link  = urljoin(BASE, href)
        if not title or link in seen:
            continue
        seen.add(link)

        # 一定要保留，後面會用到
        text_all = (b.get_text(" ", strip=True) if getattr(b, "name", "") != "a" else title) or ""

        # （暫時關閉關鍵字過濾）
        # if not any(k in text_all for k in KEYS):
        #     continue
