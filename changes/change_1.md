# change 1: переход на JSON-парсинг + Postgres + фото в WebP

## что было

Один файл `main.py` парсил DOM через CSS-селекторы и складывал в `results.json`.
Минусы: ловил мусорные карточки, цены строкой, адрес склеен, без деталей и без фото.

## что стало

### структура

```
Cian/
  main.py                # CLI: init-db | listing | offers | photos
  parser/
    state.py             # достает window._cianConfig из html
    extract.py           # маппит JSON в поля БД (offer_to_row и др.)
    listing.py           # фаза 1: листинг -> upsert в БД
    offer.py             # фаза 2: карточка -> детали + продавец + фото-урлы
    photos.py            # фаза 3: качает фото и сохраняет как webp
  db/
    db.py                # engine, session, init_db
    models.py            # Offer, OfferPhoto, ScrapeRun
  dumps/                 # html-дампы для оффлайн отладки
  photos/                # webp файлы (cian_id/<position>.webp)
  .env.example
```

### ключевое решение: парсим JSON, а не DOM

Cian кладет на каждой странице полный state в `window._cianConfig`:
- листинг: `frontend-serp` -> `initialState.results.offers[]`
- карточка: `frontend-offer-card` -> `defaultState.offerData.offer`

Это в разы стабильнее селекторов и дает все поля сразу. Раскопано на дампах в `dumps/`.

### функции

- `parser/state.py`
  - `extract_cian_config(html, app_name)` — ищет `window._cianConfig['<app>'] = (... || []).concat([...])`, аккуратно вырезает массив с учетом скобок и строк, парсит как JSON, схлопывает в dict по полю `key`.
  - `get_listing_offers(html)` / `get_offer_data(html)` — обертки для нужных нам путей.
- `parser/extract.py`
  - `to_float / to_int / to_dt` — мягкие конвертеры. Cian возвращает площади и цены строками, даты бывают и ISO и unix.
  - `offer_to_row(offer, url=None)` — единый маппинг под обе фазы. Берет `bargainTerms`, `building`, `geo`, `newbuilding`, считает `price_per_m2`, режет адрес по типам (location/okrug/raion/street/house), достает координаты и ближайшее метро. Полный сырой объект кладет в `raw_json` (JSONB) — страховка на случай новых полей.
  - `extract_seller(...)` — продавца на листинге (`offer.user`+`offer.phones`) и на карточке (`offerData.agent`) приводит к одному виду.
  - `extract_photos(offer)` — список `{position, url_original, is_layout}`. Берем `fullUrl` (это `*-1.jpg`, оригинал).
- `parser/listing.py`
  - `fetch_listing_html(page, url)` — Playwright + скролл `End` чтобы догрузить SSR.
  - `upsert_offer(...)` — Postgres `INSERT ... ON CONFLICT (cian_id) DO UPDATE`. Аналогично для `offer_photos` по `(offer_id, position)`. Идемпотентно.
  - `run(base_url, max_pages, headless)` — цикл по страницам, пишет журнал в `scrape_runs`.
- `parser/offer.py`
  - `run(limit, headless, sleep_min, sleep_max)` — выбирает в БД offers без `detail_parsed_at`, заходит на карточку, обновляет ту же запись и фото, ставит рандомную паузу 2–5 сек между карточками.
- `parser/photos.py`
  - `to_webp(raw)` — Pillow: переводит в RGB, ресайз по длинной стороне до 1600 px, сохраняет в WebP с quality=80. Это даст в 3–5 раз меньше размера без видимой потери.
  - `_run_async / run` — асинхронно качает фото через `httpx.AsyncClient`, до 6 параллельно. Кладет в `photos/<cian_id>/<position>.webp`. Считает `sha256`, размер, ширину/высоту, обновляет строку в `offer_photos`. Когда у оффера все фото скачаны — ставит ему `photos_done_at`.

### БД (Postgres, две основные таблицы)

- `offers` — плоская таблица с типизированными полями (цена/площади/этаж/дом/локация/метро/продавец/даты). Индексы: `cian_id (unique)`, `metro_name`, `district`, `region`, `jk_id`. Сырой JSON — в `raw_json JSONB`.
- `offer_photos` — `offer_id`, `position`, `url_original`, `path_local`, `width`, `height`, `bytes_size`, `sha256`, `is_layout`, `downloaded_at`. Уникальный ключ `(offer_id, position)`.
- `scrape_runs` — журнал запусков (фаза, длительность, ошибки) для воспроизводимости.

### что удалено

- старый `main.py` (DOM-парсер)
- `results.json`
- временный `dumps/_extract_state.py` (логика перенесена в `parser/state.py`)

## зависимости (pyproject.toml)

`sqlalchemy>=2.0`, `psycopg[binary]>=3.2`, `httpx>=0.27`, `pillow>=10.4`, `python-dotenv>=1.0`.

## что нужно от тебя для запуска

1. Поднять Postgres локально (любой способ; самый простой через docker):
   ```
   docker run -d --name cian-pg -p 5432:5432 \
     -e POSTGRES_USER=cian -e POSTGRES_PASSWORD=cian -e POSTGRES_DB=cian \
     postgres:16
   ```
2. Скопировать `.env.example` в `.env` (если креды другие — поправить `DATABASE_URL`).
3. Поставить deps: `uv sync`.
4. Создать таблицы: `uv run python main.py init-db`.
5. Прогнать пайплайн:
   ```
   uv run python main.py listing --pages 2
   uv run python main.py offers  --limit 20
   uv run python main.py photos  --limit 100
   ```

Скажи, когда Postgres запущен — проверим end-to-end и при необходимости поправлю.
