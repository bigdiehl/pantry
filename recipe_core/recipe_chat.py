"""
DESCRIPTION: Recipe chat. Sends the conversation plus a compact catalog of the
user's saved recipes to Gemini and gets back a structured reply: chat text,
which saved recipes it recommends, and whether to offer or run a web recipe search
(see recipe_search.py).
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CHAT_MODEL = "gemini-2.5-flash"
MAX_TURNS = 20          # most recent messages sent to the model
MAX_MESSAGE_CHARS = 4000

SYSTEM_PROMPT = """You are the kitchen assistant for a family's personal recipe app.
Help them decide what to cook: what fits what is in the fridge, what they are in
the mood for, what is quick, what they have not had in a while.

Their saved recipes are listed below, one per line:
slug | name | category, meal | last made | on shopping list | ingredients

Rules:
- Start with their saved recipes. Recommend one by putting its exact slug in `recipes`
  with a short reason. Only use slugs from the catalog; never invent saved recipes.
- When they ask for ideas or what to make, recommend 2-4 fitting saved recipes. Then,
  unless they already asked for new recipes, set `offer_search` to true, put the search
  query you would use in `offer_query`, and end `reply` with a short offer to look for
  new recipes online. If nothing saved fits, say so and
  offer the search.
- Set `web_search` to a concise search query (e.g. "lemon herb chicken thighs with
  asparagus") when they want new recipes from the web: they accept your offer ("yes",
  "sure"), say "look for more", ask for "recipes like X", or ask for something new. Base
  the query on the conversation. Keep `reply` to one short line in that case (the app
  shows the web results as cards) and leave `recipes` empty unless asked for both.
- `reply` is conversational markdown, short and practical. Refer to recipes by name,
  never by slug. Do not list the recommendations in prose; the app shows them as cards.
- When they list ingredients on hand, point out which saved recipes use them and
  what they would still need to buy.
- Ask a brief follow-up question only if the request is too vague to answer.

Catalog:
{catalog}
"""


class RecipePick(BaseModel):
    slug: str
    reason: str = Field(description="One short sentence on why this fits.")


class ChatReply(BaseModel):
    reply: str
    recipes: List[RecipePick] = []
    offer_search: bool = Field(False, description="Offer to look for new recipes online.")
    offer_query: Optional[str] = Field(None, description="Search query to use if the user accepts the offer.")
    web_search: Optional[str] = Field(None, description="Search query when the user wants new recipes from the web.")


def build_catalog(recipes: List[dict]) -> str:
    """
    One line per recipe. Each dict: slug, name, category, meal, ingredients (list of str),
    last_used (str or None), selected (bool).
    """
    lines = []
    for r in sorted(recipes, key=lambda r: r["name"]):
        lines.append(" | ".join([
            r["slug"],
            r["name"],
            f"{(r.get('category') or '?').lower()}, {(r.get('meal') or '?').lower()}",
            f"last made {r['last_used']}" if r.get("last_used") else "never made",
            "on list" if r.get("selected") else "not on list",
            ", ".join(r.get("ingredients") or []),
        ]))
    return "\n".join(lines) or "(no saved recipes yet)"


def _to_contents(messages: List[dict]) -> List[types.Content]:
    contents = []
    for m in messages[-MAX_TURNS:]:
        text = str(m.get("text", "")).strip()[:MAX_MESSAGE_CHARS]
        if not text:
            continue
        role = "model" if m.get("role") == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    if not contents or contents[-1].role != "user":
        raise ValueError("Conversation must end with a user message")
    return contents


def make_client(api_key: Optional[str] = None):
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    return genai.Client(api_key=api_key)


def chat(messages: List[dict], catalog: str, api_key: Optional[str] = None, client=None) -> ChatReply:
    """Run one chat turn. `messages` is [{role: 'user'|'assistant', text}, ...]."""
    contents = _to_contents(messages)
    client = client or make_client(api_key)

    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT.format(catalog=catalog),
            response_mime_type="application/json",
            response_schema=ChatReply,
            temperature=0.7,
        ),
    )

    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, ChatReply):
        return parsed
    return ChatReply.model_validate(json.loads(response.text))
