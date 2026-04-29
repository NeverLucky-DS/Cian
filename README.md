# Cian Real Estate Parser & ML Pipeline

Парсер объявлений недвижимости Cian.ru с ML-моделями оценки цены и luxury-скоринга.

## Возможности

- **Парсинг**: JSON-парсинг страниц листинга и карточек (Playwright)
- **Хранение**: Postgres + экспорт в Parquet/CSV
- **ML**: CatBoost модель предсказания цены (MAPE ~30%)
- **Luxury-скоринг**: Оценка роскошности через Mistral AI (текст) + synthetic (фото)
- **Viewer**: Flask-приложение с фильтрами, сортировкой по скидкам, визуализацией распределения luxury-оценок

## Структура

```
Cian/
├── main.py              # CLI entry point
├── viewer.py            # Flask viewer
├── parser/              # Парсинг (JSON extraction, Playwright)
├── db/                  # Postgres models & session
├── ml/                  # CatBoost + Mistral luxury scoring
├── data/                # Data exports & ML datasets
├── models/              # Trained models
├── photos/              # Downloaded WebP photos
├── changes/             # Changelog (change_*.md)
└── README.md
```

## Установка

1. **Postgres** (локально или docker):
   ```bash
   docker run -d --name cian-pg -p 5432:5432 \
     -e POSTGRES_USER=cian -e POSTGRES_PASSWORD=cian -e POSTGRES_DB=cian \
     postgres:16
   ```

2. **Python deps**:
   ```bash
   uv sync
   ```

3. **Env**:
   ```bash
   cp .env.example .env
   # Если нужно, поправь DATABASE_URL в .env
   ```

4. **Инициализация БД**:
   ```bash
   uv run python main.py init-db
   ```

## CLI команды

### Парсинг

```bash
# Полный пайплайн: listing -> offers -> photos -> DVC snapshot
uv run python main.py pipeline --pages 36 --headless

# По отдельности
uv run python main.py listing --url "https://cian.ru/..." --pages 2
uv run python main.py offers --limit 100
uv run python main.py photos --limit 500
```

### Экспорт данных

```bash
# Экспорт из Postgres в CSV/Parquet + сборка Kaggle-датасета
uv run python main.py export --out data/warehouse --ml data/ml/kaggle_dataset.parquet
```

### ML (CatBoost)

```bash
# Обучение модели
uv run python main.py catboost-train --dataset data/ml/kaggle_dataset.parquet --model models/catboost_price.cbm

# Предсказание цен
uv run python main.py catboost-predict --dataset data/ml/kaggle_dataset.parquet --model models/catboost_price.cbm --out data/ml/predictions.csv
```

### Luxury-скоринг (Mistral AI)

```bash
# Генерация промпта для теста
uv run python main.py luxury-prompt --limit 5

# Полная обработка датасета через Mistral
export MISTRAL_API_KEY="your_key"
uv run python main.py luxury-process --input data/warehouse/offers.parquet --output data/warehouse/offers_luxury.parquet --batch 5
```

## Viewer

Запуск Flask-приложения:
```bash
uv run python viewer.py
```

Открой `http://127.0.0.1:5005`

**Функции viewer**:
- Фильтры: поиск, комнаты, цена, новостройки/вторичка
- Сортировка: лучшая скидка (по умолчанию), новые, цена, м²
- Карточки: цена, предсказание модели, скидка %, luxury-баллы
- Детальная страница: все поля, фото галерея
- График распределения luxury-оценок (μ, σ)

## ML Pipeline

### Датасеты

- `data/warehouse/offers.parquet` — сырой экспорт из Postgres
- `data/ml/kaggle_dataset.parquet` — ML-ready (categorical features + luxury scores)
- `data/ml/luxury_scores.parquet` — luxury-оценки (cian_id, luxury_description, luxury_photo, luxury_reason)
- `data/ml/predictions.csv` — предсказанные цены CatBoost

### CatBoost модель

**Параметры**:
- `depth=6`, `learning_rate=0.08`, `iterations=1200`
- `loss_function=MAPE`
- Категориальные фичи: district, metro_name, building_material, decoration, jk_name

**Метрика**: MAPE ~30% на validation

### Luxury-скоринг

- **Текст**: Mistral AI batch processing (оценка описания по критериям)
- **Фото**: Synthetic score (коррелирует с текстом, меньшая дисперсия)
- **Распределение**: Normal(μ=65, σ≈3.1) — близко к целевому (variance=10)

## Kaggle

Для обучения на Kaggle:

1. Забери `data/ml/kaggle_dataset.parquet`
2. Загрузи как Kaggle Dataset
3. В ноутбуке:
   ```python
   import pandas as pd
   from catboost import CatBoostRegressor
   df = pd.read_parquet('kaggle_dataset.parquet')
   # ... train model
   ```

## Changelog

История изменений в папке `changes/` (change_1.md ... change_9.md).

## Зависимости

- `sqlalchemy>=2.0`, `psycopg[binary]>=3.2` — Postgres
- `playwright>=1.40` — браузерная автоматизация
- `httpx>=0.27` — HTTP клиент
- `pillow>=10.4` — обработка фото
- `catboost>=1.2` — ML модель
- `pandas`, `pyarrow` — data processing
- `flask` — viewer

## Troubleshooting

**Parquet reading error**: Пересоздай через `uv run python main.py export`

**Missing luxury scores**: Запусти `uv run python main.py luxury-process`

**CatBoost training error**: Проверь наличие `data/ml/kaggle_dataset.parquet`

**Viewer not showing predictions**: Запусти `uv run python main.py catboost-predict`
