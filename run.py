import os, json, asyncio
from sheets_writer import upsert_rows
from pipelines.dedupe import make_hash
from pipelines.normalize import now_iso
from scrapers import tasa_tw, moc_artres, artemperor

SCRAPERS = [tasa_tw.run, moc_artres.run, artemperor.run]

async def main():
    all_rows = []
    for s in SCRAPERS:
        try:
            rows = await s()
            print(f"[OK] {s.__module__}: {len(rows)} rows")
            if rows:
                sample = {k: rows[0].get(k) for k in ["title","link","deadline","source"]}
                print("[SAMPLE]", json.dumps(sample, ensure_ascii=False))
            all_rows.extend(rows)
        except Exception as e:
            print(f"[WARN] {s.__module__}: {e}")

    print(f"[ENV] SHEET_ID(tail)={os.environ.get('SHEET_ID','')[-8:]}, TAB={os.environ.get('SHEET_NAME')}")

    # 無論是否有爬到資料，都寫一筆 healthcheck，方便你在 Sheet 端看到痕跡
    hc = {
        "title": "HEALTHCHECK — crawler ran",
        "organization": "crawler",
        "category": "debug",
        "location": "",
        "deadline": "",
        "link": "https://example.com/healthcheck",
        "source": "system",
        "posted_at": now_iso(),
        "scraped_at": now_iso(),
        "hash": make_hash("HEALTHCHECK","system","https://example.com/healthcheck")
    }
    all_rows = [hc] + all_rows

    inserted, updated = upsert_rows(all_rows)
    print(f"[WRITE] inserted={inserted}, updated={updated}, total_payload={len(all_rows)}")

if __name__ == "__main__":
    asyncio.run(main())
