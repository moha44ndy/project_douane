from __future__ import annotations

import json
from typing import Any, Optional

import requests

from .config.settings import Config


_URL = Config.UPSTASH_REDIS_REST_URL
_TOKEN = Config.UPSTASH_REDIS_REST_TOKEN


def _enabled() -> bool:
    return bool(_URL and _TOKEN)


def cache_set(key: str, value: Any, ex: Optional[int] = None) -> None:
    """
    Stocke une valeur JSON dans Upstash Redis.

    key: clé de cache
    value: objet sérialisable JSON
    ex: expiration en secondes (optionnel)
    """
    if not _enabled():
        return

    payload = {"value": json.dumps(value)}
    if ex is not None:
        payload["ex"] = ex

    try:
        requests.post(
            f"{_URL}/set/{key}",
            headers={"Authorization": f"Bearer {_TOKEN}"},
            json=payload,
            timeout=2,
        )
    except Exception:
        # Cache best-effort: on ignore les erreurs
        return


def cache_get(key: str) -> Optional[Any]:
    """
    Récupère une valeur JSON depuis Upstash Redis.
    Retourne None si non trouvé ou en cas d'erreur.
    """
    if not _enabled():
        return None

    try:
        resp = requests.get(
            f"{_URL}/get/{key}",
            headers={"Authorization": f"Bearer {_TOKEN}"},
            timeout=2,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        # Upstash renvoie {"result": "...."} ou similaire
        raw = data.get("result")
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None

