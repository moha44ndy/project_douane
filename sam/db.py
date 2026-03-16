from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config.settings import Config


DATABASE_URL = Config.SUPABASE_DB_URL

if not DATABASE_URL:
    raise RuntimeError(
        "SUPABASE_DB_URL n'est pas défini. "
        "Ajoute-le dans ton fichier .env (voir configuration Supabase)."
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, future=True
)


@contextmanager
def get_db() -> Iterator[Session]:
    """Fournit une session SQLAlchemy à utiliser avec `with get_db() as db:`."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL = os.getenv("SUPABASE_DB_URL")

if not DATABASE_URL:
  raise RuntimeError("SUPABASE_DB_URL must be set in environment to use the database.")

engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

