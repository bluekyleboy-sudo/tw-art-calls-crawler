import os
import asyncio
import json
from sheets_writer import upsert_rows
from scrapers import tasa_tw, moc_artres, artemperor

# 強制指定分頁名稱（沒有就用 Calls_v2）
os.environ["SHEET_NAME"] = os.environ.get("SHEET_NAME") or "Calls_v2"

SCRAPERS = [tasa_tw.run, moc_artres.run, artemperor.run]

def _sort_key(row: dict) -> str:
    # 依截止時間排序；沒有的排最後
    d = row.get("deadline_date") or row.get("deadline") or ""
    return d if d else "9999-12-31T00:00:00+08:00"

async def main():
    # 印出實際要寫入的試算表與分頁（尾碼避免外流完整 ID）
    print(f"[ENV] SHEET_ID.tail={os.environ.get('SHEET_ID','')[-8:]}, TAB={os.environ.get('SHEET_NAME')}")

    all_rows = []
    for s in SCRAPERS:
        try:
            rows = await s()
            print(f"[DEBUG] {s.__module__}: {len(rows)}")
            if rows:
                sample = {k: rows[0].get(k) for k in ("title","link","start_date","deadline_date","source")}
                print("[SAMPLE]", json.dumps(sample, ensure_ascii=False))
            all_rows.extend(rows)
        except Exception as e:
            print(f"[WARN] {s.__module__}: {e}")

    if not all_rows:
        print("[WRITE] nothing to write: 0 rows scraped.")
        return

    # 批次內以 hash 去重
    seen, deduped = set(), []
    for r in all_rows:
        h = r.get("hash")
        if not h or h in seen:
            continue
        seen.add(h)
        deduped.append(r)

    # 依截止時間排序後再寫入
    deduped.sort(key=_sort_key)

    inserted, updated = upsert_rows(deduped)
    print(f"[WRITE] inserted={inserted}, updated={updated}, total_payload={len(deduped)}")

if __name__ == "__main__":
    asyncio.run(main())
