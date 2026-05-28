# change_10.md — публичный хостинг viewer

## Что сделано

1. Подняли локальный Postgres на 127.0.0.1:5432 (cluster в `/home/.z/pgdata`, user/db `cian`, trust auth), завернули в supervised user-service `cian-postgres` (mode=process).
2. Прогнали `main.py init-db`, схема создана.
3. Залили `data/warehouse/offers.parquet` в Postgres через одноразовый `load_parquet.py` (976 строк).
4. В parquet нашли мусорные timestamps (year 48113 в `edit_date`/`publication_date` — 94 строки). Очистили через SQL (`UPDATE ... SET ... = NULL WHERE year > 2100`) по всем timestamp-колонкам таблицы `offers`.
5. В `viewer.py` блок `if __name__ == "__main__"` теперь читает `HOST`, `PORT`, `DEBUG` из env и пытается стартовать через waitress (fallback на flask dev server). Добавили `waitress` в зависимости.
6. Зарегистрировали публичный HTTP-сервис `cian-viewer` (port 5005 → `https://cian-viewer-shallbe.zocomputer.io`).

## Что НЕ сделано (осознанно)

- Фото объявлений лежат в DVC (`photos.dvc`) и не подтянуты — в карточках их пока нет. Подтягивать имеет смысл только после полного прогона парсера, когда соберём свежие фото.
- Полный прогон Playwright-парсера не делали — это отдельная задача (~30-60 мин на 1000 объявлений).

## Зачем

Дать публичный viewer для теста UI/фильтров без необходимости разворачивать БД и парсер локально у каждого. Минимальные правки кода — только чтение env в одном месте.
