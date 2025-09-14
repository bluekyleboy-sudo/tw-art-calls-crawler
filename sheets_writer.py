import os, json
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

COLUMNS = ["title","organization","category","location","deadline",
           "link","source","posted_at","scraped_at","hash"]

def _client():
    info = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)

def _ensure_header(ws):
    values = ws.get_all_values()
    if not values:
        ws.append_row(COLUMNS)
        try:
            ws.freeze(rows=1)
        except Exception:
            pass

def _read_df(ws):
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame(columns=COLUMNS)
    header, rows = values[0], values[1:]
    df = pd.DataFrame(rows, columns=header)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    return df[COLUMNS]

def upsert_rows(rows):
    if not rows:
        return
    client = _client()
    sh = client.open_by_key(os.environ["SHEET_ID"])
    ws = sh.worksheet(os.environ.get("SHEET_NAME","Calls"))

    _ensure_header(ws)
    cur = _read_df(ws)

    new_df = pd.DataFrame(rows, columns=COLUMNS).fillna("")
    if cur.empty:
        ws.append_rows(new_df.values.tolist(), value_input_option="USER_ENTERED")
        return

    existing = set(cur["hash"].tolist())
    to_insert = new_df[~new_df["hash"].isin(existing)]
    to_update = new_df[new_df["hash"].isin(existing)]

    if not to_insert.empty:
        ws.append_rows(to_insert.values.tolist(), value_input_option="USER_ENTERED")

    if not to_update.empty:
        hash_to_row = {h: i+2 for i, h in enumerate(cur["hash"].tolist())}
        last_col_letter = chr(ord('A') + len(COLUMNS) - 1)
        updates = []
        for _, r in to_update.iterrows():
            idx = hash_to_row.get(r["hash"])
            if not idx:
                continue
            rng = f"A{idx}:{last_col_letter}{idx}"
            updates.append({"range": rng, "values": [r.tolist()]})
        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
