from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from .cache import cache_get, cache_set
from .db import get_db
from .rag import initialize_chatbot, process_user_input


app = FastAPI(
    title="Mosam CEDEAO Classification API",
    version="0.1.0",
    description="API de classification tarifaire CEDEAO (RAG + OpenAI)",
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ClassifyRequest(BaseModel):
    """Requête de classification d'une ou plusieurs marchandises."""

    query: str


class ClassifyResponse(BaseModel):
    """Réponse brute renvoyée par le LLM (JSON sérialisé en texte)."""

    raw: str


class UserCreate(BaseModel):
    """Données nécessaires à la création d'un utilisateur simple."""

    nom_user: str
    identifiant_user: str
    email: str
    is_admin: bool = False


@app.on_event("startup")
def startup_event() -> None:
    """
    Initialise le moteur RAG (chunks + index FAISS) une seule fois au démarrage.
    Les objets sont stockés sur l'application pour être réutilisés par les endpoints.
    """

    chunks, index = initialize_chatbot()
    app.state.chunks = chunks
    app.state.index = index


@app.get("/health", tags=["system"])
def health() -> dict:
    """Endpoint de healthcheck simple."""

    return {"status": "ok"}


@app.post("/classify", response_model=ClassifyResponse, tags=["classification"])
def classify(payload: ClassifyRequest) -> ClassifyResponse:
    """
    Classe une ou plusieurs marchandises.

    - `query` : texte libre saisi par l'utilisateur (peut contenir plusieurs articles).
    - Retourne la chaîne brute produite par le modèle (JSON sérialisé) dans le champ `raw`.
    """

    # Clé de cache partagée entre tous les utilisateurs (Upstash Redis)
    cache_key = f"classify:{payload.query.strip().lower()}"
    cached_raw = cache_get(cache_key)
    if cached_raw is not None:
        return ClassifyResponse(raw=cached_raw)

    try:
        chunks = app.state.chunks
        index = app.state.index
    except AttributeError as exc:
        raise HTTPException(status_code=503, detail="Moteur RAG non initialisé") from exc

    try:
        result = process_user_input(payload.query, chunks, index)
    except Exception as exc:  # pragma: no cover - garde-fou
        import traceback

        print(traceback.format_exc())
        detail = f"{type(exc).__name__}: {exc}" if str(exc) else f"{type(exc).__name__}"
        raise HTTPException(status_code=500, detail=detail) from exc

    # Mise en cache best-effort du résultat brut (par ex. 1h)
    cache_set(cache_key, result, ex=3600)

    # Persistance best-effort dans la base de données (table classifications)
    try:
        parsed = json.loads(result)
        classifications = parsed.get("classifications") or []
        if isinstance(classifications, list) and classifications:
            now = datetime.now(timezone.utc)

            with get_db() as db:
                for item in classifications:
                    if not isinstance(item, dict):
                        continue

                    db.execute(
                        text(
                            """
                            insert into public.classifications
                            (description_produit,
                             section_produit,
                             code_tarifaire,
                             classification_confidence,
                             statut_validation,
                             created_at)
                            values (:description, :section, :code, :confidence, :statut, :created_at)
                            """
                        ),
                        {
                            "description": item.get("description")
                            or item.get("product", {}).get("description"),
                            "section": item.get("section"),
                            "code": item.get("hs_code") or item.get("code"),
                            "confidence": item.get("confidence"),
                            "statut": "non_validé",
                            "created_at": now,
                        },
                    )
                db.commit()
    except Exception:
        # En cas de problème de parsing/écriture, on n'empêche pas la réponse.
        pass

    return ClassifyResponse(raw=result)


@app.get("/history", tags=["history"])
def get_history() -> list[dict]:
    """
    Retourne l'historique des classifications depuis la base Supabase.
    """

    with get_db() as db:
        rows = db.execute(
            text(
                """
                select
                  description_produit,
                  section_produit,
                  code_tarifaire,
                  classification_confidence,
                  statut_validation,
                  created_at as date_classification
                from public.classifications
                order by created_at desc
                limit 1000
                """
            )
        ).mappings().all()

        return [dict(row) for row in rows]


@app.get("/users", tags=["users"])
def get_users() -> list[dict]:
    """Retourne la liste des utilisateurs depuis la base Supabase."""

    with get_db() as db:
        rows = db.execute(
            text(
                """
                select
                  id as user_id,
                  nom_user,
                  identifiant_user,
                  email,
                  statut,
                  is_admin
                from public.users
                order by created_at asc
                """
            )
        ).mappings().all()
        return [dict(row) for row in rows]


@app.post("/users", tags=["users"])
def create_user(payload: UserCreate) -> dict:
    """Crée un nouvel utilisateur dans la base Supabase."""

    with get_db() as db:
        row = db.execute(
            text(
                """
                insert into public.users
                (nom_user, identifiant_user, email, is_admin, statut)
                values (:nom_user, :identifiant_user, :email, :is_admin, 'actif')
                returning
                  id as user_id,
                  nom_user,
                  identifiant_user,
                  email,
                  statut,
                  is_admin
                """
            ),
            {
                "nom_user": payload.nom_user,
                "identifiant_user": payload.identifiant_user,
                "email": payload.email,
                "is_admin": payload.is_admin,
            },
        ).mappings().one()
        db.commit()
        return dict(row)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
