# change 3: фиксированно 3 фото на оффер, ретраи, DVC

## фото — главный фикс

Раньше в `--limit 30` вмещалось 1-2 объявления (у каждого ~20 фото). Теперь:

- В `parser/extract.py` добавлена константа `MAX_PHOTOS = 3` и `extract_photos` возвращает **только первые 3 валидных фото** с `position = 0/1/2`.
- В `parser/listing.py` и `parser/offer.py` после апсерта строк фото в БД делается `DELETE FROM offer_photos WHERE offer_id = ? AND position >= 3` — это убирает хвосты от прежних запусков, когда лимита еще не было.
- В `parser/photos.py` функция `download_bytes` теперь делает до 3 попыток с растущей задержкой (1с, 2с, 3с). На стороне CDN cian.ru изредка бывают 5xx — теперь не считаем это фейлом сразу.
- WebP параметры стали скромнее: `MAX_SIDE = 1200`, `quality = 78`. Это не визуально не заметно, но в DVC-снапшоте экономит место в 2-3 раза.

## ретрай парсинга карточки

Если при заходе на детальную страницу `window._cianConfig` не успел подгрузиться (или у объявления случайно нет фото в JSON), это часто значит что cian отдал заглушку или антибот.

В `parser/offer.py` появилась `fetch_offer_data_with_retry(page, url, max_attempts=2)`:
1. Заходим на страницу, скроллим, парсим JSON.
2. Если `offerData` нет или у `offer.photos` пусто — делаем `page.reload()`, ждем 4 секунды и пробуем ещё раз.
3. Если и так пусто — этот оффер пропускаем и считаем ошибкой в `scrape_runs`. Дальше можно перезапустить `main.py offers` без `--limit`, он подберет только пропущенные (`detail_parsed_at IS NULL`).

Дольше 4 секунд ждать смысла нет — практика показывает, что либо JSON отдается сразу, либо нужна перезагрузка.

## viewer — структурированное описание

В `viewer.py` добавлена функция `format_desc(text)`:
- Делит текст на абзацы по двойному переносу.
- Если абзац состоит из строк, начинающихся с `•` / `-` / `*`, рендерит `<ul><li>...</li></ul>`.
- Иначе `<p>...</p>` с `<br>` для одиночных переносов.
Вёрстку трогать сильно не стал, только этот блок и стили `.desc p / .desc ul / .desc li`.

## DVC — версионирование БД и фото

### зачем
БД и папка `photos/` бинарные и тяжёлые, пушить их в git нельзя. DVC хранит сами артефакты в своём кэше (или в удалённом хранилище), а в git коммитятся только метафайлы (`.dvc`) с хэшами.

### как это устроено в проекте

- В git коммитятся:
  - `data/cian.sql.gz.dvc` — метафайл с MD5 текущего дампа БД.
  - `photos.dvc` — метафайл с хэшами всех webp.
  - `.dvc/config` — конфиг DVC (включая remote).
  - `.gitignore` обновляется автоматически (DVC сам туда добавляет фактические артефакты).
- В git **не** коммитятся:
  - `data/cian.sql.gz` (сам дамп) — игнорится, лежит в `.dvc/cache` под хэшем.
  - `photos/` — то же самое.

### снапшот одной командой

`snapshot.py` делает три вещи:
1. `dump_db()` — `docker exec cian-pg pg_dump ...` пишет gzipped SQL в `data/cian.sql.gz`.
2. `dvc_track()` — `dvc add` на дампе и на папке `photos`, потом `git add` метафайлов и `git commit`.
3. `dvc_push()` — отправка артефактов в remote (если настроен).

Запуск после каждого парсинга:
```
uv run python snapshot.py
```

### что нужно от тебя один раз (пошагово)

1. Поставить deps:
   ```
   uv sync
   ```
2. Инициализировать DVC в репо (с `--no-scm` НЕ нужно, у нас git есть):
   ```
   uv run dvc init
   git add .dvc/.gitignore .dvc/config .dvcignore
   git commit -m "init dvc"
   ```
3. Настроить remote-хранилище. Самый простой вариант — локальная папка вне репо:
   ```
   mkdir -p ../cian-dvc-storage
   uv run dvc remote add -d local ../cian-dvc-storage
   git add .dvc/config
   git commit -m "dvc remote: local"
   ```
   (При желании потом можно заменить на S3/Yandex Object Storage — `dvc remote modify local url s3://...`.)
4. Сделать первый снапшот:
   ```
   uv run python snapshot.py
   ```
   Появятся `data/cian.sql.gz.dvc` и `photos.dvc`, они закоммитятся автоматически.

### как смотреть историю/откатываться

- `git log -- photos.dvc` — все версии папки фото.
- `git checkout <commit> -- photos.dvc data/cian.sql.gz.dvc && uv run dvc checkout` — откатить локальный набор фото и дамп БД к состоянию того коммита.
- `uv run dvc diff` — что изменилось между HEAD и текущим состоянием.
- `uv run dvc status` — есть ли несинхронизированные артефакты.
- `uv run dvc pull` — стянуть артефакты на чистую машину (после `git clone`).

### воркфлоу при работе

```
# 1. парсим
uv run python main.py listing --pages 5
uv run python main.py offers
uv run python main.py photos

# 2. фиксируем снапшот
uv run python snapshot.py

# 3. при необходимости отправляем в remote
# (snapshot.py пушит сам, но можно отдельно)
uv run dvc push
```

## что нужно сделать перед следующим прогоном

Старые фото на диске (по 20+ на оффер для тех 2 объявлений, которые скачались) уже не привязаны к строкам в БД (мы поудаляли строки `position >= 3`). Чтобы освободить место — снести папку `photos/` целиком и перекачать чистый набор:

```
rm -rf photos
uv run python main.py offers          # подберет недостающие детали
uv run python main.py photos          # скачает 3 фото каждому из 56 офферов
```

После этого должно быть ровно `56 * 3 = 168` файлов в `photos/<cian_id>/0..2.webp`.
