"""Seed offer_photos из папки photos/{cian_id}/*.webp → БД."""
from pathlib import Path
from db.db import SessionLocal, engine
from db.models import OfferPhoto, Offer
from sqlalchemy import select

PHOTOS_DIR = Path("photos")

with SessionLocal() as s:
    # cian_id → offer.id
    id_map = {row.cian_id: row.id for row in s.scalars(select(Offer))}
    print(f"offers in db: {len(id_map)}")

    inserted = 0
    skipped = 0
    for folder in sorted(PHOTOS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        try:
            cian_id = int(folder.name)
        except ValueError:
            continue
        offer_id = id_map.get(cian_id)
        if offer_id is None:
            skipped += 1
            continue
        for webp in sorted(folder.glob("*.webp")):
            position = int(webp.stem)
            size = webp.stat().st_size
            s.add(OfferPhoto(
                offer_id=offer_id,
                position=position,
                url_original="",
                path_local=webp.name,
                bytes_size=size,
            ))
            inserted += 1
    s.commit()
    print(f"inserted: {inserted}, skipped (no offer): {skipped}")
