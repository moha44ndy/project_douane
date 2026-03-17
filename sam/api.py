from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal, Optional
import base64
import json as jsonlib

from fastapi import FastAPI, HTTPException, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
import requests

from .cache import (
    cache_clear_classify,
    cache_classify_is_disabled,
    cache_classify_set_disabled,
    cache_get,
    cache_set,
)
from .db import get_db
from .rag import initialize_chatbot, process_user_input
from .config.settings import Config


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
    # Optionnel : si fournis, la réponse complète est mise en cache pour cette requête
    # (cache utilisé uniquement lorsqu'au moins une classification est validée)
    query: str | None = None
    raw_response: str | None = None


# Mapping chapitre SH (2 chiffres) -> (section romain, libellé section) pour corriger les réponses LLM
HS_CHAPTER_TO_SECTION: dict[int, tuple[str, str]] = {
    **{c: ("I", "Animaux vivants et produits du règne animal") for c in range(1, 6)},
    **{c: ("II", "Produits du règne végétal") for c in range(6, 15)},
    15: ("III", "Matières grasses et huiles ; cires"),
    **{c: ("IV", "Produits des industries alimentaires ; boissons ; tabacs") for c in range(16, 25)},
    **{c: ("V", "Produits minéraux") for c in range(25, 28)},
    **{c: ("VI", "Produits des industries chimiques") for c in range(28, 39)},
    **{c: ("VII", "Matières plastiques et caoutchouc") for c in range(39, 41)},
    **{c: ("VIII", "Peaux, cuirs, fourrures") for c in range(41, 44)},
    **{c: ("IX", "Bois, liège, vannerie") for c in range(44, 47)},
    **{c: ("X", "Pâtes de bois ; papier") for c in range(47, 50)},
    **{c: ("XI", "Textiles") for c in range(50, 64)},
    **{c: ("XII", "Chaussures ; coiffure ; parapluies") for c in range(64, 68)},
    **{c: ("XIII", "Pierre, plâtre, ciment ; verre ; céramique") for c in range(68, 72)},
    71: ("XIV", "Perles, pierres précieuses ; métaux précieux"),
    **{c: ("XV", "Métaux communs et ouvrages") for c in range(72, 84)},
    **{c: ("XVI", "Machines et appareils ; matériel électrique") for c in range(84, 86)},
    **{c: ("XVII", "Matériel de transport") for c in range(86, 90)},
    **{c: ("XVIII", "Instruments optiques, photographiques ; horlogerie ; instruments de précision") for c in range(90, 93)},
    93: ("XIX", "Armes et munitions"),
    **{c: ("XX", "Articles manufacturés divers") for c in range(94, 97)},
    **{c: ("XXI", "Œuvres d'art ; antiquités") for c in range(97, 100)},
}


def _normalize_section_chapter_from_hs(hs_code: str | None) -> dict[str, str]:
    """À partir d'un code SH (ex: 8517.13.00.00 ou 2008.19), déduit section et chapitre corrects."""
    if not hs_code or not isinstance(hs_code, str):
        return {}
    part = hs_code.strip().split(".")[0]
    if len(part) < 2:
        return {}
    try:
        ch = int(part[:2])
    except ValueError:
        return {}
    if ch < 1 or ch > 99:
        return {}
    section_roman, section_name = HS_CHAPTER_TO_SECTION.get(ch, ("", ""))
    return {
        "section": section_roman,
        "section_name": section_name,
        "chapter": f"{ch:02d}",
        "chapter_name": f"Chapitre {ch:02d}",
    }


