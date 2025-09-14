from bs4 import BeautifulSoup
from urllib.parse import urljoin
from scrapers.base import fetch_html
from pipelines.normalize import normalize
from pipelines.dedupe import make_hash

BASE = "https://tasa-tw.org"
URL  = "https://tasa-tw.org/news-zh/open-call-zh"
SOURCE = "tasa_tw"

# 這頁通常是文章列表，可能是 elementor/wordpress 結構
CANDIDATE_BLOCKS = [
    "article", ".elementor-post", ".post", ".entry", ".archive-post", ".jet-listing-grid__item"
]

def _nearby_deadline_text(block):
    # 優先找有「截止/收件/至」等字樣
    txt = block.get_text(" ", strip=True)
    # 太長就截斷（保留前後 200 字讓 dateparser 有素材）
    if len(txt) > 400: 
        return txt[:200]
    return txt

async def run():
    html = await fetch_html(URL, js=False)
    soup = BeautifulSoup(html, "lxml")
    rows = []

    blocks = []
    for sel in CANDIDATE_BLOCKS:
        blocks.extend(soup.select(sel))
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

        # 抓就近日期/截止字串
        deadline_text = None
        for cand in [
            b.select_one("time"), 
            b.select_one(".date"), 
            b.select_one(".elementor-post__excerpt"),
            b
        ]:
            if cand:
                t = cand.get_text(" ", strip=True)
                if any(k in t for k in ["截止","收件","至","Deadline","申請","投稿","收件至"]):
                    deadline_text = t
                    break
        if not deadline_text:
            deadline_text = _nearby_deadline_text(b)

        item = normalize({
            "title": title,
            "organization": "TASA 台灣聲響藝術",
            "category": "徵件/開放投稿",
            "location": "Taiwan",
            "deadline_text": deadline_text,
            "link": link,
            "source": SOURCE,
        })
        item["hash"] = make_hash(item["title"], item["source"], item["link"])
        rows.append(item)
    return rows
