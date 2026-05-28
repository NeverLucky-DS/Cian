"""Грузит offers.parquet в Postgres. Одноразовый seed-скрипт для viewer без полного парсинга."""
import json
import math
import pandas as pd

from db.db import SessionLocal, init_db
from db.models import Offer

init_db()

df = pd.read_parquet("data/warehouse/offers.parquet")
print(f"rows in parquet: {len(df)}")

# колонки, которые есть в модели Offer (без id, last_seen_at, first_seen_at — заполнятся сами)
model_cols = [c.name for c in Offer.__table__.columns if c.name != "id"]


def clean_value(col, val):
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if col in ("seller_phones", "raw_json"):
        if isinstance(val, (list, dict)):
            return val
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return None
        return None
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime()
    return val


with SessionLocal() as s:
    s.query(Offer).delete()
    s.commit()

    inserted = 0
    for _, row in df.iterrows():
        data = {}
        for col in model_cols:
            if col in df.columns:
                data[col] = clean_value(col, row[col])
        s.add(Offer(**data))
        inserted += 1
        if inserted % 200 == 0:
            s.commit()
            print(f"  committed {inserted}")
    s.commit()
    print(f"inserted: {inserted}")
