from pathlib import Path

import pandas as pd

WAREHOUSE_PARQUET = Path("data/warehouse/offers.parquet")
DEFAULT_BATCH = 5

CRITERIA = [
    "архитектура здания, редкие фасады, панорамные виды",
    "материалы отделки: натуральный камень, инженерная доска, дизайнерский свет",
    "планировка и площадь комнат, приватные зоны, потолки выше 3 метров",
    "инженерные системы: вентиляция, умный дом, теплые полы, акустика",
    "инфраструктура дома: закрытый двор, сервисы, безопасность",
    "локация: центр, виды на парк или набережную, статус района",
    "редкие бонусы: террасы, камины, приватные лифты, премиальная мебель"
]


def load_batch(parquet_path: str | Path = WAREHOUSE_PARQUET, limit: int = DEFAULT_BATCH) -> pd.DataFrame:
    parquet_path = Path(parquet_path)
    if not parquet_path.exists():
        raise FileNotFoundError("сначала сделай export, чтобы появился data/warehouse/offers.parquet")
    df = pd.read_parquet(parquet_path, columns=[
        "cian_id",
        "address_full",
        "district",
        "price_rub",
        "rooms_count",
        "total_area",
        "description"
    ])
    return df.head(limit)


def build_prompt(rows: pd.DataFrame, criteria: list[str] = CRITERIA) -> str:
    head = [
        "You score Moscow real estate listings on a luxury scale from 0 to 100.",
        "Assess only the apartment quality, finishes and location, not the copywriting.",
        "Return JSON like {\"offers\": [{\"cian_id\": 123, \"luxury_score\": 88, \"reason\": \"...\"}]}.",
        "Score bands: 0-30 mass, 30-60 comfort, 60-85 business, 85-100 elite.",
        "Keep each reason under 25 words.",
    ]
    crit = "\n".join(f"- {item}" for item in criteria)
    listing_lines = []
    for _, row in rows.iterrows():
        listing_lines.append(
            "\n".join([
                f"Offer {row.cian_id}",
                f"Address: {row.address_full}",
                f"District: {row.district}",
                f"Rooms: {row.rooms_count}, Area: {row.total_area} m2",
                f"Price: {row.price_rub} RUB",
                f"Description: {row.description}" if isinstance(row.description, str) else "Description: —"
            ])
        )
    payload = "\n\n".join(head)
    payload += "\n\nLuxury criteria:\n" + crit
    payload += "\n\nEvaluate these offers in order:\n\n" + "\n\n".join(listing_lines)
    return payload


def build_payload(limit: int = DEFAULT_BATCH, parquet_path: str | Path = WAREHOUSE_PARQUET) -> str:
    rows = load_batch(parquet_path=parquet_path, limit=limit)
    return build_prompt(rows)
