from datetime import datetime
from sqlalchemy import (
    BigInteger, Integer, String, Text, Boolean, Float, DateTime,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# главная таблица: одна строка на объявление
class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cian_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    url: Mapped[str] = mapped_column(Text)

    # категория и тип
    category: Mapped[str | None] = mapped_column(String(64))
    deal_type: Mapped[str | None] = mapped_column(String(32))
    offer_type: Mapped[str | None] = mapped_column(String(32))
    flat_type: Mapped[str | None] = mapped_column(String(32))
    is_apartments: Mapped[bool | None] = mapped_column(Boolean)
    is_newbuilding: Mapped[bool | None] = mapped_column(Boolean)

    # текст
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    # цена
    price_rub: Mapped[int | None] = mapped_column(BigInteger)
    price_per_m2_rub: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(8))
    mortgage_allowed: Mapped[bool | None] = mapped_column(Boolean)
    sale_type: Mapped[str | None] = mapped_column(String(32))

    # квартира
    rooms_count: Mapped[int | None] = mapped_column(Integer)
    total_area: Mapped[float | None] = mapped_column(Float)
    living_area: Mapped[float | None] = mapped_column(Float)
    kitchen_area: Mapped[float | None] = mapped_column(Float)
    floor_number: Mapped[int | None] = mapped_column(Integer)
    floors_total: Mapped[int | None] = mapped_column(Integer)
    ceiling_height: Mapped[float | None] = mapped_column(Float)
    decoration: Mapped[str | None] = mapped_column(String(64))
    windows_view: Mapped[str | None] = mapped_column(String(64))
    balconies_count: Mapped[int | None] = mapped_column(Integer)
    loggias_count: Mapped[int | None] = mapped_column(Integer)

    # дом
    building_year: Mapped[int | None] = mapped_column(Integer)
    building_material: Mapped[str | None] = mapped_column(String(64))
    building_class: Mapped[str | None] = mapped_column(String(64))
    parking_type: Mapped[str | None] = mapped_column(String(64))
    passenger_lifts: Mapped[int | None] = mapped_column(Integer)
    cargo_lifts: Mapped[int | None] = mapped_column(Integer)
    deadline_year: Mapped[int | None] = mapped_column(Integer)
    deadline_quarter: Mapped[int | None] = mapped_column(Integer)
    is_complete: Mapped[bool | None] = mapped_column(Boolean)

    # ЖК
    jk_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    jk_name: Mapped[str | None] = mapped_column(String(255))
    jk_developer: Mapped[str | None] = mapped_column(String(255))
    jk_house: Mapped[str | None] = mapped_column(String(255))

    # локация
    region: Mapped[str | None] = mapped_column(String(128), index=True)
    okrug: Mapped[str | None] = mapped_column(String(128))
    district: Mapped[str | None] = mapped_column(String(128), index=True)
    street: Mapped[str | None] = mapped_column(String(255))
    house: Mapped[str | None] = mapped_column(String(64))
    address_full: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    # ближайшее метро (для удобства фильтра, остальные в raw_json)
    metro_name: Mapped[str | None] = mapped_column(String(128), index=True)
    metro_minutes: Mapped[int | None] = mapped_column(Integer)
    metro_travel_type: Mapped[str | None] = mapped_column(String(32))

    # продавец
    seller_type: Mapped[str | None] = mapped_column(String(32))
    seller_name: Mapped[str | None] = mapped_column(String(255))
    seller_user_id: Mapped[int | None] = mapped_column(BigInteger)
    seller_phones: Mapped[list | None] = mapped_column(JSONB)

    # сервисное
    creation_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    edit_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str | None] = mapped_column(String(32))

    # сырой JSON оффера на случай если какое-то поле забыли вытащить
    raw_json: Mapped[dict | None] = mapped_column(JSONB)

    # фазы парсинга
    listing_parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detail_parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    photos_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    photos: Mapped[list["OfferPhoto"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan"
    )


class OfferPhoto(Base):
    __tablename__ = "offer_photos"
    __table_args__ = (
        UniqueConstraint("offer_id", "position", name="uq_offer_position"),
        Index("ix_offer_photos_offer_id", "offer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    url_original: Mapped[str] = mapped_column(Text)
    path_local: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    bytes_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    is_layout: Mapped[bool | None] = mapped_column(Boolean)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    offer: Mapped[Offer] = relationship(back_populates="photos")


# журнал запусков парсера
class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phase: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pages_done: Mapped[int] = mapped_column(Integer, default=0)
    offers_seen: Mapped[int] = mapped_column(Integer, default=0)
    offers_new: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text)
