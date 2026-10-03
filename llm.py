"""
llm.py – thin wrapper around local open-weight models for BidMitra.

Supported providers (set via env LLM_PROVIDER, default "ollama"):
  - "ollama"           : local Ollama HTTP API  (docs.ollama.com)
  - "openai_compatible": any hosted open-weight endpoint using the OpenAI-
                         compatible /chat/completions route

Only plain `requests` is used. No proprietary SDK.
Model name comes ONLY from the environment (OPEN_LLM_MODEL).
The model's ONLY job is converting a typed sentence to a JSON filter.
It never sees bid data or the profile.

# TODO(verify against Ollama docs): The request/response format below is based
# on Ollama's documented /api/chat endpoint. If the Ollama API changes, update
# _call_ollama() accordingly. Reference: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations
import json
import os
import requests


def _provider() -> str:
    return os.environ.get("LLM_PROVIDER", "ollama").lower().strip()


def _ollama_base() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _openai_base() -> str:
    return os.environ.get("OPEN_LLM_BASE_URL", "http://localhost:8000").rstrip("/")


def _model_name() -> str:
    """Model name from env only. Never hardcoded."""
    return os.environ.get("OPEN_LLM_MODEL", "")


def model_display_name() -> str:
    """Human-readable model name for UI badge."""
    m = _model_name()
    return m if m else "(not configured)"


def license_url() -> str | None:
    """Optional license URL shown in the UI."""
    return os.environ.get("OPEN_LLM_LICENSE_URL") or None


def endpoint_host() -> str:
    """Hostname shown in the AI engine badge."""
    p = _provider()
    if p == "ollama":
        return _ollama_base()
    return _openai_base()


def check_reachable(timeout: float = 3.0) -> tuple[bool, str]:
    """
    Test whether the model is configured AND reachable right now.
    Returns (is_ok, status_label) for the AI engine badge.

    Status labels:
      "not configured"        – OPEN_LLM_MODEL env var is empty
      "not pulled"            – Ollama running but model not downloaded yet
      "unreachable"           – endpoint not responding
      "running locally"       – Ollama OK + model present
      "reachable"             – openai_compatible endpoint responded
    """
    if not _model_name():
        return False, "not configured"
    try:
        p = _provider()
        if p == "ollama":
            url = f"{_ollama_base()}/api/tags"
            resp = requests.get(url, timeout=timeout)
            if resp.status_code != 200:
                return False, "unreachable"
            tags = resp.json().get("models", [])
            model = _model_name().lower()
            # Match by base name (e.g. "phi3" matches "phi3:mini")
            model_base = model.split(":")[0]
            present = any(
                str(t.get("name", "")).lower().startswith(model_base)
                for t in tags
            )
            if present:
                return True, "running locally"
            return False, f"not pulled (run: ollama pull {_model_name()})"
        else:
            base = _openai_base()
            resp = requests.get(base, timeout=timeout)
            if resp.status_code < 500:
                return True, "reachable"
            return False, "unreachable"
    except requests.exceptions.ConnectionError:
        return False, "unreachable"
    except requests.exceptions.Timeout:
        return False, "unreachable"
    except Exception:
        return False, "unreachable"


def warm_up() -> bool:
    """Legacy compat shim. Returns True if reachable."""
    ok, _ = check_reachable()
    return ok


def _call_ollama(prompt: str, system: str, timeout: int) -> str:
    """
    Call Ollama's /api/chat endpoint.
    # TODO(verify against Ollama docs): format parameter may vary by Ollama version.
    """
    url = f"{_ollama_base()}/api/chat"
    model = _model_name()
    if not model:
        raise ValueError("OPEN_LLM_MODEL env var is not set.")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": "json",   # request JSON output; validate in code regardless
        # TODO(verify against Ollama docs): "format":"json" is documented in
        # Ollama's structured output guide. Some older versions may ignore it.
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    # TODO(verify against Ollama docs): response shape is {"message": {"content": "..."}}
    return data["message"]["content"]


def _call_openai_compatible(prompt: str, system: str, timeout: int) -> str:
    """Call an OpenAI-compatible /chat/completions endpoint."""
    url = f"{_openai_base()}/v1/chat/completions"
    model = _model_name()
    if not model:
        raise ValueError("OPEN_LLM_MODEL env var is not set.")

    api_key = os.environ.get("OPEN_LLM_API_KEY", "sk-placeholder")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},  # request JSON; validate in code
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_model(prompt: str, system: str = "", timeout: int = 60) -> str:
    """Dispatch to the configured provider."""
    p = _provider()
    if p == "ollama":
        return _call_ollama(prompt, system, timeout)
    elif p == "openai_compatible":
        return _call_openai_compatible(prompt, system, timeout)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {p!r}")


# ---- Public API ----

def query(sentence: str, system_prompt: str, timeout: int = 60) -> str:
    """
    Send `sentence` + `system_prompt` to the model.
    Returns the raw text response.
    Raises on network error or timeout.
    """
    return _call_model(sentence, system=system_prompt, timeout=timeout)
