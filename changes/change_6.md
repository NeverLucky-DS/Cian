# change 6: экспорт в CSV/Parquet и CatBoost

## зачем
SQL остаётся источником данных для пайплайна, но теперь всё можно выгрузить в файлы и кормить ML без Postgres. Команды:
```
uv run python main.py export --out data/warehouse --ml data/ml/catboost_dataset.parquet
uv run python main.py catboost-train --dataset data/ml/catboost_dataset.parquet --model models/catboost_price.cbm
uv run python main.py catboost-predict --model models/catboost_price.cbm --dataset data/ml/catboost_dataset.parquet --out data/ml/predictions.csv
```

## что добавлено
- `data/exporter.py`
  - читает таблицы `offers` и `offer_photos` -> Pandas DataFrame.
  - высчитывает `photos_count`, сериализует JSON-поля, сохраняет `offers.csv` и `offers.parquet` в `data/warehouse/`.
  - строит датасет для CatBoost: базовые числовые фичи + признаки `floor_ratio`, `age_years`, `price_per_m2_calc`, `has_metro`.
  - `run_full_export()` сразу делает оба шага и кладёт ML-датасет в `data/ml/catboost_dataset.parquet`.
- `ml/catboost_model.py`
  - `train()` — читает parquet, делит на train/val, обучает CatBoostRegressor (MAPE), печатает метрику, сохраняет модель (`.cbm`).
  - `predict()` — грузит модель, считает предикт для всего датасета, пишет `cian_id, price_rub, pred_price` в CSV.
- CLI (`main.py`): новые команды `export`, `catboost-train`, `catboost-predict` и импорты.
- `pyproject.toml`: добавлены `pandas`, `pyarrow`, `catboost`, `scikit-learn`.

## инструкция по миграции в Parquet/CSV
```
uv sync                              # подтянуть новые либы
uv run python main.py export         # data/warehouse/offers.(csv|parquet)
uv run python main.py catboost-train # обучит модель и сохранит models/catboost_price.cbm
uv run python main.py catboost-predict
```
После этого Postgres можно останавливать: все данные лежат в `data/warehouse/offers.parquet`, а ML готов к работе.
