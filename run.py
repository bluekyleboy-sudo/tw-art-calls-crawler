# 這個檔先不接爬蟲；只是測試能否寫入 Google Sheet
from datetime import datetime, timedelta, timezone
import hashlib

from sheets_writer import upsert_rows

def make_hash(title, source, link):
    s = f"{title}|{source}|{link}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

now = datetime.now(timezone(timedelta(hours=8)))
deadline = (now + timedelta(days=7)).isoformat()

demo_row = {
    "title": "（示範）藝術補助徵件",
    "organization": "DEMO 單位",
    "category": "補助/徵件",
    "location": "Taiwan",
    "deadline": deadline,
    "link": "https://example.com/call",
    "source": "demo",
    "posted_at": now.isoformat(),
    "scraped_at": now.isoformat(),
    "hash": make_hash("（示範）藝術補助徵件", "demo", "https://example.com/call")
}

if __name__ == "__main__":
    upsert_rows([demo_row])
