# pipelines/normalize.py
import dateparser
from datetime import datetime, timezone, timedelta

# 寫入 Google Sheet 的欄位順序
COLUMNS = [
    "title", "organization", "category", "location",
    "start_date", "deadline_date",
    "deadline", "link", "source",
    "posted_at", "scraped_at", "hash"
]

_TZ = timezone(timedelta(hours=8))  # Asia/Taipei

def now_iso() -> str:
    return datetime.now(_TZ).isoformat()

def parse_to_iso(text: str | None) -> str:
    if not text:
        return ""
    dt = dateparser.parse(
        text,
        languages=["zh", "en"],
        settings={
            "TIMEZONE": "Asia/Taipei",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",   # 沒指明年份時偏向未來
        },
    )
    return dt.isoformat() if dt else ""

def normalize(item: dict) -> dict:
    # 確保所有欄位存在；未提供就補空字串
    base = {k: "" for k in COLUMNS}
    base.update(item or {})
    if not base.get("scraped_at"):
        base["scraped_at"] = now_iso()
    # 舊版相容：如果只給 deadline_date，也把 deadline 一起帶上
    if not base.get("deadline") and base.get("deadline_date"):
        base["deadline"] = base["deadline_date"]
    return base