def _normalize_classifications_response(raw_text: str) -> str:
    """
    Parse la réponse JSON du LLM, corrige section/chapitre à partir du code SH pour chaque
    classification, puis resérialise. Limite le nombre de lignes pour éviter les décompositions abusives.
    """
    if not raw_text or not raw_text.strip():
        return raw_text
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip("` \n\r")
    try:
        data = json.loads(stripped)
    except Exception:
        return raw_text
    if not isinstance(data, dict):
        return raw_text
    classifications = data.get("classifications")
    if not isinstance(classifications, list):
        return raw_text
    for item in classifications:
        if not isinstance(item, dict):
            continue
        hs = item.get("hs_code")
        if not hs:
            continue
        s = str(hs).strip().upper()
        if s in ("NON APPLICABLE", "NON RENSEIGNÉ", "N/A", "NA") or len(s) < 4:
            continue
        if not s.replace(".", "").replace(" ", "").isdigit():
            continue
        normalized = _normalize_section_chapter_from_hs(str(hs))
        if normalized:
            if normalized.get("section"):
                item["section"] = normalized["section"]
            if normalized.get("section_name"):
                item["section_name"] = normalized["section_name"]
            if normalized.get("chapter"):
                item["chapter"] = normalized["chapter"]
            if normalized.get("chapter_name"):
                item["chapter_name"] = normalized["chapter_name"]
    return json.dumps(data, ensure_ascii=False)


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


class UserUpdate(BaseModel):
    """
    Données autorisées pour la mise à jour d'un utilisateur.

    Tous les champs sont facultatifs pour permettre des PATCH partiels.
    """

    nom_user: Optional[str] = None
    identifiant_user: Optional[str] = None
    email: Optional[str] = None
    is_admin: Optional[bool] = None
    statut: Optional[Literal["actif", "inactif", "supprimé"]] = None


class ResetPasswordResponse(BaseModel):
    """Réponse renvoyée après une réinitialisation de mot de passe."""

    user_id: str
    email: str
    new_password: str


class ClassificationStatusUpdate(BaseModel):
    """
    Données envoyées lorsqu'un admin force le statut d'une classification.
    """

    statut_validation: Literal["validé", "invalidé", "archivé"]


class AuditLogItem(BaseModel):
    id: str
    created_at: datetime
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    details: dict[str, Any] | None = None


@app.patch(
    "/classifications/{classification_id}/status",
    tags=["classification"],
)
def update_classification_status(
    classification_id: str,
    payload: ClassificationStatusUpdate,
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Met à jour le statut de validation d'une classification (admin uniquement).
    """

    actor_id = _require_admin(authorization)

    with get_db() as db:
        row = db.execute(
            text(
                """
                update public.classifications
                set statut_validation = :statut
                where id::text = :classification_id
                returning
                  id,
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
                "classification_id": classification_id,
                "statut": payload.statut_validation,
            },
        ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Classification introuvable.")

        db.commit()
        result = dict(row)

    _insert_audit_log(
        actor_id=actor_id,
        action="classification.update_status",
        entity_type="classification",
        entity_id=str(classification_id),
        details={
            "new_statut_validation": payload.statut_validation,
        },
    )

    return result


def _decode_supabase_jwt(token: str) -> dict | None:
    """
    Décodage best-effort du payload JWT Supabase (sans vérification de signature).

    On utilise uniquement cette info pour identifier l'utilisateur courant côté
    backend lorsque la requête provient de notre frontend de confiance.
    """

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # Ajoute le padding manquant si nécessaire
        padding = "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        return jsonlib.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None


