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
        # Azure OpenAI via the Foundry project (keyless auth via az login).
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AzureOpenAI

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
        return AzureOpenAI(
            azure_endpoint=config.PROJECT_ENDPOINT,
            azure_ad_token_provider=token_provider,
            api_version="2024-10-21",
        )

    raise LLMError(f"Unknown LLM_PROVIDER: {config.LLM_PROVIDER}")


def chat_json(system: str, user: str, *, temperature: float = 0.3,
              max_tokens: int = 1200) -> dict:
    """Send system+user messages, force JSON output, return a parsed dict.

    Raises LLMError on any failure so the agent can fall back to mock logic.
    """
    try:
        resp = _client().chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model returned non-JSON: {e}") from e
    except Exception as e:  # network, auth, rate-limit, etc.
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
