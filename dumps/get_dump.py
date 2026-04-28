from playwright.sync_api import sync_playwright
import time
urls = {
    'listing.html': 'https://cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1',
    'offer.html':   'https://www.cian.ru/sale/flat/327542673/'
}
with sync_playwright() as p:
    b = p.chromium.launch(headless=False)
    pg = b.new_page(viewport={'width':1920,'height':1080})
    for name, u in urls.items():
        pg.goto(u, wait_until='domcontentloaded', timeout=60000)
        time.sleep(4)
        for _ in range(6):
            pg.keyboard.press('End'); time.sleep(0.7)
        open('dumps/'+name,'w',encoding='utf-8').write(pg.content())
    b.close()