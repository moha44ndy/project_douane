"""Compatibilite des parametres OpenAI selon le modele (GPT-5, o-series, etc.)."""

from __future__ import annotations


def _model_key(model: str) -> str:
    return (model or "").strip().lower()


def uses_max_completion_tokens(model: str) -> bool:
    """GPT-5 et modeles reasoning n'acceptent pas max_tokens."""
    key = _model_key(model)
    return key.startswith("gpt-5") or key.startswith("o1") or key.startswith("o3") or key.startswith("o4")


def supports_temperature(model: str) -> bool:
    key = _model_key(model)
    return not (
        key.startswith("gpt-5")
        or key.startswith("o1")
        or key.startswith("o3")
        or key.startswith("o4")
    )


def scaled_max_tokens(model: str, base: int) -> int:
    """GPT-5 consomme des tokens de raisonnement internes : augmenter la limite."""
    if uses_max_completion_tokens(model):
        return max(base * 4, 8192)
    return base


def chat_completion_kwargs(
    model: str,
    *,
    max_tokens: int,
    temperature: float = 0.2,
) -> dict:
    """Parametres token/temperature adaptes au modele."""
    limit = scaled_max_tokens(model, max_tokens)
    kwargs: dict = {}
    if uses_max_completion_tokens(model):
        kwargs["max_completion_tokens"] = limit
    else:
        kwargs["max_tokens"] = limit
        kwargs["temperature"] = temperature
    return kwargs


def responses_max_output_tokens(model: str, base: int = 1400) -> int:
    return scaled_max_tokens(model, base)


def responses_api_kwargs(model: str, *, temperature: float = 0.2) -> dict:
    """Parametres optionnels pour l'API Responses (web search)."""
    if supports_temperature(model):
        return {"temperature": temperature}
    return {}
