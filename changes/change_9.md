# change 9: kaggle-friendly catboost, luxury метрики в вебе

## зачем
- Нужен датасет, который можно забрать на Kaggle и обучить CatBoost без боли.
- Сайт теперь должен показывать «лучшую скидку» (факт vs модель) и роскошность.
- Отдельно сохраняем luxury-оценки, чтобы не ломать parquet и быстро подмешивать в ML.

## что сделал
1. `data/exporter.py`
   - kaggle dataset -> `data/ml/kaggle_dataset.parquet`, туда уже влетают `luxury_description`/`luxury_photo`.
   - загрузка luxury-оценок (`data/ml/luxury_scores.parquet`) и подмешивание при сборке датасета.
2. `ml/process_luxury.py`
   - отдельный файл `data/ml/luxury_scores.(parquet|csv)` только с `cian_id + luxury`.
   - упрощенный `offers_luxury.parquet`: только безопасные колонки, чтобы parquet без ошибок читался.
3. `ml/catboost_model.py` + CLI
   - дефолтный датасет для train/predict — `data/ml/kaggle_dataset.parquet`.
   - CatBoost с depth=6, 1200 итераций, быстрее стартует.
4. `viewer.py`
   - грузит `luxury_scores` + `predictions.csv`, показывает баллы роскоши и «скидку» (факт минус модель).
   - новый сорт `deal` (по скидке) стоит по умолчанию, карточки/деталка отображают метрики.

## как использовать Kaggle
```bash
uv run python main.py export                # обновит offers.parquet + kaggle_dataset.parquet
# забираешь data/ml/kaggle_dataset.parquet -> Kaggle Dataset -> ноутбук
# в ноутбуке: pip install catboost pandas pyarrow && python ml/catboost_model.py ...
```

## как обновить luxury посчитанный Mistral`ом
```bash
export MISTRAL_API_KEY="..."
uv run python main.py export
uv run python main.py luxury-process        # создаст data/ml/luxury_scores.parquet и offers_luxury.parquet
uv run python main.py catboost-train
uv run python main.py catboost-predict
```
После этого viewer подхватит новые файлы автоматически, и карточки упорядочатся по «самым выгодным» объявлениям.
