from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from db.db import engine

WAREHOUSE_DIR = Path("data/warehouse")
ML_DIR = Path("data/ml")
DEFAULT_ML_DATASET = ML_DIR / "kaggle_dataset.parquet"
LUXURY_SCORES_PATH = ML_DIR / "luxury_scores.parquet"


def _read_table(name: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_table(name, conn)


def _jsonify_column(series: pd.Series) -> pd.Series:
    return series.apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else x)


def _add_photo_stats(offers_df: pd.DataFrame, photos_df: pd.DataFrame) -> pd.DataFrame:
    if photos_df.empty:
        offers_df["photos_count"] = 0
        return offers_df
    counts = photos_df.groupby("offer_id").size()
    offers_df["photos_count"] = offers_df["id"].map(counts).fillna(0).astype(int)
    return offers_df


def _enrich_offers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ("seller_phones", "raw_json"):
        if col in df.columns:
            df[col] = _jsonify_column(df[col])
    return df


def export_offers(out_dir: str | Path = WAREHOUSE_DIR) -> pd.DataFrame:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    offers_df = _read_table("offers")
    photos_df = _read_table("offer_photos")
    offers_df = _add_photo_stats(offers_df, photos_df)
    offers_df = _enrich_offers(offers_df)

    csv_path = out_dir / "offers.csv"
    parquet_path = out_dir / "offers.parquet"
    offers_df.to_csv(csv_path, index=False)
    offers_df.to_parquet(parquet_path, index=False)
    print(f"[export] saved {len(offers_df)} rows -> {csv_path} / {parquet_path}")
    return offers_df


def _load_luxury_scores(path: str | Path = LUXURY_SCORES_PATH) -> pd.DataFrame:
    path = Path(path)
    if path.exists():
        return pd.read_parquet(path)
    csv_path = path.with_suffix(".csv")
    if csv_path.exists():
        return pd.read_csv(csv_path)
    return pd.DataFrame(columns=["cian_id", "luxury_description", "luxury_photo", "luxury_reason"])


def build_catboost_dataset(offers_df: pd.DataFrame, luxury_df: pd.DataFrame | None = None) -> pd.DataFrame:
    now_year = datetime.utcnow().year
    df = offers_df.copy()
    df["price_rub"] = pd.to_numeric(df["price_rub"], errors="coerce")
    df = df[df["price_rub"].notnull()]

    base_cols = [
        "cian_id", "price_rub", "rooms_count", "total_area", "living_area",
        "kitchen_area", "floor_number", "floors_total", "is_newbuilding",
        "ceiling_height", "decoration", "windows_view", "building_year",
        "building_material", "district", "metro_name", "metro_minutes",
        "lat", "lon", "photos_count", "jk_name"
    ]
    present_cols = [c for c in base_cols if c in df.columns]
    dataset = df[present_cols].copy()

    dataset["rooms_count"] = dataset["rooms_count"].fillna(0)
    dataset["total_area"] = dataset["total_area"].fillna(dataset["total_area"].median())
    dataset["kitchen_area"] = dataset["kitchen_area"].fillna(0)
    dataset["living_area"] = dataset["living_area"].fillna(0)
    dataset["floor_number"] = dataset["floor_number"].fillna(0)
    dataset["floors_total"] = dataset["floors_total"].replace(0, pd.NA)
    dataset["floors_total"] = dataset["floors_total"].fillna(dataset["floors_total"].median())
    dataset["is_newbuilding"] = dataset["is_newbuilding"].fillna(False).astype(int)
    dataset["photos_count"] = dataset["photos_count"].fillna(0).astype(int)

    dataset["floor_ratio"] = (dataset["floor_number"] / dataset["floors_total"]).fillna(0)
    dataset["age_years"] = now_year - dataset["building_year"].fillna(now_year)
    dataset["price_per_m2_calc"] = dataset["price_rub"] / dataset["total_area"].replace(0, pd.NA)
    dataset["has_metro"] = dataset["metro_minutes"].notnull().astype(int)

    keep_cols = [
        "cian_id", "price_rub", "rooms_count", "total_area", "kitchen_area",
        "floor_number", "floors_total", "is_newbuilding", "photos_count",
        "floor_ratio", "age_years", "price_per_m2_calc", "district",
        "metro_name", "metro_minutes", "building_material", "decoration",
        "lat", "lon", "has_metro", "jk_name"
    ]
    dataset = dataset[keep_cols]
    dataset.dropna(subset=["total_area", "price_rub"], inplace=True)

    cat_cols = ["district", "metro_name", "building_material", "decoration", "jk_name"]
    for col in cat_cols:
        if col in dataset.columns:
            dataset[col] = dataset[col].fillna("NA")

    if luxury_df is None:
        luxury_df = _load_luxury_scores()
    if not luxury_df.empty:
        dataset = dataset.merge(
            luxury_df[["cian_id", "luxury_description", "luxury_photo"]],
            on="cian_id",
            how="left",
        )

    if "luxury_description" in dataset.columns:
        dataset["luxury_description"] = dataset["luxury_description"].fillna(50)
    else:
        dataset["luxury_description"] = 50

    if "luxury_photo" in dataset.columns:
        dataset["luxury_photo"] = dataset["luxury_photo"].fillna(50)
    else:
        dataset["luxury_photo"] = 50
    return dataset


def save_catboost_dataset(offers_df: pd.DataFrame, path: str | Path = DEFAULT_ML_DATASET) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = build_catboost_dataset(offers_df)
    dataset.to_parquet(path, index=False)
    print(f"[export] kaggle dataset rows={len(dataset)} -> {path}")
    return path


def run_full_export(out_dir: str | Path = WAREHOUSE_DIR, ml_path: str | Path = DEFAULT_ML_DATASET) -> None:
    offers_df = export_offers(out_dir)
    save_catboost_dataset(offers_df, ml_path)
