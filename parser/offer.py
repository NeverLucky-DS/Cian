import time
import random
from datetime import datetime
from playwright.sync_api import sync_playwright
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.db import SessionLocal
from db.models import Offer, OfferPhoto, ScrapeRun
from parser.state import get_offer_data
from parser.extract import offer_to_row, extract_seller, extract_photos, MAX_PHOTOS


# заходит на карточку и возвращает html
def fetch_offer_html(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2)
    for _ in range(3):
        page.keyboard.press("End")
        time.sleep(0.5)
    return page.content()


# обновляет существующую запись данными с детальной страницы
def update_offer_detail(session, offer_data):
    offer = offer_data.get("offer") or {}
    cian_id = offer.get("cianId") or offer.get("id")
    if not cian_id:
        return None

    row = offer_to_row(offer)
    # продавец на карточке отдельно в offerData.agent
    row.update(extract_seller(offer_data))
    row["detail_parsed_at"] = datetime.utcnow()
    row["last_seen_at"] = datetime.utcnow()

    stmt = pg_insert(Offer).values(**row, first_seen_at=datetime.utcnow())
    update_cols = {
        k: stmt.excluded[k]
        for k in row.keys()
        if k not in ("cian_id", "first_seen_at")
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["cian_id"],
        set_=update_cols,
    ).returning(Offer.id)
    res = session.execute(stmt).first()
    offer_id = res.id

    # обновляем фото (с детальной страницы свежее)
    photos = extract_photos(offer)
    for ph in photos:
        ins = pg_insert(OfferPhoto).values(
            offer_id=offer_id,
            position=ph["position"],
            url_original=ph["url_original"],
            is_layout=ph["is_layout"],
        ).on_conflict_do_update(
            index_elements=["offer_id", "position"],
            set_={"url_original": ph["url_original"], "is_layout": ph["is_layout"]},
        )
        session.execute(ins)
    # подчищаем хвосты от прежних запусков
    session.execute(
        delete(OfferPhoto).where(
            OfferPhoto.offer_id == offer_id,
            OfferPhoto.position >= MAX_PHOTOS,
        )
    )
    return offer_id


# вытаскиваем offerData с попыткой ретрая (если не успело прогрузиться)
def fetch_offer_data_with_retry(page, url, max_attempts=2):
    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            html = fetch_offer_html(page, url)
        else:
            # ретрай: перезагружаем страницу и ждем чуть подольше
            try:
                page.reload(wait_until="domcontentloaded", timeout=60000)
            except Exception:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(4)
            html = page.content()
        od = get_offer_data(html)
        if od and od.get("offer", {}).get("photos"):
            return od
    return None


# главная функция фазы 2: добирает детали для всех еще не обработанных карточек
def run(limit=None, headless=False, sleep_min=2.0, sleep_max=5.0):
    run_log = ScrapeRun(phase="offer", note=f"limit={limit}")

    with SessionLocal() as session:
        session.add(run_log)
        session.commit()

        # выбираем offers без detail_parsed_at
        q = select(Offer.id, Offer.cian_id, Offer.url).where(Offer.detail_parsed_at.is_(None))
        if limit:
            q = q.limit(limit)
        targets = session.execute(q).all()
        print(f"[offer] to process: {len(targets)}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            ctx = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                locale="ru-RU",
                timezone_id="Europe/Moscow",
            )
            ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => false });"
            )
            page = ctx.new_page()

            for i, t in enumerate(targets, 1):
                print(f"[offer] {i}/{len(targets)} cian_id={t.cian_id}")
                try:
                    od = fetch_offer_data_with_retry(page, t.url, max_attempts=2)
                    if not od:
                        print("  no offerData (after retry)")
                        run_log.errors += 1
                        continue
                    update_offer_detail(session, od)
                    session.commit()
                    run_log.offers_seen += 1
                except Exception as e:
                    run_log.errors += 1
                    print(f"  error: {e}")
                # антибот: рандомная пауза между карточками
                time.sleep(random.uniform(sleep_min, sleep_max))

            browser.close()

        run_log.finished_at = datetime.utcnow()
        session.commit()
        print(f"[offer] done. seen={run_log.offers_seen} errors={run_log.errors}")
