# change 7: luxury scoring prompt

## зачем
Надо быстро кормить Mistral пачкой описаний и получать luxury score 0-100. Собрал критерии + генерацию промпта, чтобы не писать руками. Команда выводит готовый текст за 1-2 секунды.

## что сделал
- `ml/luxury_prompt.py`
  - список признаков премиального жилья
  - чтение свежих данных из `data/warehouse/offers.parquet`
  - функция, которая собирает батч и строит JSON-friendly промпт с короткими требованиями
- `main.py`
  - команда `luxury-prompt --limit 5 --parquet ...`
  - выводит готовый текст, сразу можно кидать в Mistral API

## как пользоваться
```
uv run python main.py export                     # если parquet ещё не собран
uv run python main.py luxury-prompt --limit 8    # напечатает промпт
```
Дальше копируешь текст в запрос к Mistral (можно batched, модель сама вернёт JSON с `luxury_score`).
