# scrapers/moc_artres.py  — 快速且穩定版
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Route, Request
from pipelines.normalize import normalize, parse_to_iso
from pipelines.dedupe import make_hash
import re, asyncio, time

BASE = "https://artres.moc.gov.tw"
URL  = "https://artres.moc.gov.tw/zh/calls/list"
SOURCE = "moc_artres"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

# 為了速度與穩定，限制最多抓幾筆（要更多再調）
MAX_LINKS = 12
NAV_TIMEOUT = 20_000  # 20s
SCROLL_TIMES = 8      # 列表頁滾動次數（避免無限滾）

DATE_RE   = re.compile(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})(?:\s*(\d{1,2}:\d{2}))?")
RANGE_RE  = re.compile(r"(自|自從)?\s*(20\d{2}[./-]\d{1,2}[./-]\d{1,2}).{0,14}至.{0,14}(20\d{2}[./-]\d{1,2}[./-]\d{1,2})")

def extract_range(text: str):
    if not text: return "",""
    m = RANGE_RE.search(text)
    if m:
        return parse_to_iso(m.group(2)), parse_to_iso(m.group(3))
    ds = DATE_RE.findall(text)
    if len(ds) >= 2:
        return parse_to_iso(ds[0][0]), parse_to_iso(ds[-1][0])
    if len(ds) == 1:
        return "", parse_to_iso(ds[0][0])
    return "",""

async def run():
    rows, seen = [], set()
    start = time.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(user_agent=UA, locale="zh-TW")
        # 擋掉圖片/字體/樣式等非必要資源以加速
        async def _route(route: Route, request: Request):
            if request.resource_type in {"image","font","stylesheet","media"}:
                return await route.abort()
            return await route.continue_()
        await ctx.route("**/*", _route)

        page = await ctx.new_page()
        page.set_default_timeout(NAV_TIMEOUT)

        # 1) 列表頁：載入 + 滾動幾次 + 撈出所有 /calls/ 連結
        await page.goto(URL, wait_until="domcontentloaded")
        for _ in range(SCROLL_TIMES):
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(500)

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        hrefs = []
        for a in soup.select("a[href*='/calls/'], a[href*='/zh/calls/']"):
            href = a.get("href","")
            if "/calls/" in href:
                hrefs.append(urljoin(BASE, href))
        # 去重 + 限流
        links = []
        for l in hrefs:
            if l not in seen:
                seen.add(l); links.append(l)
            if len(links) >= MAX_LINKS:
                break

        # 2) 逐一打開內頁（重用同一個 tab），擷取標題與起訖時間
        for link in links:
            try:
                await page.goto(link, wait_until="domcontentloaded")
                # 某些頁面需要再等一下文字載入
                await page.wait_for_timeout(400)
                detail_html = await page.content()
            except Exception as e:
                print(f"[WARN] detail nav timeout: {link} -> {e}")
                continue

            s = BeautifulSoup(detail_html, "lxml")
            title_node = s.select_one("h1") or s.title
            title = title_node.get_text(strip=True) if title_node else ""
            text = s.get_text(" ", strip=True)
            start_iso, end_iso = extract_range(text)

            if not title:
                continue

            item = normalize({
                "title": title,
                "organization": "文化部 Art Residency 平台",
                "category": "駐村/徵選",
                "location": "Taiwan/International",
                "start_date": start_iso,
                "deadline_date": end_iso,
                "deadline": end_iso,
                "link": link,
                "source": SOURCE,
            })
            item["hash"] = make_hash(item["title"], item["source"], item["link"])
            rows.append(item)

        await browser.close()

    print(f"[DEBUG] {SOURCE}: {len(rows)} (elapsed {int(time.time()-start)}s)")
    return rows
