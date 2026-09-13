from sqlmodel import SQLModel, create_engine

from config import DATABASE_URL
from db import models  # Register all table models before create_all runs.

engine = create_engine(
    DATABASE_URL,
    echo=False
)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
