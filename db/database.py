from sqlmodel import SQLModel, Session, create_engine

from config import DATABASE_URL
from db import models  # Register all table models before create_all runs.

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine, expire_on_commit=False) as session:
        yield session
