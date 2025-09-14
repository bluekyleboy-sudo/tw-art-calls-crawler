import asyncio
from sheets_writer import upsert_rows

# 把你要跑的來源加進來
from scrapers import example_html, example_js

SCRAPERS = [
    example_html.run,
    example_js.run,
]

async def main():
    all_rows = []
    for s in SCRAPERS:
        try:
            rows = await s()
            all_rows.extend(rows)
        except Exception as e:
            print(f"[WARN] scraper error: {s.__module__} -> {e}")

    if not all_rows:
        print("No rows scraped today.")
        return

    upsert_rows(all_rows)
    print(f"Wrote {len(all_rows)} rows to Google Sheet.")

if __name__ == "__main__":
    asyncio.run(main())
