# change 8: полная обработка датасета через Mistral + synthetic photo score

## зачем
Нужно оценить роскошь всех объявлений через Mistral и добавить synthetic признак "роскошь по фото" с дисперсией 15. Делает вид, что фотки прогнали через нейронку.

## что добавлено

### ml/mistral_client.py
- HTTP клиент для Mistral API
- функция score_luxury_batch() отправляет промпт и парсит JSON ответ
- берет ключ из env MISTRAL_API_KEY

### ml/process_luxury.py  
- читает весь offers.parquet
- батчами (default 5) отправляет в Mistral для оценки luxury_description
- генерирует luxury_photo = luxury_description +/- random(-15, +15), clamp 0-100
- мержит результаты и сохраняет в offers_luxury.parquet + .csv

### main.py
- команда luxury-process --input --output --batch
- запускает полную обработку датасета

## как запустить

```bash
# 0. Установить ключ Mistral
export MISTRAL_API_KEY="your-key-here"

# 1. Убедиться, что есть данные
uv run python main.py export

# 2. Обработать весь датасет (батчами по 5)
uv run python main.py luxury-process --input data/warehouse/offers.parquet --output data/warehouse/offers_luxury.parquet --batch 5

# 3. Результат: data/warehouse/offers_luxury.parquet с колонками:
#    - luxury_description (0-100, от Mistral)
#    - luxury_photo (0-100, synthetic с дисперсией 15)
#    - luxury_reason (пояснение от Mistral)
```

## особенности
- Если Mistral упал на батче, скрипт печатает ошибку и идет дальше (пропускает батч)
- Можно менять batch size: меньше = быстрее но дороже API, больше = медленнее ответы
- Synthetic photo score имитирует результат обработки фото через нейронку
