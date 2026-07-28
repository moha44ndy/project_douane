"""Recherche internet via l'outil web_search de l'API OpenAI Responses."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from .config.settings import Config
from .openai_compat import responses_api_kwargs, responses_max_output_tokens
from .telemetry import record_telemetry_call

logger = logging.getLogger(__name__)

_OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def openai_web_search_enabled() -> bool:
    if not Config.OPENAI_API_KEY:
        return False
    return bool(Config.MOSAM_WEB_SEARCH_ENABLED)


def web_search_model() -> str:
    return (
        (Config.MOSAM_WEB_SEARCH_MODEL or "").strip()
        or (Config.MOSAM_MODEL or "").strip()
        or "gpt-5"
    )


def _extract_output_text(data: dict[str, Any]) -> str:
    top_level = str(data.get("output_text") or "").strip()
    if top_level:
        return top_level
    parts: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                if content.get("type") in {"output_text", "text"}:
                    text = str(content.get("text") or "").strip()
                    if text:
                        parts.append(text)
        elif item.get("type") == "text":
            text = str(item.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def extract_web_search_queries(data: dict[str, Any]) -> list[str]:
    """Requetes effectivement lancees par l'outil web_search."""
    queries: list[str] = []
    seen: set[str] = set()
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "web_search_call":
            continue
        action = item.get("action")
        if not isinstance(action, dict):
            continue
        candidates: list[str] = []
        query = str(action.get("query") or "").strip()
        if query:
            candidates.append(query)
        raw_queries = action.get("queries")
        if isinstance(raw_queries, list):
            candidates.extend(str(q).strip() for q in raw_queries if str(q).strip())
        for candidate in candidates:
            key = candidate.casefold()
            if key not in seen:
                seen.add(key)
                queries.append(candidate)
    return queries[:5]


def extract_url_citations(data: dict[str, Any]) -> list[dict[str, str]]:
    """Extrait les URLs citees par le modele apres une recherche web."""
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            for ann in content.get("annotations") or []:
                if not isinstance(ann, dict) or ann.get("type") != "url_citation":
                    continue
                url = str(ann.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                sources.append(
                    {
                        "title": str(ann.get("title") or url).strip(),
                        "url": url,
                        "snippet": "",
                    }
                )
    return sources[:10]


def _call_responses_api(payload: dict[str, Any]) -> dict[str, Any]:
    """Appelle l'API Responses (SDK si disponible, sinon HTTP)."""
    from openai import OpenAI

    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    if hasattr(client, "responses"):
        response = client.responses.create(**payload)
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if isinstance(response, dict):
            return response
        return dict(response)

    headers = {
        "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    timeout = max(30, int(Config.MOSAM_WEB_SEARCH_TIMEOUT_SECONDS or 90))
    http_response = requests.post(
        _OPENAI_RESPONSES_URL,
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    if not http_response.ok:
        detail = http_response.text[:500]
        raise RuntimeError(
            f"OpenAI Responses API HTTP {http_response.status_code}: {detail}"
        )
    data = http_response.json()
    if not isinstance(data, dict):
        raise RuntimeError("OpenAI Responses API: reponse JSON inattendue")
    return data


def identify_with_openai_web_search(
    *,
    instructions: str,
    user_input: str,
) -> tuple[str, list[dict[str, str]], list[str]]:
    """
    Lance une identification marchandise avec recherche web OpenAI.
    Retourne (texte brut du modele, sources URL, requetes web).
    """
    model = web_search_model()
    base_payload: dict[str, Any] = {
        "model": model,
        "instructions": instructions,
        "input": user_input,
        "tools": [{"type": "web_search"}],
        "max_output_tokens": responses_max_output_tokens(model, 1400),
        "store": False,
        **responses_api_kwargs(model, temperature=0.2),
    }

    context_sizes = [
        Config.MOSAM_WEB_SEARCH_CONTEXT_SIZE or "medium",
        "low",
    ]
    last_error: Exception | None = None

    for attempt, context_size in enumerate(context_sizes, start=1):
        payload = dict(base_payload)
        payload["tools"] = [
            {
                "type": "web_search",
                "search_context_size": context_size,
            }
        ]
        started = time.perf_counter()
        try:
            data = _call_responses_api(payload)
            record_telemetry_call(
                "web_search",
                model=model,
                duration_ms=(time.perf_counter() - started) * 1000.0,
                prompt_chars=len(user_input or "") + len(instructions or ""),
                success=True,
            )
            text = _extract_output_text(data)
            sources = extract_url_citations(data)
            queries = extract_web_search_queries(data)
            if not text:
                raise RuntimeError("OpenAI Responses API: reponse vide")
            return text, sources, queries
        except Exception as exc:
            record_telemetry_call(
                "web_search",
                model=model,
                duration_ms=(time.perf_counter() - started) * 1000.0,
                prompt_chars=len(user_input or "") + len(instructions or ""),
                success=False,
            )
            last_error = exc
            retryable = attempt < len(context_sizes) and (
                "timeout" in str(exc).lower()
                or "timed out" in str(exc).lower()
                or "connection" in str(exc).lower()
            )
            if retryable:
                logger.warning(
                    "[openai_web_search] tentative %d echouee (%s), retry context=%s",
                    attempt,
                    exc,
                    context_sizes[attempt],
                )
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError("OpenAI Responses API: echec recherche web")
