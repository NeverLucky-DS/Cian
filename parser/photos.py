import asyncio
import hashlib
import io
import os
from datetime import datetime
from pathlib import Path

import httpx
from PIL import Image
from sqlalchemy import select, update

from db.db import SessionLocal
from db.models import Offer, OfferPhoto, ScrapeRun


PHOTOS_DIR = Path("photos")
MAX_SIDE = 1200         # ограничение длинной стороны в пикселях
WEBP_QUALITY = 78
CONCURRENCY = 6         # сколько фото качаем параллельно


# скачивает байты картинки с ретраями
async def download_bytes(client, url, attempts=3):
    last_err = None
    for i in range(attempts):
        try:
            r = await client.get(url, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            last_err = e
            await asyncio.sleep(1.0 * (i + 1))
    raise last_err


# конвертирует исходные байты в webp с ресайзом, возвращает (bytes, w, h)
def to_webp(raw):
    img = Image.open(io.BytesIO(raw))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_SIDE:
        if w >= h:
            new_w = MAX_SIDE
            new_h = int(h * MAX_SIDE / w)
        else:
            new_h = MAX_SIDE
            new_w = int(w * MAX_SIDE / h)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        w, h = new_w, new_h
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=6)
    return buf.getvalue(), w, h


# обработка одной фотографии: качаем, конвертируем, пишем на диск
async def process_one(client, sem, photo_row, cian_id):
    async with sem:
        try:
            raw = await download_bytes(client, photo_row.url_original)
        except Exception as e:
            return photo_row.id, None, str(e)
        try:
            data, w, h = to_webp(raw)
        except Exception as e:
            return photo_row.id, None, f"webp: {e}"

        folder = PHOTOS_DIR / str(cian_id)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{photo_row.position}.webp"
        path.write_bytes(data)
        return photo_row.id, {
            "path_local": str(path),
            "width": w,
            "height": h,
            "bytes_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }, None


# главный цикл фазы 3
async def _run_async(limit=None):
    run_log = ScrapeRun(phase="photos", note=f"limit={limit}")
    PHOTOS_DIR.mkdir(exist_ok=True)

    with SessionLocal() as session:
        session.add(run_log)
        session.commit()

        # выбираем фото которые еще не скачаны
        q = (
            select(OfferPhoto, Offer.cian_id)
            .join(Offer, Offer.id == OfferPhoto.offer_id)
            .where(OfferPhoto.path_local.is_(None))
        )
        if limit:
            q = q.limit(limit)
        rows = session.execute(q).all()
        print(f"[photos] to download: {len(rows)}")

        sem = asyncio.Semaphore(CONCURRENCY)
        async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}) as client:
            tasks = [process_one(client, sem, r.OfferPhoto, r.cian_id) for r in rows]
            for fut in asyncio.as_completed(tasks):
                photo_id, info, err = await fut
                if err:
                    run_log.errors += 1
                    continue
                session.execute(
                    update(OfferPhoto)
                    .where(OfferPhoto.id == photo_id)
                    .values(downloaded_at=datetime.utcnow(), **info)
                )
                run_log.offers_seen += 1
            session.commit()

        # отметим offers, у которых все фото скачаны
        session.execute(
            update(Offer)
            .where(Offer.id.in_(
                select(OfferPhoto.offer_id).where(OfferPhoto.path_local.isnot(None)).distinct()
            ))
            .values(photos_done_at=datetime.utcnow())
        )
        run_log.finished_at = datetime.utcnow()
        session.commit()
        print(f"[photos] done. ok={run_log.offers_seen} errors={run_log.errors}")


def run(limit=None):
    asyncio.run(_run_async(limit=limit))
