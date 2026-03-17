from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Response
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
    # Identifiant de l'utilisateur (Supabase Auth ou table users),
    # facultatif pour compatibilité.
    user_id: str | None = None


class ClassifyResponse(BaseModel):
    """Réponse brute renvoyée par le LLM (JSON sérialisé en texte)."""

    raw: str


class ValidateClassificationRequest(BaseModel):
    """
    Données envoyées par le frontend lorsqu'un agent
    valide une classification précise.
    """

    description: str
    section: str
    chapter: str
    hs_code: str
    confidence: float | None = None
    dd_rate: str | None = None
    rs_rate: str | None = None
    other_taxes: str | None = None
    us_unit: str | None = None
    origin: str | None = None
    value: str | None = None
    user_id: str | None = None


def _extract_classifications(raw_text: str) -> list[dict]:
    """
    Essaie d'extraire la liste `classifications` à partir d'une chaîne brute.

    Gère plusieurs cas :
    - JSON direct: {"narrative": "...", "classifications": [...]}
    - JSON encodé en string: "\"{...}\""
    - Présence éventuelle de fences ```json ... ``` autour du JSON.
    """

    def _strip_fences(s: str) -> str:
        t = s.strip()
        if t.startswith("```"):
            # enlève ```json ou ``` puis la clôture finale ```
            t = t.strip("`")
            # si ça commence par json après les backticks
            if t.lower().startswith("json"):
                t = t[4:]
            return t.strip("` \n\r")
        return t

    current: object = raw_text
    for _ in range(3):
        if isinstance(current, str):
            candidate = _strip_fences(current)
            try:
                current = json.loads(candidate)
            except Exception:
                return []
        if isinstance(current, dict):
            classifications = current.get("classifications") or []
            return classifications if isinstance(classifications, list) else []
    return []


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
        # Compatibilité : certains anciens enregistrements peuvent encore
        # être au format {"value": "...", "ex": ...}. On en extrait la valeur.
        if isinstance(cached_raw, dict) and "value" in cached_raw:
            cached_value = cached_raw["value"]
        else:
            cached_value = cached_raw

        raw_str = str(cached_value)
        # Option A : en cas de hit cache, on renvoie simplement la réponse
        # sans rien enregistrer en base. La persistance se fait uniquement
        # via l'endpoint /classifications/validate.
        return ClassifyResponse(raw=raw_str)

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

    return ClassifyResponse(raw=result)


@app.post(
    "/classifications/validate",
    tags=["classification"],
)
def validate_classification(payload: ValidateClassificationRequest) -> dict:
    """
    Enregistre en base UNE classification choisie par un agent.

    Cette route est appelée depuis le frontend quand l'utilisateur
    clique sur "Valider cette classification" pour une ligne donnée.
    """
    now = datetime.now(timezone.utc)

    # On stocke déjà section et chapitre sous forme "numéro - libellé" côté frontend
    # (si le libellé est connu). On ne ré-interprète donc pas ici.
    section_label = payload.section or "N/A"
    chapter_label = payload.chapter or "N/A"

    with get_db() as db:
        row = db.execute(
            text(
                """
                insert into public.classifications
                (description_produit,
                 section_produit,
                 chapitre_produit,
                 code_tarifaire,
                 classification_confidence,
                 dd_rate,
                 rs_rate,
                 other_taxes,
                 us_unit,
                 origin,
                 value,
                 user_id,
                 statut_validation,
                 created_at)
                values (
                  :description,
                  :section,
                  :chapitre,
                  :code,
                  :confidence,
                  :dd_rate,
                  :rs_rate,
                  :other_taxes,
                  :us_unit,
                  :origin,
                  :value,
                  :user_id,
                  :statut,
                  :created_at
                )
                returning
                  description_produit,
                  section_produit,
                  chapitre_produit,
                  code_tarifaire,
                  classification_confidence,
                  dd_rate,
                  rs_rate,
                  other_taxes,
                  us_unit,
                  origin,
                  value,
                  user_id,
                  statut_validation,
                  created_at as date_classification
                """
            ),
            {
                "description": payload.description,
                "section": section_label,
                "chapitre": chapter_label,
                "code": payload.hs_code,
                "confidence": payload.confidence,
                "dd_rate": payload.dd_rate,
                "rs_rate": payload.rs_rate,
                "other_taxes": payload.other_taxes,
                "us_unit": payload.us_unit,
                "origin": payload.origin,
                "value": payload.value,
                "user_id": payload.user_id,
                "statut": "validé",
                "created_at": now,
            },
        ).mappings().one()
        db.commit()

    return dict(row)


@app.get("/history", tags=["history"])
def get_history(user_id: str | None = None) -> list[dict]:
    """
    Retourne l'historique des classifications depuis la base Supabase.
    """

    base_sql = """
        select
          description_produit,
          section_produit,
          chapitre_produit,
          code_tarifaire,
          classification_confidence,
          dd_rate,
          rs_rate,
          other_taxes,
          us_unit,
          origin,
          value,
          statut_validation,
          created_at as date_classification
        from public.classifications
    """

    params: dict[str, Any] = {}
    if user_id:
        base_sql += " where user_id = :user_id"
        params["user_id"] = user_id

    base_sql += " order by created_at desc limit 1000"

    with get_db() as db:
        rows = db.execute(text(base_sql), params).mappings().all()
        return [dict(row) for row in rows]


@app.get("/history.csv", tags=["history"])
def export_history_csv(user_id: str | None = None) -> Response:
    """
    Exporte l'historique des classifications au format CSV.

    Inclut les principaux champs utilisés dans l'interface.
    """
    rows = get_history(user_id=user_id)

    headers = [
        "description_produit",
        "section_produit",
        "chapitre_produit",
        "code_tarifaire",
        "classification_confidence",
        "dd_rate",
        "rs_rate",
        "other_taxes",
        "us_unit",
        "origin",
        "value",
        "statut_validation",
        "date_classification",
    ]

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])

    content = output.getvalue()
    output.close()

    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="historique.csv"'},
    )


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
