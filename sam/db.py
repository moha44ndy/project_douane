from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config.settings import Config

logger = logging.getLogger(__name__)


def _ensure_sslmode_require(url: str) -> str:
    """Supabase exige TLS ; force sslmode=require si absent de l'URI."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    if not qs.get("sslmode"):
        qs["sslmode"] = ["require"]
    query = urlencode(qs, doseq=True)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


DATABASE_URL_RAW = Config.SUPABASE_DB_URL

if not DATABASE_URL_RAW:
    raise RuntimeError(
        "Aucune URL Postgres : définis SUPABASE_DB_URL ou SUPABASE_DB_POOLER_URL "
        "dans le .env à la racine du projet (Session pooler recommandé sur réseau IPv4)."
    )

DATABASE_URL = _ensure_sslmode_require(DATABASE_URL_RAW)

_parsed = urlparse(DATABASE_URL)
_host = (_parsed.hostname or "").lower()
_port = _parsed.port or 5432

if _host.startswith("db.") and _host.endswith(".supabase.co") and "pooler" not in _host:
    if _port == 5432:
        logger.warning(
            "Postgres via hote direct %s:5432 : souvent IPv6-only ; timeout frequent sur Windows. "
            "Definis SUPABASE_DB_POOLER_URL avec le Session pooler (aws-*.pooler.supabase.com:5432).",
            _host,
        )
    if _port == 6543:
        logger.warning(
            "Postgres via %s:6543 : souvent IPv6-only (timeout sur Windows sans IPv6). "
            "Definis SUPABASE_DB_POOLER_URL avec le Session pooler "
            "(Connect → Session pooler : postgres.VOTRE_REF @ aws-0|aws-1-*.pooler.supabase.com:5432). "
            "Script : python sam/scripts/fix_supabase_pooler_env.py",
            _host,
        )

# Transaction pooler Supabase (db.*.supabase.co:6543) : pas de prepared statements côté pooler.
_is_supabase_transaction_pooler = (
    _host.endswith(".supabase.co") and _host.startswith("db.") and _port == 6543
)

_connect_timeout = int(os.getenv("SUPABASE_DB_CONNECT_TIMEOUT", "25"))

_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "future": True,
    "pool_recycle": int(os.getenv("SUPABASE_DB_POOL_RECYCLE", "1800")),
    "connect_args": {
        "connect_timeout": _connect_timeout,
    },
}
if _is_supabase_transaction_pooler:
    _engine_kwargs["query_cache_size"] = 0
    logger.info(
        "Moteur SQLAlchemy : query_cache_size=0 pour le transaction pooler Supabase (port 6543)."
    )

engine = create_engine(
    DATABASE_URL,
    **_engine_kwargs,
)
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

