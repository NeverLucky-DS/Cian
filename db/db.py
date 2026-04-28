import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base

load_dotenv()

# DATABASE_URL читается из .env, например:
# postgresql+psycopg://cian:cian@localhost:5432/cian
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://cian:cian@localhost:5432/cian")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db():
    # создает все таблицы если их еще нет
    Base.metadata.create_all(engine)
