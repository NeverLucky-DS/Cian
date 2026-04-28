import argparse

from db.db import init_db
from parser import listing as listing_mod
from parser import offer as offer_mod
from parser import photos as photos_mod


# базовая ссылка на листинг (продажа квартир, Москва)
DEFAULT_BASE_URL = (
    "https://cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1"
)


def main():
    ap = argparse.ArgumentParser(description="Cian parser")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="создает таблицы в Postgres")

    p1 = sub.add_parser("listing", help="фаза 1: парсит страницы листинга в БД")
    p1.add_argument("--url", default=DEFAULT_BASE_URL)
    p1.add_argument("--pages", type=int, default=2)
    p1.add_argument("--headless", action="store_true")

    p2 = sub.add_parser("offers", help="фаза 2: добирает детали по карточкам")
    p2.add_argument("--limit", type=int, default=None)
    p2.add_argument("--headless", action="store_true")

    p3 = sub.add_parser("photos", help="фаза 3: качает фото и конвертирует в webp")
    p3.add_argument("--limit", type=int, default=None)

    args = ap.parse_args()

    if args.cmd == "init-db":
        init_db()
        print("DB ready")
    elif args.cmd == "listing":
        listing_mod.run(args.url, args.pages, headless=args.headless)
    elif args.cmd == "offers":
        offer_mod.run(limit=args.limit, headless=args.headless)
    elif args.cmd == "photos":
        photos_mod.run(limit=args.limit)


if __name__ == "__main__":
    main()
