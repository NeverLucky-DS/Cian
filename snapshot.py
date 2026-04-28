import subprocess
import os
from datetime import datetime
from pathlib import Path


# имя docker-контейнера с Postgres
PG_CONTAINER = "cian-pg"
PG_USER = "cian"
PG_DB = "cian"

DATA_DIR = Path("data")
DUMP_PATH = DATA_DIR / "cian.sql.gz"


# вызывает команду и печатает что делает; падает при ошибке
def sh(cmd):
    print(">", " ".join(cmd) if isinstance(cmd, list) else cmd)
    subprocess.run(cmd, shell=isinstance(cmd, str), check=True)


# дампит БД в gz через pg_dump внутри контейнера
def dump_db():
    DATA_DIR.mkdir(exist_ok=True)
    # pg_dump в контейнере, поток отправляется на stdout, тут жмем gzip и пишем в файл
    cmd = (
        f"docker exec {PG_CONTAINER} pg_dump -U {PG_USER} -d {PG_DB} "
        f"--no-owner --no-privileges | gzip > {DUMP_PATH}"
    )
    sh(cmd)
    size_mb = DUMP_PATH.stat().st_size / 1024 / 1024
    print(f"dump ok: {DUMP_PATH} ({size_mb:.1f} MB)")


# обновляет dvc-трекинг для дампа БД и папки фото
def dvc_track():
    # dvc add делает .dvc-файлы и заносит сами артефакты в dvc-кэш
    sh(["dvc", "add", str(DUMP_PATH), "photos"])
    # коммитим .dvc-файлы и .gitignore-обновления в git
    sh(["git", "add", f"{DUMP_PATH}.dvc", "photos.dvc", "data/.gitignore", ".gitignore"])
    msg = f"dvc snapshot {datetime.utcnow().isoformat(timespec='seconds')}Z"
    # commit может упасть если нечего коммитить, это нормально
    subprocess.run(["git", "commit", "-m", msg])


# пушит данные в dvc remote (если настроен)
def dvc_push():
    # remote может быть не настроен, не падаем
    res = subprocess.run(["dvc", "push"])
    if res.returncode != 0:
        print("dvc push: remote не настроен или ошибка пуша. Локальный кэш все равно обновлен.")


def main():
    dump_db()
    dvc_track()
    dvc_push()


if __name__ == "__main__":
    main()
