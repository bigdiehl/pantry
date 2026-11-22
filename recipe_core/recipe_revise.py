"""
DESCRIPTION: AI recipe revision. Takes the recipe form state (the same shape the editor
and import review use) plus an instruction ("make it dairy free", "double it") and returns
the revised form state with a short note on what changed. Stateless: the client sends
the current draft each time.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from google.genai import types
from pydantic import BaseModel, Field

from recipe_core.recipe_chat import make_client

logger = logging.getLogger(__name__)

REVISE_MODEL = "gemini-2.5-flash"
MAX_HISTORY = 10

SYSTEM_PROMPT = """You edit recipes for a family's recipe app. You get the current recipe
as JSON and an instruction. Return the full revised recipe in the same structure plus a
one or two sentence `note` saying what you changed.

Fields:
- name, servings (int), category (ENTREE|SALAD|DESSERT|SIDE), meal (BREAKFAST|LUNCH|DINNER)
- ingredients: shopping list entries. `food` is a simple grocery name ("chicken breast",
  "yellow onion"); `quantity` is a number plus optional unit ("2 lbs", "1/2 cup", "3"), or
  "" if unspecified. No prep words ("chopped") here.
- ingredients_md: the human-readable ingredient list as markdown bullets ("- 1 cup chopped
  onion"). May use "### Sauce"-style subheadings.
- instructions_md: numbered markdown steps, optional "### Subheading" sections, and an
  optional "### Notes" section. Do not include the title, servings line, or images.

Rules:
- Change only what the instruction asks for, plus whatever must change to stay consistent
  (e.g. scaling servings scales both ingredient lists; swapping an ingredient updates the
  steps that mention it).
- Keep the shopping list ingredients and ingredients_md in agreement.
- If the instruction is a question rather than a change, answer it in `note` and return
  the recipe unchanged.
"""


class DraftIngredient(BaseModel):
    food: str
    quantity: str = ""


class RecipeDraft(BaseModel):
    name: str
    servings: int
    category: str
    meal: str
    ingredients: List[DraftIngredient]
    ingredients_md: str
    instructions_md: str


class Revision(BaseModel):
    recipe: RecipeDraft
    note: str = Field(description="One or two sentences on what changed, or an answer to a question.")


EDITABLE = ("name", "servings", "category", "meal", "ingredients", "ingredients_md", "instructions_md")


def revise_recipe(draft: dict, instruction: str, history: Optional[List[dict]] = None,
                  api_key: Optional[str] = None, client=None) -> dict:
    """Returns {"draft": revised form state, "note": str}. Fields the model doesn't edit
    (enabled, min_period_weeks, image_url, source) are carried over unchanged."""
    current = {k: draft.get(k) for k in EDITABLE}
    current["ingredients"] = [{"food": i.get("food", ""), "quantity": i.get("quantity", "")}
                              for i in (draft.get("ingredients") or [])]

    contents = []
    for turn in (history or [])[-MAX_HISTORY:]:
        if turn.get("instruction"):
            contents.append(types.Content(role="user", parts=[types.Part(text=str(turn["instruction"])[:1000])]))
        if turn.get("note"):
            contents.append(types.Content(role="model", parts=[types.Part(text=str(turn["note"])[:1000])]))
    contents.append(types.Content(role="user", parts=[types.Part(text=(
        f"Current recipe:\n{json.dumps(current, ensure_ascii=False)}\n\nInstruction: {instruction[:2000]}"))]))

    client = client or make_client(api_key)
    response = client.models.generate_content(
        model=REVISE_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=Revision,
            temperature=0.3,
        ),
    )
    parsed = getattr(response, "parsed", None)
    revision = parsed if isinstance(parsed, Revision) else Revision.model_validate(json.loads(response.text))

    revised = {**draft, **revision.recipe.model_dump()}
    revised["category"] = revised["category"].upper()
    revised["meal"] = revised["meal"].upper()
    return {"draft": revised, "note": revision.note}
