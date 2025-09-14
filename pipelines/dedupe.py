# 生成唯一鍵避免重複
import hashlib
def make_hash(title: str, source: str, link: str) -> str:
    s = f"{(title or '').strip()}|{(source or '').strip()}|{(link or '').strip()}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
