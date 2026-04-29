from __future__ import annotations

from pathlib import Path

import pandas as pd
from catboost import CatBoostRegressor, Pool
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_percentage_error, r2_score

from data.exporter import DEFAULT_ML_DATASET, build_catboost_dataset, export_offers, save_catboost_dataset

MODEL_PATH = Path("models/catboost_price.cbm")
PREDICTIONS_PATH = Path("data/ml/predictions.csv")

CAT_FEATURES = ["district", "metro_name", "building_material", "decoration", "jk_name"]


def _split_dataset(df: pd.DataFrame):
    target = df["price_rub"]
    features = df.drop(columns=["price_rub", "cian_id"])
    X_train, X_val, y_train, y_val = train_test_split(features, target, test_size=0.2, random_state=42)
    cat_idxs = [features.columns.get_loc(col) for col in CAT_FEATURES if col in features.columns]
    train_pool = Pool(X_train, y_train, cat_features=cat_idxs)
    val_pool = Pool(X_val, y_val, cat_features=cat_idxs)
    return train_pool, val_pool, X_val.index, y_val


def train(model_path: str | Path = MODEL_PATH, dataset_path: str | Path = DEFAULT_ML_DATASET) -> Path:
    dataset_path = Path(dataset_path)
    if not dataset_path.exists():
        offers_df = export_offers()
        save_catboost_dataset(offers_df, dataset_path)

    df = pd.read_parquet(dataset_path)
    train_pool, val_pool, val_index, y_val = _split_dataset(df)

    model = CatBoostRegressor(
        depth=6,
        learning_rate=0.08,
        loss_function="MAPE",
        iterations=1200,
        random_seed=42,
        eval_metric="MAPE",
        verbose=100,
    )
    model.fit(train_pool, eval_set=val_pool, use_best_model=True)

    preds = model.predict(val_pool)
    mape = mean_absolute_percentage_error(y_val, preds)
    r2 = r2_score(y_val, preds)
    print(f"[catboost] validation MAPE={mape:.3f}")
    print(f"[catboost] validation R²={r2:.3f}")

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(model_path)
    print(f"[catboost] model saved to {model_path}")
    return model_path


def predict(model_path: str | Path = MODEL_PATH, out_path: str | Path = PREDICTIONS_PATH, dataset_path: str | Path = DEFAULT_ML_DATASET) -> Path:
    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"model not found: {model_path}. Train it first.")

    df = pd.read_parquet(dataset_path)
    feature_df = df.drop(columns=["price_rub", "cian_id"])
    cat_idxs = [feature_df.columns.get_loc(col) for col in CAT_FEATURES if col in feature_df.columns]
    pool = Pool(feature_df, cat_features=cat_idxs)

    model = CatBoostRegressor()
    model.load_model(model_path)
    df["pred_price"] = model.predict(pool)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df[["cian_id", "price_rub", "pred_price"]].to_csv(out_path, index=False)
    print(f"[catboost] predictions saved to {out_path}")
    return out_path