def _require_admin(authorization: str | None) -> str:
    """
    Vérifie que le porteur du JWT est bien un admin.

    - Extrait l'id utilisateur depuis le token Supabase.
    - Vérifie dans public.users que is_admin = true pour cet id.
    - Retourne l'id utilisateur si admin, sinon lève HTTP 403.
    """

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Jeton d'authentification manquant")

    token = authorization.split(" ", 1)[1].strip()
    payload = _decode_supabase_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Jeton d'authentification invalide")

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Jeton d'authentification invalide")

    with get_db() as db:
        row = db.execute(
            text(
                """
                select is_admin
                from public.users
                where id = :user_id
                  and statut = 'actif'
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

        if not row or not row.get("is_admin"):
            raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")

    return user_id


def _create_supabase_auth_user(email: str, password: str) -> str | None:
    """
    Crée un utilisateur dans Supabase Auth via l'API d'admin.

    - Retourne l'id de l'utilisateur auth (string) en cas de succès.
    - Si la configuration Supabase Admin est absente, retourne simplement None
      sans lever d'erreur, pour conserver le comportement existant.
    """

    supabase_url = Config.SUPABASE_URL
    service_key = Config.SUPABASE_SERVICE_ROLE_KEY
    if not supabase_url or not service_key:
        # Configuration non fournie : on ne crée que dans public.users.
        return None

    url = f"{supabase_url.rstrip('/')}/auth/v1/admin/users"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    if not resp.ok:
        # On journalise l'erreur côté serveur mais on n'empêche pas
        # la création dans public.users, pour ne pas bloquer l'admin.
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        print(f"[Supabase Auth] Echec creation user {email}: {detail}")
        return None

    data = resp.json()
    # id est le champ standard dans auth.users
    return data.get("id")


def _reset_supabase_auth_password(email: str, new_password: str) -> None:
    """
    Réinitialise le mot de passe d'un utilisateur Supabase Auth à partir de son email.

    Best-effort :
    - Si la configuration Supabase n'est pas fournie ou si l'appel échoue,
      on ne bloque pas la route ; on se contente de journaliser l'erreur.
    """

    supabase_url = Config.SUPABASE_URL
    service_key = Config.SUPABASE_SERVICE_ROLE_KEY
    if not supabase_url or not service_key:
        return

    base_url = supabase_url.rstrip("/")
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    # 1. Recherche de l'utilisateur Auth par email
    try:
        list_resp = requests.get(
            f"{base_url}/auth/v1/admin/users",
            headers=headers,
            params={"email": email, "per_page": 1},
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover - garde-fou réseau
        print(f"[Supabase Auth] Erreur réseau lors de la recherche user {email}: {exc}")
        return

    if not list_resp.ok:
        print(
            f"[Supabase Auth] Echec recherche user {email}: "
            f"{list_resp.status_code} {list_resp.text}"
        )
        return

    try:
        users = list_resp.json()
    except Exception:
        print(f"[Supabase Auth] Réponse JSON invalide lors de la recherche user {email}")
        return

    if isinstance(users, dict) and "users" in users:
        users_list = users.get("users") or []
    else:
        users_list = users if isinstance(users, list) else []

    if not users_list:
        print(f"[Supabase Auth] Aucun compte Auth trouvé pour {email}")
        return

    auth_id = users_list[0].get("id")
    if not auth_id:
        print(f"[Supabase Auth] Réponse sans id pour {email}")
        return

    # 2. Mise à jour du mot de passe pour cet id
    try:
        update_resp = requests.put(
            f"{base_url}/auth/v1/admin/users/{auth_id}",
            headers=headers,
            json={"password": new_password},
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover - garde-fou réseau
        print(
            f"[Supabase Auth] Erreur réseau lors de la mise à jour du "
            f"mot de passe pour {email}: {exc}"
        )
        return

    if not update_resp.ok:
        print(
            f"[Supabase Auth] Echec mise à jour mot de passe pour {email}: "
            f"{update_resp.status_code} {update_resp.text}"
        )


def _insert_audit_log(
    *,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict | None = None,
) -> None:
    """
    Insère une entrée dans la table d'audit.

    Best-effort : en cas d'erreur, on journalise mais on ne bloque pas la requête.
    """

    from uuid import uuid4

    payload_details = details or {}
    try:
        details_json = json.dumps(payload_details, ensure_ascii=False)
    except Exception:
        # En cas de problème de sérialisation, on force un dict minimal.
        details_json = json.dumps({"error": "unserializable details"})

    now = datetime.now(timezone.utc)

    try:
        with get_db() as db:
            db.execute(
                text(
                    """
                    insert into public.audit_logs (
                      id,
                      created_at,
                      actor_id,
                      action,
                      entity_type,
                      entity_id,
                      details
                    )
                    values (
                      :id,
                      :created_at,
                      :actor_id,
                      :action,
                      :entity_type,
                      :entity_id,
                      :details
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "created_at": now,
                    "actor_id": actor_id,
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "details": details_json,
                },
            )
            db.commit()
    except Exception as exc:  # pragma: no cover - garde-fou
        print(f"[AUDIT] Echec insertion log {action} sur {entity_type}:{entity_id}: {exc}")


def _delete_supabase_auth_user(email: str) -> None:
    """
    Supprime un utilisateur dans Supabase Auth à partir de son email.

    Best-effort :
    - Si la configuration Supabase n'est pas fournie ou si l'appel échoue,
      on ne bloque pas la route ; on se contente de journaliser l'erreur.
    """

    supabase_url = Config.SUPABASE_URL
    service_key = Config.SUPABASE_SERVICE_ROLE_KEY
    if not supabase_url or not service_key:
        return

    base_url = supabase_url.rstrip("/")
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }

    try:
        list_resp = requests.get(
            f"{base_url}/auth/v1/admin/users",
            headers=headers,
            params={"email": email, "per_page": 1},
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover - garde-fou réseau
        print(f"[Supabase Auth] Erreur réseau lors de la recherche user {email}: {exc}")
        return

    if not list_resp.ok:
        print(
            f"[Supabase Auth] Echec recherche user {email} avant suppression: "
            f"{list_resp.status_code} {list_resp.text}"
        )
        return

    try:
        users = list_resp.json()
    except Exception:
        print(f"[Supabase Auth] Réponse JSON invalide lors de la recherche user {email}")
        return

    if isinstance(users, dict) and "users" in users:
        users_list = users.get("users") or []
    else:
        users_list = users if isinstance(users, list) else []

    if not users_list:
        print(f"[Supabase Auth] Aucun compte Auth trouvé pour {email} à supprimer")
        return

    auth_id = users_list[0].get("id")
    if not auth_id:
        print(f"[Supabase Auth] Réponse sans id pour {email} à la suppression")
        return

    try:
        delete_resp = requests.delete(
            f"{base_url}/auth/v1/admin/users/{auth_id}",
            headers=headers,
            timeout=10,
        )
    except Exception as exc:  # pragma: no cover - garde-fou réseau
        print(
            f"[Supabase Auth] Erreur réseau lors de la suppression du "
            f"compte Auth pour {email}: {exc}"
        )
        return

    if not delete_resp.ok:
        print(
            f"[Supabase Auth] Echec suppression compte Auth pour {email}: "
            f"{delete_resp.status_code} {delete_resp.text}"
        )


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
    - Le résultat n'est mis en cache que lorsqu'une classification est validée (voir POST /classifications/validate).
    """

    # Vérifier si une réponse a déjà été mise en cache (sauf si le cache est désactivé)
    cache_key = f"classify:{payload.query.strip().lower()}"
    if not cache_classify_is_disabled():
        cached_raw = cache_get(cache_key)
        if cached_raw is not None:
            if isinstance(cached_raw, dict) and "value" in cached_raw:
                cached_value = cached_raw["value"]
            else:
                cached_value = cached_raw
            # Toujours renvoyer du JSON que le frontend peut parser en une fois
            if isinstance(cached_value, (dict, list)):
                raw_out = json.dumps(cached_value, ensure_ascii=False)
            elif isinstance(cached_value, str):
                # Si la chaîne est du JSON encodé (ex: "{\"narrative\":...}"), décoder une fois
                s = cached_value.strip()
                if s.startswith('"') and s.endswith('"') and len(s) >= 2:
                    try:
                        decoded = json.loads(s)
                        if isinstance(decoded, str):
                            raw_out = decoded
                        else:
                            raw_out = json.dumps(decoded, ensure_ascii=False)
                    except Exception:
                        raw_out = cached_value
                else:
                    raw_out = cached_value
            else:
                raw_out = str(cached_value)
            return ClassifyResponse(raw=raw_out)

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

    # Corriger section/chapitre à partir du code SH pour chaque classification
    result = _normalize_classifications_response(result)

    # Ne pas mettre en cache ici : le cache est alimenté uniquement lors d'une validation
    # (POST /classifications/validate avec query + raw_response), pour ne pas retenir
    # les réponses non validées.

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
                  id,
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

    result = dict(row)

    # Mise en cache uniquement lorsqu'une classification est validée (et si le cache est activé)
    if not cache_classify_is_disabled() and payload.query and payload.raw_response:
        cache_key = f"classify:{payload.query.strip().lower()}"
        cache_set(cache_key, payload.raw_response, ex=3600)

    # Audit best-effort : validation d'une nouvelle classification
    user_id_for_audit = payload.user_id or "anonymous"
    _insert_audit_log(
        actor_id=user_id_for_audit,
        action="classification.validate",
        entity_type="classification",
        entity_id=str(result.get("id", "")),
        details={
            "hs_code": payload.hs_code,
            "section": payload.section,
            "chapter": payload.chapter,
            "statut_validation": "validé",
        },
    )

    return result


@app.get("/admin/cache/classify/status", tags=["admin"])
def get_classify_cache_status(
    authorization: str | None = Header(default=None),
) -> dict:
    """Retourne l'état du cache des classifications (activé / désactivé). Réservé aux admins."""
    _require_admin(authorization)
    return {"disabled": cache_classify_is_disabled()}


class CacheStatusUpdate(BaseModel):
    """Body pour activer/désactiver le cache des classifications."""
    disabled: bool


@app.patch("/admin/cache/classify/status", tags=["admin"])
def update_classify_cache_status(
    authorization: str | None = Header(default=None),
    payload: CacheStatusUpdate | None = None,
) -> dict:
    """Active ou désactive le cache des classifications. Réservé aux admins."""
    _require_admin(authorization)
    disabled = payload.disabled if payload else False
    if not cache_classify_set_disabled(disabled):
        raise HTTPException(
            status_code=500,
            detail="Impossible de mettre à jour l'état du cache (vérifier la configuration Redis et les droits en écriture).",
        )
    return {"disabled": disabled}


@app.delete("/admin/cache/classify", tags=["admin"])
def clear_classify_cache(
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Vide le cache des réponses de classification (clés classify:*).
    Réservé aux administrateurs. Utile après mise à jour du prompt ou des documents RAG.
    """
    _require_admin(authorization)
    deleted = cache_clear_classify()
    return {"cleared": True, "keys_deleted": deleted}


@app.get("/history", tags=["history"])
def get_history(user_id: str | None = None) -> list[dict]:
    """
    Retourne l'historique des classifications depuis la base Supabase.

    Cet endpoint reste orienté "utilisateur final" (filtre par user_id éventuel)
    et ne nécessite pas de droits administrateur.
    """

    base_sql = """
        select
          c.id,
          c.description_produit,
          c.section_produit,
          c.chapitre_produit,
          c.code_tarifaire,
          c.classification_confidence,
          c.dd_rate,
          c.rs_rate,
          c.other_taxes,
          c.us_unit,
          c.origin,
          c.value,
          c.statut_validation,
          c.created_at as date_classification,
          c.user_id,
          u.nom_user as agent_name,
          u.id as agent_id
        from public.classifications c
        left join public.users u on u.id = c.user_id
    """

    params: dict[str, Any] = {}
    if user_id:
        base_sql += " where c.user_id = :user_id"
        params["user_id"] = user_id

    base_sql += " order by c.created_at desc limit 1000"

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
        "id",
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
        "user_id",
        "agent_name",
        "agent_id",
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
def get_users(
    authorization: str | None = Header(default=None),
    search: str | None = None,
    statut: str | None = None,
    is_admin: bool | None = None,
) -> list[dict]:
    """
    Retourne la liste des utilisateurs depuis la base Supabase.

    Filtres optionnels:
    - search : recherche texte sur nom, identifiant, email
    - statut : 'actif', 'inactif', 'supprimé'
    - is_admin : true / false
    """

    _require_admin(authorization)

    base_sql = """
        select
          id as user_id,
          nom_user,
          identifiant_user,
          email,
          statut,
          is_admin
        from public.users
    """
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if statut:
        conditions.append("statut = :statut")
        params["statut"] = statut

    if is_admin is not None:
        conditions.append("is_admin = :is_admin")
        params["is_admin"] = is_admin

    if search:
        conditions.append(
            "("
            "lower(nom_user) like :search "
            "or lower(identifiant_user) like :search "
            "or lower(email) like :search"
            ")"
        )
        params["search"] = f"%{search.strip().lower()}%"

    if conditions:
        base_sql += " where " + " and ".join(conditions)

    base_sql += " order by created_at asc"

    with get_db() as db:
        rows = db.execute(text(base_sql), params).mappings().all()
        return [dict(row) for row in rows]


@app.get("/users.csv", tags=["users"])
def export_users_csv(
    authorization: str | None = Header(default=None),
    search: str | None = None,
    statut: str | None = None,
    is_admin: bool | None = None,
) -> Response:
    """
    Exporte la liste des utilisateurs au format CSV, avec les mêmes filtres
    que l'endpoint JSON /users.
    """

    rows = get_users(
        authorization=authorization,
        search=search,
        statut=statut,
        is_admin=is_admin,
    )

    headers = [
        "user_id",
        "nom_user",
        "identifiant_user",
        "email",
        "statut",
        "is_admin",
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
        headers={"Content-Disposition": 'attachment; filename="utilisateurs.csv"'},
    )


@app.get("/audit-logs", tags=["audit"])
def get_audit_logs(
    authorization: str | None = Header(default=None),
    actor_id: str | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    Retourne les entrées d'audit (admin uniquement), avec filtres simples.
    """

    _require_admin(authorization)

    base_sql = """
        select
          l.id,
          l.created_at,
          l.actor_id,
          l.action,
          l.entity_type,
          l.entity_id,
          l.details::jsonb as details,
          u.nom_user as actor_name,
          coalesce(eu.nom_user, ec.description_produit) as entity_name
        from public.audit_logs l
        left join public.users u
          on u.id::text = l.actor_id
        left join public.users eu
          on l.entity_type = 'user' and eu.id::text = l.entity_id
        left join public.classifications ec
          on l.entity_type = 'classification' and ec.id::text = l.entity_id
    """
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if actor_id:
        conditions.append("actor_id = :actor_id")
        params["actor_id"] = actor_id
    if entity_type:
        conditions.append("entity_type = :entity_type")
        params["entity_type"] = entity_type
    if action:
        conditions.append("action = :action")
        params["action"] = action
    if q:
        conditions.append("(actor_id ilike :q or action ilike :q or entity_id ilike :q)")
        params["q"] = f"%{q}%"
    if date_from:
        conditions.append("created_at >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("created_at <= :date_to")
        params["date_to"] = date_to

    if conditions:
        base_sql += " where " + " and ".join(conditions)

    base_sql += " order by created_at desc limit :limit"
    params["limit"] = max(1, min(limit, 500))

    with get_db() as db:
        rows = db.execute(text(base_sql), params).mappings().all()
        return [dict(row) for row in rows]


@app.get("/audit-logs.csv", tags=["audit"])
def export_audit_logs_csv(
    authorization: str | None = Header(default=None),
    actor_id: str | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
) -> Response:
    """
    Exporte les entrées d'audit au format CSV, avec les mêmes filtres que /audit-logs.
    """

    rows = get_audit_logs(
        authorization=authorization,
        actor_id=actor_id,
        entity_type=entity_type,
        action=action,
        q=q,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    headers = [
        "id",
        "created_at",
        "actor_id",
        "actor_name",
        "action",
        "entity_type",
        "entity_id",
        "entity_name",
        "details",
    ]

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(
            [
                row.get("id", ""),
                row.get("created_at", ""),
                row.get("actor_id", ""),
                row.get("actor_name", ""),
                row.get("action", ""),
                row.get("entity_type", ""),
                row.get("entity_id", ""),
                row.get("entity_name", ""),
                row.get("details", ""),
            ]
        )

    content = output.getvalue()
    output.close()

    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit_logs.csv"'},
    )


@app.patch("/users/{user_id}", tags=["users"])
def update_user(
    user_id: str,
    payload: UserUpdate,
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Met à jour les informations d'un utilisateur (nom, email, identifiant, rôle, statut).
    """

    admin_id = _require_admin(authorization)

    # Normalisation des champs fournis
    fields_to_update: dict[str, Any] = {}
    if payload.nom_user is not None:
        nom = payload.nom_user.strip()
        if not nom:
            raise HTTPException(status_code=400, detail="Le nom complet est obligatoire.")
        fields_to_update["nom_user"] = nom
    if payload.identifiant_user is not None:
        identifiant = payload.identifiant_user.strip()
        if not identifiant:
            raise HTTPException(status_code=400, detail="L'identifiant est obligatoire.")
        if " " in identifiant:
            raise HTTPException(
                status_code=400,
                detail="L'identifiant ne doit pas contenir d'espace.",
            )
        fields_to_update["identifiant_user"] = identifiant
    if payload.email is not None:
        email = payload.email.strip().lower()
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="L'email fourni n'est pas valide.")
        fields_to_update["email"] = email
    if payload.is_admin is not None:
        # Empêche un administrateur de se retirer lui-même ses droits.
        if user_id == admin_id and payload.is_admin is False:
            raise HTTPException(
                status_code=400,
                detail="Vous ne pouvez pas retirer vos propres droits administrateur.",
            )
        fields_to_update["is_admin"] = payload.is_admin
    if payload.statut is not None:
        # Empêche un administrateur de se désactiver ou de se supprimer lui-même.
        if user_id == admin_id and payload.statut in {"inactif", "supprimé"}:
            raise HTTPException(
                status_code=400,
                detail="Vous ne pouvez pas désactiver ou supprimer votre propre compte.",
            )
        fields_to_update["statut"] = payload.statut

    if not fields_to_update:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour.")

    with get_db() as db:
        # Vérifie que l'utilisateur existe
        existing = db.execute(
            text(
                """
                select id
                from public.users
                where id = :user_id
                """
            ),
            {"user_id": user_id},
        ).first()
        if not existing:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

        # Vérification d'unicité email / identifiant si modifiés
        if "email" in fields_to_update or "identifiant_user" in fields_to_update:
            email = fields_to_update.get("email")
            identifiant = fields_to_update.get("identifiant_user")
            checks: list[str] = []
            params: dict[str, Any] = {"user_id": user_id}
            if email:
                checks.append("lower(email) = :email")
                params["email"] = email
            if identifiant:
                checks.append("lower(identifiant_user) = :identifiant")
                params["identifiant"] = identifiant.lower()

            if checks:
                sql = (
                    "select 1 from public.users "
                    "where (" + " or ".join(checks) + ") "
                    "and id <> :user_id limit 1"
                )
                exists = db.execute(text(sql), params).first()
                if exists:
                    raise HTTPException(
                        status_code=400,
                        detail="Cet email ou identifiant est déjà utilisé.",
                    )

        # Construction dynamique de la requête UPDATE
        set_clauses = [f"{col} = :{col}" for col in fields_to_update.keys()]
        params = dict(fields_to_update)
        params["user_id"] = user_id

        row = db.execute(
            text(
                f"""
                update public.users
                set {", ".join(set_clauses)}
                where id = :user_id
                returning
                  id as user_id,
                  nom_user,
                  identifiant_user,
                  email,
                  statut,
                  is_admin
                """
            ),
            params,
        ).mappings().one()
        db.commit()
        result = dict(row)

    # Audit best-effort : mise à jour d'utilisateur
    _insert_audit_log(
        actor_id=admin_id,
        action="user.update",
        entity_type="user",
        entity_id=str(user_id),
        details=fields_to_update,
    )

    return result


@app.delete("/users/{user_id}", tags=["users"])
def delete_user(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Supprime complètement un utilisateur (table public.users) après avoir tenté
    de supprimer son compte dans Supabase Auth.
    """

    admin_id = _require_admin(authorization)

    if user_id == admin_id:
        raise HTTPException(
            status_code=400,
            detail="Vous ne pouvez pas supprimer votre propre compte administrateur.",
        )

    with get_db() as db:
        # On récupère l'email avant suppression pour supprimer aussi dans Auth.
        existing = db.execute(
            text(
                """
                select email
                from public.users
                where id = :user_id
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

        if not existing:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

        email = existing.get("email")

        row = db.execute(
            text(
                """
                delete from public.users
                where id = :user_id
                returning
                  id as user_id,
                  nom_user,
                  identifiant_user,
                  email
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

        db.commit()

    # Suppression best-effort du compte Auth correspondant.
    if email:
        _delete_supabase_auth_user(email=email)

    # Audit best-effort : suppression d'utilisateur
    _insert_audit_log(
        actor_id=admin_id,
        action="user.delete",
        entity_type="user",
        entity_id=str(user_id),
        details={"email": email},
    )

    return dict(row) if row else {"user_id": user_id}


@app.post("/users/{user_id}/reset-password", tags=["users"])
def reset_user_password(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> ResetPasswordResponse:
    """
    Réinitialise le mot de passe d'un utilisateur.

    - Génère un nouveau mot de passe aléatoire.
    - Met à jour le compte Supabase Auth correspondant (si configuré).
    - Ne modifie pas la table public.users (les mots de passe y sont gérés par Supabase Auth).
    """

    import secrets
    import string

    admin_id = _require_admin(authorization)

    # Génération d'un mot de passe robuste et lisible (6 caractères, lettres, chiffres, symboles)
    alphabet = string.ascii_letters + string.digits + "@#$%&*?!"
    new_password = "".join(secrets.choice(alphabet) for _ in range(6))

    with get_db() as db:
        row = db.execute(
            text(
                """
                select id::text as user_id, email
                from public.users
                where id = :user_id
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

        email = row.get("email")
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Impossible de réinitialiser le mot de passe : email manquant.",
            )

    # Mise à jour best-effort côté Supabase Auth
    _reset_supabase_auth_password(email=email, new_password=new_password)

    resp = ResetPasswordResponse(
        user_id=row["user_id"],
        email=email,
        new_password=new_password,
    )

    # Audit best-effort : reset mot de passe
    _insert_audit_log(
        actor_id=admin_id,
        action="user.reset_password",
        entity_type="user",
        entity_id=str(row["user_id"]),
        details={"email": email},
    )

    return resp


@app.post("/users", tags=["users"])
def create_user(
    payload: UserCreate,
    authorization: str | None = Header(default=None),
) -> dict:
    """Crée un nouvel utilisateur dans la base Supabase."""

    admin_id = _require_admin(authorization)

    # Validation / normalisation basique des champs
    nom_user = (payload.nom_user or "").strip()
    identifiant = (payload.identifiant_user or "").strip()
    email = (payload.email or "").strip().lower()

    if not nom_user:
        raise HTTPException(status_code=400, detail="Le nom complet est obligatoire.")
    if not identifiant:
        raise HTTPException(status_code=400, detail="L'identifiant est obligatoire.")
    if " " in identifiant:
        raise HTTPException(
            status_code=400,
            detail="L'identifiant ne doit pas contenir d'espace.",
        )
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="L'email fourni n'est pas valide.")

    # Vérification d'unicité email / identifiant
    with get_db() as db:
        exists = db.execute(
            text(
                """
                select 1
                from public.users
                where lower(email) = :email
                   or lower(identifiant_user) = :identifiant
                limit 1
                """
            ),
            {"email": email, "identifiant": identifiant.lower()},
        ).first()

        if exists:
            raise HTTPException(
                status_code=400,
                detail="Cet email ou identifiant est déjà utilisé.",
            )

    # On génère un mot de passe initial aléatoire (6 caractères, lettres, chiffres, symboles),
    # que l'admin pourra communiquer à l'utilisateur (qui devra ensuite le changer).
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits + "@#$%&*?!"
    initial_password = "".join(secrets.choice(alphabet) for _ in range(6))

    auth_user_id: str | None = _create_supabase_auth_user(
        email=email,
        password=initial_password,
    )

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
                "nom_user": nom_user,
                "identifiant_user": identifiant,
                "email": email,
                "is_admin": payload.is_admin,
            },
        ).mappings().one()
        db.commit()
        result = dict(row)
        # On ajoute l'info d'id Auth si on l'a, à titre informatif,
        # ainsi que le mot de passe initial généré côté serveur.
        if auth_user_id is not None:
            result["auth_user_id"] = auth_user_id
        result["initial_password"] = initial_password

    # Audit best-effort : création d'utilisateur
    _insert_audit_log(
        actor_id=admin_id,
        action="user.create",
        entity_type="user",
        entity_id=str(result.get("user_id", "")),
        details={
            "nom_user": nom_user,
            "identifiant_user": identifiant,
            "email": email,
            "is_admin": payload.is_admin,
        },
    )

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
