# scrapers/moc_artres.py
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from pipelines.normalize import normalize, parse_to_iso
from pipelines.dedupe import make_hash
import re

BASE = "https://artres.moc.gov.tw"
URL  = "https://artres.moc.gov.tw/zh/calls/list"
SOURCE = "moc_artres"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

DATE_RE  = re.compile(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})(?:\s*(\d{1,2}:\d{2}))?")
RANGE_RE = re.compile(r"(自|自從)?\s*(20\d{2}[./-]\d{1,2}[./-]\d{1,2}).{0,14}至.{0,14}(20\d{2}[./-]\d{1,2}[./-]\d{1,2})")

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

async def _load_html(url: str, timeout_ms=90_000):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(user_agent=UA, locale="zh-TW")
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        # 關 Cookie/隱私彈窗（若有）
        for sel in ['button:has-text("同意")','button:has-text("接受")',
                    '#onetrust-accept-btn-handler','.cookie-accept','.ot-sdk-container button']:
            try: await page.click(sel, timeout=1200)
            except Exception: pass
        # 滾動載入
        for _ in range(15):
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(600)
        await page.wait_for_load_state("networkidle")
        html = await page.content()
        await browser.close()
        return html

async def _detail(link: str):
    html = await _load_html(link)
    s = BeautifulSoup(html, "lxml")
    title = (s.select_one("h1") or s.title)
    title = title.get_text(strip=True) if title else ""
    text = s.get_text(" ", strip=True)
    start_iso, end_iso = extract_range(text)
    return title, start_iso, end_iso

async def run():
    html = await _load_html(URL)
    soup = BeautifulSoup(html, "lxml")
    hrefs = {a.get("href","") for a in soup.select("a[href*='/calls/'], a[href*='/zh/calls/']")}
    links = [urljoin(BASE, h) for h in hrefs if "/calls/" in h]

    rows, seen = [], set()
    for link in links:
        if link in seen: 
            continue
        seen.add(link)
        try:
            title, start_iso, end_iso = await _detail(link)
        except Exception as e:
            print(f"[WARN] detail fail: {link} -> {e}")
            continue
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

    print(f"[DEBUG] {SOURCE}: {len(rows)}")
    return rows
