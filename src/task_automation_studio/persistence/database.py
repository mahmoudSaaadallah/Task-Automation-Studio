from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from task_automation_studio.persistence.models import Base


def create_sqlite_engine(database_url: str):
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "", 1)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(database_url, echo=False, future=True)


def init_database(database_url: str) -> sessionmaker[Session]:
    engine = create_sqlite_engine(database_url)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
