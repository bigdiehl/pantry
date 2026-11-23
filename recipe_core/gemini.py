"""
DESCRIPTION: One place for Gemini model choice. Every feature calls generate(), which
tries the primary model and falls back to lighter models when the primary is over quota
(429) or overloaded (503). Each model has its own free-tier quota, so a fallback keeps
chat and import working after the primary's daily limit is used up.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from google.genai import errors

logger = logging.getLogger(__name__)

PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODELS: List[str] = [m for m in os.environ.get(
    "GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite").split(",") if m.strip()]
RETRYABLE = (429, 503)


def generate(client, *, contents, config=None, model: Optional[str] = None):
    """client.models.generate_content with fallback. Raises the last error if all fail."""
    models = [model or PRIMARY_MODEL] + [m.strip() for m in FALLBACK_MODELS if m.strip() != (model or PRIMARY_MODEL)]
    last = None
    for name in models:
        try:
            return client.models.generate_content(model=name, contents=contents, config=config)
        except errors.APIError as e:
            if getattr(e, "code", None) not in RETRYABLE:
                raise
            logger.warning("Gemini %s unavailable (%s); trying next model", name, e.code)
            last = e
    raise last


def friendly_error(e: Exception) -> str:
    """Short user-facing explanation for a failed Gemini call."""
    code = getattr(e, "code", None)
    if code == 429:
        return ("The AI's daily free limit is used up (it resets around midnight Pacific). "
                "Turning on billing for the Gemini API key removes the limit.")
    if code == 503:
        return "The AI service is busy right now. Try again in a minute."
    return f"The assistant is unavailable right now ({type(e).__name__})."
