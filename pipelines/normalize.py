# pipelines/normalize.py
import re, dateparser
from datetime import datetime, timezone, timedelta

COLUMNS = ["title","organization","category","location",
           "start_date","deadline_date",
           "deadline","link","source","posted_at","scraped_at","hash"]

_TZ = timezone(timedelta(hours=8))

def now_iso():
    return datetime.now(_TZ).isoformat()

def parse_to_iso(text: str | None):
    if not text: return ""
    dt = dateparser.parse(
        text,
        languages=["zh","en"],
        settings={
            "TIMEZONE": "Asia/Taipei",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future"
        }
    )
    return dt.isoformat() if dt else ""

def normalize(item: dict) -> dict:
    item = {**{c:"" for c in COLUMNS}, **item}
    # 保留相容用的 deadline（可空），真正排序用 deadline_date
    item["scraped_at"] = item.get("scraped_at") or now_iso()
    return item
