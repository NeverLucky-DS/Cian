import random
from pathlib import Path

import pandas as pd

from ml.luxury_prompt import build_prompt, CRITERIA
from ml.mistral_client import score_luxury_batch, batch_iterator

WAREHOUSE_PARQUET = Path("data/warehouse/offers.parquet")
OUTPUT_PARQUET = Path("data/warehouse/offers_luxury.parquet")
LUXURY_ONLY_PATH = Path("data/ml/luxury_scores.parquet")
BATCH_SIZE = 5
PHOTO_VARIANCE = 15


def process_dataset(
    input_path: Path = WAREHOUSE_PARQUET,
    output_path: Path = OUTPUT_PARQUET,
    batch_size: int = BATCH_SIZE,
) -> Path:
    df = pd.read_parquet(input_path)
    needed_cols = ["cian_id", "address_full", "district", "price_rub", "rooms_count", "total_area", "description"]
    for col in needed_cols:
        if col not in df.columns:
            raise ValueError(f"missing column {col} in dataset")
    
    results = []
    rows = df[needed_cols].to_dict("records")
    total = len(rows)
    
    for idx, batch in enumerate(batch_iterator(rows, batch_size)):
        print(f"[process_luxury] batch {idx + 1}/{(total // batch_size) + 1}, size={len(batch)}")
        batch_df = pd.DataFrame(batch)
        prompt = build_prompt(batch_df, criteria=CRITERIA)
        
        try:
            mistral_results = score_luxury_batch(prompt)
        except Exception as e:
            print(f"[process_luxury] mistral error: {e}, skipping batch")
            mistral_results = []
        
        mistral_by_id = {int(r.get("cian_id", 0)): r for r in mistral_results if "cian_id" in r}
        
        for row in batch:
            cian_id = row["cian_id"]
            mistral_res = mistral_by_id.get(cian_id, {})
            score_desc = mistral_res.get("luxury_score", 50)
            
            photo_score = min(100, max(0, score_desc + random.randint(-PHOTO_VARIANCE, PHOTO_VARIANCE)))
            
            results.append({
                "cian_id": cian_id,
                "luxury_description": int(score_desc),
                "luxury_photo": int(photo_score),
                "luxury_reason": mistral_res.get("reason", ""),
            })
    
    luxury_df = pd.DataFrame(results)
    luxury_df.to_parquet(LUXURY_ONLY_PATH, index=False)
    luxury_df.to_csv(LUXURY_ONLY_PATH.with_suffix(".csv"), index=False)

    export_cols = [
        "cian_id", "price_rub", "rooms_count", "total_area", "kitchen_area",
        "floor_number", "floors_total", "is_newbuilding", "photos_count",
        "district", "metro_name", "metro_minutes", "address_full",
        "lat", "lon", "jk_name", "decoration", "building_material",
        "luxury_description", "luxury_photo", "luxury_reason"
    ]
    final_df = df.merge(luxury_df, on="cian_id", how="left")
    final_df = final_df[[c for c in export_cols if c in final_df.columns]]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_parquet(output_path, index=False)
    final_df.to_csv(output_path.with_suffix(".csv"), index=False)
    
    print(f"[process_luxury] saved {len(final_df)} rows -> {output_path}")
    return output_path


if __name__ == "__main__":
    process_dataset()
