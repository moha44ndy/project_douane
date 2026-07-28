from __future__ import annotations

import json
import threading
import time
from typing import Any, Optional

import requests

from .config.settings import Config
from .app_logger import get_logger

logger = get_logger(__name__)

_URL = Config.UPSTASH_REDIS_REST_URL
_TOKEN = Config.UPSTASH_REDIS_REST_TOKEN

# Clé Redis pour désactiver le cache des classifications (valeur "1" = désactivé)
CLASSIFY_CACHE_DISABLED_KEY = "mosam:classify_cache_disabled"
_CLASSIFY_STATUS_TTL_SECONDS = 30.0
_CLASSIFY_STATUS_LOCK = threading.Lock()
_CLASSIFY_STATUS: dict[str, Any] = {
    "disabled": False,
    "expires_at": 0.0,
    "refreshing": False,
    "initialized": False,
}


def _enabled() -> bool:
    return bool(_URL and _TOKEN)


def cache_set(key: str, value: Any, ex: Optional[int] = None) -> bool:
    """
    Stocke une valeur dans Upstash Redis (même format que les autres commandes).
    value est sérialisé en JSON pour le stockage.
    """
    if not _enabled():
        logger.debug("[cache] SET skipped: Redis not configured key=%s", key)
        return False
    # Stocker en chaîne JSON pour pouvoir relire proprement
    value_str = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    cmd: list[Any] = ["SET", key, value_str]
    if ex is not None:
        cmd.extend(["EX", ex])
    try:
        resp = requests.post(
            _URL,
            headers={"Authorization": f"Bearer {_TOKEN}"},
            json=cmd,
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning("[cache] SET failed key=%s status=%s", key, resp.status_code)
            return False
        data = resp.json()
        if "error" in data:
            logger.warning("[cache] SET Redis error key=%s error=%s", key, data.get("error"))
            return False
        ok = data.get("result") == "OK"
        if not ok:
            logger.warning("[cache] SET unexpected result key=%s result=%r", key, data.get("result"))
        return ok
    except Exception as exc:
        logger.warning("[cache] SET failed key=%s error=%s", key, type(exc).__name__)
        return False


def cache_get(key: str) -> Optional[Any]:
    """
    Récupère une valeur depuis Upstash Redis (même format que les autres commandes).
    Retourne None si non trouvé ou en cas d'erreur.
    """
    if not _enabled():
        return None
    try:
        resp = requests.post(
            _URL,
            headers={"Authorization": f"Bearer {_TOKEN}"},
            json=["GET", key],
            timeout=5,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if "error" in data:
            return None
        raw = data.get("result")
        if raw is None:
            return None
        # Contrat : on renvoie la valeur brute sous forme de string.
        # Cela évite les double-encodages et rend le parsing front déterministe.
        if isinstance(raw, str):
            # Compat rétroactive : ancien format possible en wrapper {"value": "..."}
            try:
                decoded = json.loads(raw)
                # Legacy format is exactly {"value": "<payload>"}. Business
                # objects can also contain a `value` field and must stay intact.
                if isinstance(decoded, dict) and set(decoded) == {"value"}:
                    return decoded["value"]
            except json.JSONDecodeError:
                pass
            return raw
        # Si Upstash renvoie autre chose qu'une string, on laisse tel quel.
        return raw
    except Exception:
        return None


def _read_classify_disabled_remote() -> bool:
    """
    Indique si le cache des classifications est désactivé (réglage admin).
    Retourne False si Redis est indisponible ou si le cache est activé.
    """
    if not _enabled():
        logger.debug("[cache] classify_is_disabled: Redis non configuré (URL ou TOKEN manquant)")
        return False
    try:
        resp = requests.post(
            _URL,
            headers={"Authorization": f"Bearer {_TOKEN}"},
            json=["GET", CLASSIFY_CACHE_DISABLED_KEY],
            timeout=5,
        )
        data = resp.json() if resp.content else {}
        raw = data.get("result")
        out = raw == "1"
        logger.debug(
            "[cache] GET %s -> status=%s, result=%r, disabled=%s",
            CLASSIFY_CACHE_DISABLED_KEY,
            resp.status_code,
            raw,
            out,
        )
        if resp.status_code != 200:
            return False
        if "error" in data:
            logger.warning("[cache] GET Redis error: %s", data.get("error"))
            return False
        return out
    except Exception as e:
        logger.exception("[cache] GET %s failed", CLASSIFY_CACHE_DISABLED_KEY)
        return False


def _set_local_classify_disabled(disabled: bool) -> None:
    with _CLASSIFY_STATUS_LOCK:
        _CLASSIFY_STATUS["disabled"] = bool(disabled)
        _CLASSIFY_STATUS["expires_at"] = time.monotonic() + _CLASSIFY_STATUS_TTL_SECONDS
        _CLASSIFY_STATUS["refreshing"] = False
        _CLASSIFY_STATUS["initialized"] = True


def _refresh_classify_disabled_background() -> None:
    disabled = _read_classify_disabled_remote()
    _set_local_classify_disabled(disabled)


def cache_classify_is_disabled(*, force_refresh: bool = False) -> bool:
    """Return cache status without blocking classification requests on Redis I/O."""
    if not _enabled():
        return False
    if force_refresh:
        disabled = _read_classify_disabled_remote()
        _set_local_classify_disabled(disabled)
        return disabled

    now = time.monotonic()
    start_refresh = False
    with _CLASSIFY_STATUS_LOCK:
        disabled = bool(_CLASSIFY_STATUS["disabled"])
        if bool(_CLASSIFY_STATUS["initialized"]) and now < float(_CLASSIFY_STATUS["expires_at"]):
            return disabled
        if not bool(_CLASSIFY_STATUS["refreshing"]):
            _CLASSIFY_STATUS["refreshing"] = True
            start_refresh = True

    if start_refresh:
        threading.Thread(
            target=_refresh_classify_disabled_background,
            name="mosam-cache-status-refresh",
            daemon=True,
        ).start()
    logger.debug("[cache] classify status stale; using local disabled=%s", disabled)
    return disabled


def cache_classify_set_disabled(disabled: bool) -> bool:
    """
    Active ou désactive le cache des classifications (réglage admin).
    Retourne True si l'écriture Redis a réussi, False sinon.
    """
    if not _enabled():
        logger.debug("[cache] classify_set_disabled: Redis non configuré")
        return False
    value = "1" if disabled else "0"
    try:
        resp = requests.post(
            _URL,
            headers={"Authorization": f"Bearer {_TOKEN}"},
            json=["SET", CLASSIFY_CACHE_DISABLED_KEY, value],
            timeout=5,
        )
        data = resp.json() if resp.content else {}
        result = data.get("result")
        ok = result == "OK"
        logger.debug(
            "[cache] SET %s=%s -> status=%s, result=%r, ok=%s",
            CLASSIFY_CACHE_DISABLED_KEY,
            value,
            resp.status_code,
            result,
            ok,
        )
        if resp.status_code != 200:
            logger.warning("[cache] SET failed: status=%s, body=%s", resp.status_code, data)
            return False
        if "error" in data:
            logger.warning("[cache] SET Redis error: %s", data.get("error"))
            return False
        if ok:
            _set_local_classify_disabled(disabled)
        return ok
    except Exception as e:
        logger.exception("[cache] SET %s=%s failed", CLASSIFY_CACHE_DISABLED_KEY, value)
        return False


def cache_clear_classify() -> int:
    """
    Supprime toutes les clés de cache des classifications (préfixe classify:*).
    Utilise SCAN pour lister les clés puis DEL par lots.
    Retourne le nombre de clés supprimées (0 si cache désactivé ou erreur).
    """
    if not _enabled():
        return 0

    all_keys: list[str] = []
    cursor = 0

    while True:
        try:
            resp = requests.post(
                _URL,
                headers={"Authorization": f"Bearer {_TOKEN}"},
                json=["SCAN", str(cursor), "MATCH", "classify:*", "COUNT", 500],
                timeout=10,
            )
        except Exception:
            break
        if resp.status_code != 200:
            break
        try:
            data = resp.json()
        except Exception:
            break
        if "error" in data:
            break
        result = data.get("result")
        if not result or not isinstance(result, list) or len(result) < 2:
            break
        next_cursor = result[0]
        keys = result[1] if isinstance(result[1], list) else []
        all_keys.extend(k for k in keys if isinstance(k, str))
        try:
            cursor = int(next_cursor) if isinstance(next_cursor, str) else int(next_cursor)
        except (TypeError, ValueError):
            cursor = 0
        if cursor == 0:
            break

    if not all_keys:
        return 0

    deleted = 0
    batch_size = 50
    for i in range(0, len(all_keys), batch_size):
        batch = all_keys[i : i + batch_size]
        try:
            resp = requests.post(
                _URL,
                headers={"Authorization": f"Bearer {_TOKEN}"},
                json=["DEL"] + batch,
                timeout=10,
            )
        except Exception:
            continue
        if resp.status_code == 200:
            try:
                data = resp.json()
                n = data.get("result")
                if isinstance(n, int):
                    deleted += n
                else:
                    deleted += len(batch)
            except Exception:
                deleted += len(batch)
    return deleted

