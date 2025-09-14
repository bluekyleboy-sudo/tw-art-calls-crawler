# scrapers/base.py
import httpx, asyncio
from playwright.async_api import async_playwright

HEADERS = {"User-Agent": "Mozilla/5.0 (crawler for personal research)"}

async def fetch_html(url: str, js: bool=False, wait_selector: str|None=None, timeout: int=45_000) -> str:
    if not js:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, headers=HEADERS, follow_redirects=True)
            r.raise_for_status()
            return r.text

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url, timeout=timeout)
        if wait_selector:
            await page.wait_for_selector(wait_selector, timeout=timeout)
        else:
            await page.wait_for_load_state("networkidle")
        html = await page.content()
        await browser.close()
        return html
