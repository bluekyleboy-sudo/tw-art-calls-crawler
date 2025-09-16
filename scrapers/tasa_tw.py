from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

BASE = "https://tasa-tw.org"
URL = "https://tasa-tw.org/news-zh/open-call-zh"
SOURCE = "tasa_tw"
KEYS = ["截止", "收件", "申請", "報名", "至", "Deadline", "Open Call"]

def _kw(text: str) -> bool:
    t = (text or "").strip()
    return any(k in t for k in KEYS)

async def _scrape_detail(link: str):
    html = await fetch_html(link, js=True)
    soup = BeautifulSoup(html, "lxml")
    txt = soup.get_text(" ", strip=True)
    # 回傳含關鍵字附近的一小段
    for k in KEYS:
        if k in txt:
            i = txt.find(k)
            return txt[max(0, i-60): i+120]
    # 正則抓日期備援
    import re
    m = re.search(r"(\d{4}[./-]\d{1,2}[./-]\d{1,2}(\s*\d{1,2}:\d{2})?)", txt)
    return m.group(0) if m else None

async def run():
    # Elementor/WordPress：用 JS 並等待文章連結
    html = await fetch_html(
        URL, js=True,
        wait_selector="article a, .elementor-post__title a, a[rel='bookmark']"
    )
    soup = BeautifulSoup(html, "lxml")
    rows, seen = [], set()

    # 先從常見容器找卡片
    blocks = soup.select("article, .elementor-post, .jet-listing-grid__item, .entry, .post")
    if not blocks:
        blocks = soup.select("#content a[href]")

    for b in blocks:
        a = b.select_one("h3 a, .elementor-post__title a, a[rel='bookmark'], a[href]") if hasattr(b, "select_one") else None
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if not title or not href:
            continue
        link = urljoin(BASE, href)
        if link in seen:
            continue
        seen.add(link)

        # 列表附近先找
        deadline_text = None
        for sel in ["time", ".date", ".elementor-post__excerpt", ".entry-summary",
                    ".post-meta", ".elementor-post__meta-data"]:
            n = b.select_one(sel) if hasattr(b, "select_one") else None
            if n:
                t = n.get_text(" ", strip=True)
                if _kw(t):
                    deadline_text = t; break

        # 列表沒有就抓內頁
        if not deadline_text:
            deadline_text = await _scrape_detail(link)

        item = normalize({
            "title": title,
            "organization": "TASA 台灣聲響藝術",
            "category": "Open Call/徵件",
            "location": "Taiwan",
            "deadline_text": deadline_text,
            "link": link,
            "source": SOURCE,
        })
        item["hash"] = make_hash(item["title"], item["source"], item["link"])
        rows.append(item)

    print(f"[DEBUG] {SOURCE}: {len(rows)}")
    return rows
