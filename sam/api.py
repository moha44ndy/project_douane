from pathlib import Path
from typing import Optional, Any
import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .rag import initialize_chatbot, process_user_input


BASE_DIR = Path(__file__).resolve().parent
TABLE_DATA_PATH = BASE_DIR / "table_data.json"
USERS_PATH = BASE_DIR / "users.json"


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


def _load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_json_list(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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

    # Persistance best-effort dans l'historique local
    try:
        parsed = json.loads(result)
        classifications = parsed.get("classifications") or []
        if isinstance(classifications, list) and classifications:
            history = _load_json_list(TABLE_DATA_PATH)
            now = datetime.now(timezone.utc).isoformat()

            for item in classifications:
                if not isinstance(item, dict):
                    continue
                entry: dict[str, Any] = {
                    "description_produit": item.get("description")
                    or item.get("product", {}).get("description"),
                    "section_produit": item.get("section"),
                    "code_tarifaire": item.get("hs_code") or item.get("code"),
                    "classification_confidence": item.get("confidence"),
                    "statut_validation": "non_validé",
                    "date_classification": now,
                }
                # Ne pas ajouter d'entrées totalement vides
                if any(v is not None for v in entry.values()):
                    history.append(entry)

            _save_json_list(TABLE_DATA_PATH, history)
    except Exception:
        # En cas de problème de parsing/écriture, on n'empêche pas la réponse
        pass

    return ClassifyResponse(raw=result)


@app.get("/history", tags=["history"])
def get_history() -> list[dict]:
    """
    Retourne l'historique brut des classifications stocké dans `sam/table_data.json`.
    La structure est volontairement flexible pour rester compatible avec la version Streamlit.
    """

    return _load_json_list(TABLE_DATA_PATH)


@app.get("/users", tags=["users"])
def get_users() -> list[dict]:
    """Retourne la liste brute des utilisateurs (`sam/users.json`)."""

    return _load_json_list(USERS_PATH)


@app.post("/users", tags=["users"])
def create_user(payload: UserCreate) -> dict:
    """Crée un nouvel utilisateur et le persiste dans `sam/users.json`."""

    users = _load_json_list(USERS_PATH)
    new_id = max((u.get("user_id", 0) for u in users), default=0) + 1

    user = {
        "user_id": new_id,
        "nom_user": payload.nom_user,
        "identifiant_user": payload.identifiant_user,
        "email": payload.email,
        "statut": "actif",
        "is_admin": payload.is_admin,
    }
    users.append(user)
    _save_json_list(USERS_PATH, users)
    return user


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
