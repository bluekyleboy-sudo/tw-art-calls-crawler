import asyncio
from sheets_writer import upsert_rows

from scrapers import tasa_tw, moc_artres, artemperor

SCRAPERS = [
    tasa_tw.run,
    moc_artres.run,
    artemperor.run,
]

async def main():
    all_rows = []
    for s in SCRAPERS:
        try:
            rows = await s()
            print(f"[OK] {s.__module__}: {len(rows)} rows")
            all_rows.extend(rows)
        except Exception as e:
            print(f"[WARN] {s.__module__} -> {e}")

    if not all_rows:
        print("No rows scraped today.")
        return

    upsert_rows(all_rows)
    print(f"Wrote {len(all_rows)} rows to Google Sheet.")

if __name__ == "__main__":
    asyncio.run(main())
