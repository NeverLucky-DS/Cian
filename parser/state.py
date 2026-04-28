import json


# вырезает из html массив, который Cian кладет в window._cianConfig['<app>']
# приложения у Cian: 'frontend-serp' для листинга, 'frontend-offer-card' для карточки
def extract_cian_config(html, app_name):
    key = "window._cianConfig['" + app_name + "']"
    start = html.find(key)
    if start == -1:
        return None
    i = html.find('.concat(', start)
    if i == -1:
        return None
    i2 = i + len('.concat(')
    # ищем закрывающую скобку с учетом строк и экранирования
    depth = 0
    in_str = False
    esc = False
    end = None
    for j in range(i2, len(html)):
        c = html[j]
        if esc:
            esc = False
            continue
        if c == '\\':
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '(':
            depth += 1
        elif c == ')':
            if depth == 0:
                end = j
                break
            depth -= 1
    if end is None:
        return None
    arr = json.loads(html[i2:end])
    # массив пар вида [{"key": ..., "value": ...}, ...]
    return {item['key']: item['value'] for item in arr}


# берет только то что нам реально нужно: список объявлений с листинга
def get_listing_offers(html):
    cfg = extract_cian_config(html, 'frontend-serp')
    if not cfg:
        return []
    return cfg.get('initialState', {}).get('results', {}).get('offers', []) or []


# берет offerData из карточки объявления
def get_offer_data(html):
    cfg = extract_cian_config(html, 'frontend-offer-card')
    if not cfg:
        return None
    return cfg.get('defaultState', {}).get('offerData')
