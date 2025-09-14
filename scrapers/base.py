# 共用抓取：requests 與（必要時）Playwright
import asyncio, httpx
from playwright.async_api import async_playwright

HEADERS = {"User-Agent": "Mozilla/5.0 (crawler for personal research)"}

async def fetch_html(url: str, js: bool=False, timeout: int=30_000) -> str:
    if not js:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=HEADERS)
            r.raise_for_status()
            return r.text

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=timeout, wait_until="networkidle")
        html = await page.content()
        await browser.close()
        return html
