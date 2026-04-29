import argparse
import subprocess

from db.db import init_db
from parser import listing as listing_mod
from parser import offer as offer_mod
from parser import photos as photos_mod
from data.exporter import run_full_export
from ml import catboost_model
from ml import luxury_prompt
from ml.process_luxury import process_dataset


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
    p1.add_argument("--commit-every", type=int, default=50)

    p2 = sub.add_parser("offers", help="фаза 2: добирает детали по карточкам")
    p2.add_argument("--limit", type=int, default=None)
    p2.add_argument("--headless", action="store_true")

    p3 = sub.add_parser("photos", help="фаза 3: качает фото и конвертирует в webp")
    p3.add_argument("--limit", type=int, default=None)

    p4 = sub.add_parser("pipeline", help="полный прогон: listing -> offers -> photos -> snapshot")
    p4.add_argument("--url", default=DEFAULT_BASE_URL)
    p4.add_argument("--pages", type=int, default=36)         # 36 * 28 ~ 1000 объявлений
    p4.add_argument("--headless", action="store_true")
    p4.add_argument("--commit-every", type=int, default=50)
    p4.add_argument("--no-snapshot", action="store_true", help="не делать DVC снапшот в конце")

    p5 = sub.add_parser("export", help="экспортировать offers и подготовить Kaggle-датасет")
    p5.add_argument("--out", default="data/warehouse")
    p5.add_argument("--ml", default="data/ml/kaggle_dataset.parquet")

    p6 = sub.add_parser("catboost-train", help="обучить CatBoost модель")
    p6.add_argument("--dataset", default="data/ml/kaggle_dataset.parquet")
    p6.add_argument("--model", default="models/catboost_price.cbm")

    p7 = sub.add_parser("catboost-predict", help="применить обученную модель")
    p7.add_argument("--dataset", default="data/ml/kaggle_dataset.parquet")
    p7.add_argument("--model", default="models/catboost_price.cbm")
    p7.add_argument("--out", default="data/ml/predictions.csv")

    p8 = sub.add_parser("luxury-prompt", help="собрать промпт для Mistral с быстрым батчем")
    p8.add_argument("--limit", type=int, default=5)
    p8.add_argument("--parquet", default="data/warehouse/offers.parquet")

    p9 = sub.add_parser("luxury-process", help="обработать весь датасет через Mistral, добавить luxury_description и luxury_photo")
    p9.add_argument("--input", default="data/warehouse/offers.parquet")
    p9.add_argument("--output", default="data/warehouse/offers_luxury.parquet")
    p9.add_argument("--batch", type=int, default=5)

    args = ap.parse_args()

    if args.cmd == "init-db":
        init_db()
        print("DB ready")
    elif args.cmd == "listing":
        listing_mod.run(args.url, args.pages, headless=args.headless, commit_every=args.commit_every)
    elif args.cmd == "offers":
        offer_mod.run(limit=args.limit, headless=args.headless)
    elif args.cmd == "photos":
        photos_mod.run(limit=args.limit)
    elif args.cmd == "pipeline":
        listing_mod.run(args.url, args.pages, headless=args.headless, commit_every=args.commit_every)
        offer_mod.run(headless=args.headless)
        photos_mod.run()
        if not args.no_snapshot:
            print("[pipeline] running snapshot.py")
            subprocess.run(["python", "snapshot.py"], check=False)
    elif args.cmd == "export":
        run_full_export(args.out, args.ml)
    elif args.cmd == "catboost-train":
        catboost_model.train(model_path=args.model, dataset_path=args.dataset)
    elif args.cmd == "catboost-predict":
        catboost_model.predict(model_path=args.model, out_path=args.out, dataset_path=args.dataset)
    elif args.cmd == "luxury-prompt":
        prompt = luxury_prompt.build_payload(limit=args.limit, parquet_path=args.parquet)
        print(prompt)
    elif args.cmd == "luxury-process":
        from pathlib import Path
        process_dataset(Path(args.input), Path(args.output), batch_size=args.batch)


if __name__ == "__main__":
    main()
