"""LLM client for CertForge live mode.

A thin, provider-agnostic wrapper. By default it talks to **GitHub Models**
(free, OpenAI-compatible), but the same code works against Azure OpenAI by
flipping LLM_PROVIDER — both speak the OpenAI chat-completions API.

The single entry point agents use is `chat_json(system, user)`: it sends a
system + user message, forces JSON output, and returns a parsed dict. All the
provider/auth/parsing details live here so agents stay clean.
"""
from __future__ import annotations

import json
from functools import lru_cache

from . import config


class LLMError(RuntimeError):
    """Raised when the LLM call or JSON parse fails — callers fall back to mock."""


@lru_cache(maxsize=1)
def _client():
    """Build the OpenAI-compatible client once (cached)."""
    from openai import OpenAI

    if config.LLM_PROVIDER == "github":
        if not config.GITHUB_TOKEN:
            raise LLMError("GITHUB_TOKEN not set in certforge/.env")
        return OpenAI(base_url=config.GITHUB_MODELS_ENDPOINT, api_key=config.GITHUB_TOKEN)

    if config.LLM_PROVIDER == "azure":
        # Microsoft Foundry: unified project client -> OpenAI-compatible client
        # against the single project endpoint (the official Foundry pattern).
        # Uses Instant Models (call by name, no deployment needed) when available.
        from azure.ai.projects import AIProjectClient
        from azure.identity import (AzureCliCredential, ChainedTokenCredential,
                                    DefaultAzureCredential)

        if not config.PROJECT_ENDPOINT:
            raise LLMError("PROJECT_ENDPOINT not set in certforge/.env")
        # Prefer az-login creds locally; managed identity in a hosted container.
        credential = ChainedTokenCredential(AzureCliCredential(), DefaultAzureCredential())
        project = AIProjectClient(endpoint=config.PROJECT_ENDPOINT, credential=credential)
        return project.get_openai_client()

    raise LLMError(f"Unknown LLM_PROVIDER: {config.LLM_PROVIDER}")


# Some Foundry-hosted reasoning models (e.g. gpt-oss) sometimes wrap their JSON
# answer in a single envelope key. We unwrap these transparently.
_WRAPPER_KEYS = {"final", "response", "result", "output", "answer", "json"}


def _unwrap(obj):
    """If the model wrapped the real JSON in {'final': '<json string>'}, unwrap it."""
    if isinstance(obj, dict) and len(obj) == 1:
        (key, val), = obj.items()
        if key.lower() in _WRAPPER_KEYS:
            if isinstance(val, str):
                try:
                    return _unwrap(json.loads(val))
                except json.JSONDecodeError:
                    return obj
            if isinstance(val, dict):
                return _unwrap(val)
    return obj


def chat_json(system: str, user: str, *, temperature: float = 0.3,
              max_tokens: int = 2500) -> dict:
    """Send system+user messages, force JSON output, return a parsed dict.

    Robust to reasoning models that wrap output in an envelope key. Raises
    LLMError on any failure so the agent can fall back to mock logic.
    """
    try:
        resp = _client().chat.completions.create(
            model=config.chat_model(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or "{}"
        return _unwrap(json.loads(content))
    except json.JSONDecodeError as e:
        raise LLMError(f"Model returned non-JSON: {e}") from e
    except Exception as e:  # network, auth, rate-limit, etc.
        raise LLMError(str(e)) from e


@lru_cache(maxsize=1)
def _embed_client():
    """Embeddings client. Foundry serves embeddings on the classic Azure OpenAI
    route (resource endpoint + api-version), not the unified project route, so we
    build a dedicated client for it. GitHub uses the same client as chat."""
    if config.LLM_PROVIDER == "azure":
        from azure.identity import (AzureCliCredential, ChainedTokenCredential,
                                    DefaultAzureCredential, get_bearer_token_provider)
        from openai import AzureOpenAI

        cred = ChainedTokenCredential(AzureCliCredential(), DefaultAzureCredential())
        token_provider = get_bearer_token_provider(
            cred, "https://cognitiveservices.azure.com/.default")
        base = config.PROJECT_ENDPOINT.split("/api/")[0]
        return AzureOpenAI(azure_endpoint=base, azure_ad_token_provider=token_provider,
                           api_version="2024-10-21")
    return _client()


def embed(texts: list[str]) -> list[list[float]]:
    """Return embedding vectors for a list of texts. Raises LLMError on failure."""
    try:
        resp = _embed_client().embeddings.create(model=config.embed_model(), input=texts)
        return [d.embedding for d in resp.data]
    except Exception as e:
        raise LLMError(str(e)) from e


def is_configured() -> bool:
    """True if the chosen provider has the credentials it needs."""
    if config.LLM_PROVIDER == "github":
        return bool(config.GITHUB_TOKEN)
    if config.LLM_PROVIDER == "azure":
        return bool(config.PROJECT_ENDPOINT)
    return False


def smoke_test() -> str:
    """Tiny end-to-end check used by scripts to confirm the token works."""
    out = chat_json(
        "You are a test. Reply with JSON only.",
        'Return exactly {"ok": true, "model": "<the model you are>"}.',
        max_tokens=50,
    )
    return json.dumps(out)
