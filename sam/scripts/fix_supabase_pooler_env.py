"""Met a jour SUPABASE_DB_POOLER_URL (Session pooler IPv4) depuis SUPABASE_DB_URL."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

REGIONS = (
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-central-1",
    "eu-north-1",
    "us-east-1",
    "us-west-1",
    "ap-southeast-1",
    "ap-northeast-1",
    "ap-south-1",
    "ca-central-1",
    "sa-east-1",
)


def _project_ref(direct_url: str, supabase_url: str) -> str:
    parsed = urlparse(direct_url)
    host = (parsed.hostname or "").lower()
    if host.startswith("db.") and host.endswith(".supabase.co"):
        return host.removeprefix("db.").removesuffix(".supabase.co")
    if supabase_url:
        hostname = urlparse(supabase_url).hostname or ""
        return hostname.split(".")[0]
    return ""


def build_pooler_url(password: str, project_ref: str, pooler_host: str, port: int = 5432) -> str:
    user = f"postgres.{project_ref}"
    netloc = f"{user}:{quote(password, safe='')}@{pooler_host}:{port}"
    return urlunparse(("postgresql", netloc, "/postgres", "", "sslmode=require", ""))


def find_session_pooler_host(password: str, project_ref: str) -> str | None:
    import psycopg2

    user = f"postgres.{project_ref}"
    for prefix in ("aws-1", "aws-0"):
        for region in REGIONS:
            host = f"{prefix}-{region}.pooler.supabase.com"
            try:
                conn = psycopg2.connect(
                    host=host,
                    port=5432,
                    user=user,
                    password=password,
                    dbname="postgres",
                    sslmode="require",
                    connect_timeout=6,
                )
                conn.close()
                return host
            except Exception as exc:
                message = str(exc).lower()
                if "password authentication failed" in message:
                    raise RuntimeError(
                        "Mot de passe Postgres refuse par le pooler. "
                        "Supabase → Project Settings → Database → Reset database password, "
                        "puis mettez a jour SUPABASE_DB_URL."
                    ) from exc
                continue
    return None


def main() -> int:
    load_dotenv(ENV_PATH)
    import os

    direct = (os.getenv("SUPABASE_DB_URL") or "").strip()
    if not direct:
        print("SUPABASE_DB_URL manquant dans .env", file=sys.stderr)
        return 1

    parsed = urlparse(direct)
    password = parsed.password or ""
    project_ref = _project_ref(direct, (os.getenv("SUPABASE_URL") or "").strip())
    if not project_ref or not password:
        print("Project ref ou mot de passe Postgres introuvable", file=sys.stderr)
        return 1

    pooler_host = find_session_pooler_host(password, project_ref)
    if not pooler_host:
        print(
            "Aucun pooler Session trouve pour ce projet. "
            "Copiez l'URI depuis Supabase → Connect → Session pooler.",
            file=sys.stderr,
        )
        return 1

    pooler = build_pooler_url(password, project_ref, pooler_host)
    text = ENV_PATH.read_text(encoding="utf-8")
    if re.search(r"^SUPABASE_DB_POOLER_URL=", text, flags=re.M):
        text = re.sub(
            r"^SUPABASE_DB_POOLER_URL=.*$",
            f"SUPABASE_DB_POOLER_URL={pooler}",
            text,
            flags=re.M,
        )
    else:
        text = (
            text.rstrip()
            + "\n\n# Session pooler IPv4 (prioritaire sur db.*.supabase.co, souvent IPv6-only)\n"
            + f"SUPABASE_DB_POOLER_URL={pooler}\n"
        )
    ENV_PATH.write_text(text, encoding="utf-8")
    print(f"SUPABASE_DB_POOLER_URL -> {pooler_host}:5432 (user postgres.{project_ref})")

    os.environ["SUPABASE_DB_POOLER_URL"] = pooler
    from importlib import reload

    import sam.config.settings as settings_mod
    import sam.db as db_mod

    reload(settings_mod)
    reload(db_mod)

    from sqlalchemy import text as sql_text

    with db_mod.engine.connect() as conn:
        value = conn.execute(sql_text("select 1")).scalar()
    print(f"Connexion Postgres OK (select 1 => {value})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
