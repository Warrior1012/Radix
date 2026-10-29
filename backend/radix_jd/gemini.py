"""Shared LLM client for Role 1 (JD) and Role 2 (resume).

* One place for retries, timeouts, HTTP/provider error mapping and strict JSON parsing.
* Failures raise ``LLMError`` with a machine-readable ``kind`` so callers/users see the REAL cause
  (auth, rate limit, timeout, bad JSON, ...) instead of a generic "did not succeed".
* API keys are only ever sent to the provider. They are never logged and never put in an error message
  (the Gemini key travels as a query param, so we never echo request URLs).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import httpx


class LLMError(RuntimeError):
    """Typed model failure. ``kind`` is one of: auth, model_not_found, rate_limited, timeout, network,
    http_error, empty_response, blocked, bad_json, bad_structure."""

    def __init__(self, kind: str, message: str, *, model: str = "", provider: str = ""):
        super().__init__(message)
        self.kind, self.model, self.provider = kind, model, provider

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "message": str(self), "model": self.model, "provider": self.provider}


def strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    return re.sub(r"\s*```$", "", text).strip()


def _classify_http(status: int) -> str:
    if status in (401, 403):
        return "auth"
    if status == 404:
        return "model_not_found"
    if status == 429:
        return "rate_limited"
    return "http_error"


def provider_error(response: httpx.Response) -> str:
    detail = re.sub(r"\s+", " ", response.text or "").strip()
    return f"HTTP {response.status_code}" + (f": {detail[:220]}" if detail else "")


async def post_with_retry(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
    """Retry transient errors (429/5xx/timeouts); never retry permanent auth/model errors."""
    for attempt in range(3):
        try:
            response = await client.post(url, **kwargs)
        except httpx.TimeoutException as exc:
            if attempt == 2:
                raise LLMError("timeout", f"Model request timed out after retries ({type(exc).__name__}).") from exc
            await asyncio.sleep(0.7 * (attempt + 1))
            continue
        except httpx.NetworkError as exc:
            if attempt == 2:
                raise LLMError("network", f"Network error reaching the model provider ({type(exc).__name__}).") from exc
            await asyncio.sleep(0.7 * (attempt + 1))
            continue
        if response.status_code not in (429, 500, 502, 503, 504) or attempt == 2:
            return response
        try:
            delay = min(4.0, max(0.5, float(response.headers.get("Retry-After", ""))))
        except ValueError:
            delay = 0.7 * (attempt + 1)
        await asyncio.sleep(delay)
    raise LLMError("http_error", "Provider request failed after retries.")


async def call_json(client: httpx.AsyncClient, target: dict[str, str], *, system: str, user: str,
                    gemini_schema: dict[str, Any] | None = None, max_tokens: int = 5000,
                    app_title: str = "RADIX Talent Match") -> dict[str, Any]:
    """Call one provider/model and return the parsed top-level JSON object. Raises ``LLMError`` only."""
    provider, model = target["provider"], target["model"]

    def err(kind: str, msg: str) -> LLMError:
        return LLMError(kind, msg, model=model, provider=provider)

    try:
        if provider == "gemini":
            gen: dict[str, Any] = {"temperature": 0, "responseMimeType": "application/json", "maxOutputTokens": max_tokens}
            if gemini_schema:
                gen["responseSchema"] = gemini_schema
            response = await post_with_retry(
                client, f"{target['base_url']}/models/{model}:generateContent", params={"key": target["api_key"]},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": gen})
            if response.status_code >= 400:
                raise err(_classify_http(response.status_code), provider_error(response))
            data = response.json()
            try:
                parts = data["candidates"][0]["content"]["parts"]
                content = "\n".join(p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text"))
            except (KeyError, IndexError, TypeError) as exc:
                feedback = data.get("promptFeedback", {}) if isinstance(data, dict) else {}
                raise err("blocked", f"Gemini returned no text candidate; feedback={str(feedback)[:120]}") from exc
        else:
            headers = {"Authorization": f"Bearer {target['api_key']}", "Content-Type": "application/json"}
            if provider == "openrouter":
                headers["HTTP-Referer"] = os.getenv("OPENROUTER_APP_URL", "http://localhost:5173")
                headers["X-Title"] = app_title
            response = await post_with_retry(
                client, f"{target['base_url']}/chat/completions", headers=headers,
                json={"model": model, "temperature": 0.0, "max_tokens": max_tokens,
                      "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            if response.status_code >= 400:
                raise err(_classify_http(response.status_code), provider_error(response))
            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise err("empty_response", "Provider response did not contain choices[0].message.content") from exc
    except LLMError as exc:  # fill in model/provider for errors raised by post_with_retry
        exc.model, exc.provider = exc.model or model, exc.provider or provider
        raise
    except (ValueError, json.JSONDecodeError) as exc:  # response.json() failed
        raise err("bad_json", f"Provider returned a non-JSON HTTP body ({type(exc).__name__}).") from exc

    if not isinstance(content, str) or not content.strip():
        raise err("empty_response", "Provider returned empty text content.")
    try:
        parsed = json.loads(strip_code_fence(content))
    except json.JSONDecodeError as exc:
        raise err("bad_json", f"Model output was not valid JSON ({exc.msg} at char {exc.pos}).") from exc
    if not isinstance(parsed, dict):
        raise err("bad_structure", "Model JSON was not an object.")
    return parsed
