import asyncio
import json
from sheets_writer import upsert_rows
from scrapers import tasa_tw, moc_artres, artemperor

# 要跑的來源
SCRAPERS = [tasa_tw.run, moc_artres.run, artemperor.run]

async def main():
    all_rows = []
    for s in SCRAPERS:
        try:
            rows = await s()
            print(f"[DEBUG] {s.__module__}: {len(rows)}")
            if rows:
                sample = {k: rows[0].get(k) for k in ["title", "link", "deadline", "source"]}
                print("[SAMPLE]", json.dumps(sample, ensure_ascii=False))
            all_rows.extend(rows)
        except Exception as e:
            print(f"[WARN] {s.__module__}: {e}")

    if not all_rows:
        print("[WRITE] nothing to write: 0 rows scraped.")
        return

    inserted, updated = upsert_rows(all_rows)
    print(f"[WRITE] inserted={inserted}, updated={updated}, total_payload={len(all_rows)}")

if __name__ == "__main__":
    asyncio.run(main())
