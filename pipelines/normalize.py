# 統一欄位、解析日期與雜訊清洗
import re, dateparser
from datetime import datetime, timezone, timedelta

COLUMNS = ["title","organization","category","location","deadline",
           "link","source","posted_at","scraped_at","hash"]

_TZ = timezone(timedelta(hours=8))

def parse_deadline(text: str | None):
    if not text: return None
    text = re.sub(r"\s+", " ", text)
    dt = dateparser.parse(
        text,
        languages=["zh","en"],
        settings={"TIMEZONE": "Asia/Taipei",
                  "RETURN_AS_TIMEZONE_AWARE": True,
                  "PREFER_DATES_FROM": "future"}
    )
    return dt.isoformat() if dt else None

def now_iso():
    return datetime.now(_TZ).isoformat()

def normalize(item: dict) -> dict:
    # item 需至少包含 title/link/source；其他可缺
    item = {**{c:"" for c in COLUMNS}, **item}
    item["deadline"] = item.get("deadline") or parse_deadline(item.get("deadline_text"))
    item["scraped_at"] = now_iso()
    return item
