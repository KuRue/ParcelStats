from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from services.config import settings

engine = create_engine(settings.database_url, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
