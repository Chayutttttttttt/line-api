"""Enable pgvector before the preserved initial migration, then upgrade."""
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from db.database import engine


def main():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    command.upgrade(Config("alembic.ini"), "head")


if __name__ == "__main__":
    main()
