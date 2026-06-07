# Cian — парсер недвижимости и ML-пайплайн

End-to-end pipeline: парсинг Cian.ru → PostgreSQL → CatBoost (цена) → Mistral (luxury) → веб-viewer.

**Live demo:** [cian-viewer-shallbe.zocomputer.io](https://cian-viewer-shallbe.zocomputer.io)  
976 объявлений, 2964 фото, ML-оценки.

---

## Зачем этот проект (data / ML backend)

Демонстрация полного data pipeline с публичным demo — можно открыть на собеседовании в браузере.

| Навык | Реализация |
|-------|------------|
| Python | CLI, parser, ML, viewer |
| PostgreSQL | хранение объявлений, SQLAlchemy |
| ETL / парсинг | Playwright, JSON extraction, Parquet export |
| ML | CatBoost (MAPE ~30%), Mistral luxury scoring |
| Git | DVC для данных, changelog |
| Async I/O | Playwright, httpx |

---

## Возможности

- Парсинг listing + карточек (Playwright)
- Postgres + экспорт Parquet/CSV
- CatBoost — предсказание цены
- Mistral — luxury-скоринг по тексту
- Flask viewer с фильтрами и сортировкой

---

## Быстрый старт

```bash
uv sync
cp .env.example .env
uv run python main.py init-db
uv run python main.py pipeline --pages 2 --headless
uv run python viewer.py
```

---

## Скриншоты

```markdown
![Viewer](docs/screenshots/viewer.png)
```

| Файл | Что снять |
|------|-----------|
| `viewer.png` | главная live demo (фильтры, карточки) |
| `luxury-chart.png` | распределение luxury-оценок |
| `pipeline-cli.png` | вывод `main.py pipeline` в терминале |

Положи в `docs/screenshots/` и закоммить — отобразится в README.

---

## Структура

```
parser/   — Playwright, extract
db/       — Postgres models
ml/       — CatBoost, Mistral luxury
viewer.py — Flask UI (deployed)
main.py   — CLI (9 subcommands)
```
