import time
import random
from datetime import datetime
from playwright.sync_api import sync_playwright
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.db import SessionLocal
from db.models import Offer, OfferPhoto, ScrapeRun
from parser.state import get_listing_offers
from parser.extract import offer_to_row, extract_seller, extract_photos, MAX_PHOTOS


# берет одну страницу листинга и возвращает ее html после прогрузки
def fetch_listing_html(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    # прокрутить вниз чтобы догрузились карточки
    for _ in range(5):
        page.keyboard.press("End")
        time.sleep(0.7)
    return page.content()


# сохраняет/обновляет одно объявление в БД (upsert по cian_id)
def upsert_offer(session, offer_dict, photos_list):
    # сначала верхняя строка через ON CONFLICT
    now = datetime.utcnow()
    insert_data = dict(offer_dict)
    insert_data["listing_parsed_at"] = now
    insert_data["last_seen_at"] = now
    insert_data["first_seen_at"] = now

    stmt = pg_insert(Offer).values(**insert_data)
    update_cols = {
        k: stmt.excluded[k]
        for k in insert_data.keys()
        if k not in ("cian_id", "first_seen_at")
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["cian_id"],
        set_=update_cols,
    ).returning(Offer.id, Offer.cian_id)
    res = session.execute(stmt).first()
    offer_id = res.id

    # фото — пишем url-ы (без скачивания, скачаем отдельной фазой)
    for ph in photos_list:
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
    # подчищаем строки сверх лимита (от прежних запусков, когда лимита не было)
    session.execute(
        delete(OfferPhoto).where(
            OfferPhoto.offer_id == offer_id,
            OfferPhoto.position >= MAX_PHOTOS,
        )
    )
    return offer_id


# главная функция фазы 1: проходит N страниц листинга, складывает в БД
# commit_every — коммит каждые N упертых апсертов (страховка чтобы не потерять прогресс)
# pause_min/pause_max — рандомная пауза между страницами
def run(base_url, max_pages, headless=False, commit_every=50, pause_min=2.0, pause_max=5.0):
    run_log = ScrapeRun(phase="listing", note=base_url)

    with SessionLocal() as session:
        session.add(run_log)
        session.commit()

        # дедуп в рамках одного запуска: cian повторяет одни и те же объявления
        # на разных страницах листинга, нет смысла апсертить второй раз
        seen_in_run = set()
        since_commit = 0
        total_dups = 0

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

            for page_num in range(1, max_pages + 1):
                url = base_url if page_num == 1 else f"{base_url}&p={page_num}"
                print(f"[listing] page {page_num}/{max_pages}: {url}")
                try:
                    html = fetch_listing_html(page, url)
                    offers = get_listing_offers(html)
                    print(f"  offers in JSON: {len(offers)}")
                    page_new = 0
                    page_dup = 0
                    for o in offers:
                        try:
                            row = offer_to_row(o)
                            cid = row.get("cian_id")
                            if not cid:
                                continue
                            if cid in seen_in_run:
                                page_dup += 1
                                total_dups += 1
                                continue
                            seen_in_run.add(cid)
                            row.update(extract_seller(o))
                            photos = extract_photos(o)
                            upsert_offer(session, row, photos)
                            run_log.offers_seen += 1
                            page_new += 1
                            since_commit += 1
                            if since_commit >= commit_every:
                                session.commit()
                                print(f"  [commit] saved {since_commit} offers, total seen={run_log.offers_seen}")
                                since_commit = 0
                        except Exception as e:
                            run_log.errors += 1
                            print(f"  offer error: {e}")
                    session.commit()
                    since_commit = 0
                    run_log.pages_done += 1
                    print(f"  page summary: new={page_new} dup_in_run={page_dup} unique_total={len(seen_in_run)}")
                    # рандомная пауза между страницами против антибота
                    time.sleep(random.uniform(pause_min, pause_max))
                except Exception as e:
                    run_log.errors += 1
                    print(f"  page error: {e}")

            browser.close()

        session.commit()
        run_log.finished_at = datetime.utcnow()
        session.commit()
        print(f"[listing] done. unique={len(seen_in_run)} duplicates_skipped={total_dups} errors={run_log.errors}")
