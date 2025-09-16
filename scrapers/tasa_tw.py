from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

BASE = "https://tasa-tw.org"
URL = "https://tasa-tw.org/news-zh/open-call-zh"
SOURCE = "tasa_tw"

# 用來偵測截止/申請等關鍵字（拿來抓就近的日期文字或當備援）
KEYS = ["截止", "收件", "申請", "報名", "至", "Deadline"]

def pick_title_and_link(block):
    """從列表卡片中找標題與連結"""
    for sel in ["h3 a", ".elementor-post__title a", "a[rel='bookmark']", "a[href]"]:
        a = block.select_one(sel)
        if a and a.get_text(strip=True):
            return a.get_text(strip=True), urljoin(BASE, a["href"])
    return None, None

async def _scrape_detail(link: str):
    """有些截止日寫在內文；抓內頁回傳包含關鍵字的一小段文字"""
    html = await fetch_html(link, js=False)
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    for k in KEYS:
        if k in text:
            idx = text.find(k)
            return text[max(0, idx - 40): idx + 80]
    return None

async def run():
    # 這頁是 WordPress/Elementor，常會延遲載入；用 JS 並等到文章連結出現
    html = await fetch_html(
        URL,
        js=True,
        wait_selector="article a, .elementor-post__title a, a[rel='bookmark']"
    )
    soup = BeautifulSoup(html, "lxml")
    rows, seen = [], set()

    # 常見的列表容器
    blocks = soup.select("article, .elementor-post, .jet-listing-grid__item, .entry, .post")
    if not blocks:
        blocks = soup.find_all(["article", "div", "li"])

    for b in blocks:
        title, link = pick_title_and_link(b)
        if not title or not link or link in seen:
            continue
        seen.add(link)

        # 先在卡片附近找帶有日期語意的節點
        deadline_text = None
        for sel in ["time", ".date", ".elementor-post__excerpt", ".entry-summary",
                    ".post-meta", ".elementor-post__meta-data"]:
            n = b.select_one(sel)
            if n:
                t = n.get_text(" ", strip=True)
                if any(k in t for k in KEYS):
                    deadline_text = t
                    break

        # 如果列表抓不到，就進內頁擷取一小段包含關鍵字的文字
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
