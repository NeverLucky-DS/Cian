import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# Настройки
BASE_URL = "https://cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1"
MAX_PAGES = 2
OUTPUT_FILE = "results.json"

# Селекторы
SELECTORS = {
    "card": "article",
    "title": '[data-mark="OfferTitle"]',
    "price": '[data-testid="offer-discount-new-price"], [data-mark="MainPrice"], span[class*="price"]',
    "price_per_m2": '[data-mark="PriceInfo"]',
    "metro": '[data-name="SpecialGeo"] a',
    "address": '[data-name="GeoLabel"]',
    "link": 'a[href*="/sale/flat/"]'
}

def get_price(card):
    """Пробуем разные селекторы пока не найдем цену"""
    selectors = [
        '[data-testid="offer-discount-new-price"]',
        '[data-mark="MainPrice"]', 
        '[data-testid="price"]',
        '[data-mark="Price"]',
        'span[class*="price"]'
    ]
    
    for sel in selectors:
        el = card.query_selector(sel)
        if el:
            text = el.inner_text().strip()
            if any(c.isdigit() for c in text):
                return text
    return "Нет цены"

def parse_card(card):
    """Вытаскиваем данные из одной карточки"""
    try:
        # Заголовок
        title_el = card.query_selector(SELECTORS["title"])
        title = title_el.inner_text().strip() if title_el else ""
        
        # Цена (сложная часть - разная верстка)
        price = get_price(card)
        
        # Метро
        metro_el = card.query_selector(SELECTORS["metro"])
        metro = metro_el.inner_text().strip() if metro_el else ""
        
        # Адрес (может быть несколько частей)
        addr_els = card.query_selector_all(SELECTORS["address"])
        address = ", ".join([el.inner_text().strip() for el in addr_els])
        
        # Ссылка
        link_el = card.query_selector(SELECTORS["link"])
        url = ""
        if link_el:
            href = link_el.get_attribute("href")
            url = href if href.startswith("http") else f"https://cian.ru{href}"
        
        return {
            "title": title,
            "price": price,
            "metro": metro,
            "address": address,
            "url": url,
            "parsed_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Ошибка в карточке: {e}")
        return None

def main():
    print("Старт парсинга...")
    
    data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        
        # Прячем автоматизацию
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)
        
        for page_num in range(1, MAX_PAGES + 1):
            url = BASE_URL if page_num == 1 else f"{BASE_URL}&p={page_num}"
            print(f"\nПарсим страницу {page_num}: {url[:60]}...")
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(2)  # ждем подгрузки JS
                
                # Скроллим вниз чтобы все карточки появились
                for i in range(3):
                    page.keyboard.press("End")
                    time.sleep(1)
                
                # Собираем карточки
                cards = page.query_selector_all(SELECTORS["card"])
                print(f"Найдено карточек: {len(cards)}")
                
                for i, card in enumerate(cards, 1):
                    item = parse_card(card)
                    if item:
                        data.append(item)
                        print(f"  {i}. {item['price'][:30]}...")
                
                time.sleep(3)  # пауза между страницами
                
            except Exception as e:
                print(f"Ошибка на странице {page_num}: {e}")
                continue
        
        browser.close()
    
    # Сохраняем
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\nГотово! Собрано {len(data)} объектов. Файл: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()