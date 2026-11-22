"""
DESCRIPTION: Food registry — loads from foods.yaml, supports fuzzy matching,
and never hard-fails on an unrecognised ingredient name.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import List, Optional, Tuple

import yaml
from rapidfuzz import fuzz, process
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from recipe_core.recipe_lib import Food, FoodType

logger = logging.getLogger(__name__)

_FOODS_YAML = os.path.join(os.path.dirname(__file__), "foods.yaml")

# Similarity threshold for fuzzy matching (0–100).
# Raise to require a closer match; lower to be more permissive.
FUZZY_THRESHOLD = 85


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

def _load_registry(path: str = _FOODS_YAML) -> List[Food]:
    """Load and validate the food registry from YAML."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    return [Food(**entry) for entry in raw]


@lru_cache(maxsize=1)
def _get_registry() -> List[Food]:
    """Return the registry, cached after the first load."""
    return _load_registry()


def _build_alias_index() -> List[Tuple[str, Food]]:
    """Flat list of (alias, Food) pairs — used for fuzzy search."""
    return [(alias, food) for food in _get_registry() for alias in food.names]


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def get_food(name: str) -> Food:
    """
    Return the Food matching *name* from the registry.

    Resolution order:
      1. Exact match (case-insensitive) against all aliases.
      2. Fuzzy match — if the best candidate scores >= FUZZY_THRESHOLD.
      3. Soft fallback — return a default Food(Other) and log a warning.

    Never raises; the shopping list pipeline always gets a usable Food back.
    """
    normalised = name.lower().strip()
    registry = _get_registry()

    # 1. Exact match
    for food in registry:
        if food.has_name(normalised):
            return food

    # 2. Fuzzy match
    alias_index = _build_alias_index()
    candidates = [alias for alias, _ in alias_index]

    result = process.extractOne(
        normalised,
        candidates,
        scorer=fuzz.token_sort_ratio,
    )

    if result is not None:
        matched_alias, score, idx = result
        if score >= FUZZY_THRESHOLD:
            matched_food = alias_index[idx][1]
            logger.info(
                "Fuzzy matched '%s' → '%s' (score=%d)",
                name,
                matched_food.get_name(),
                score,
            )
            return matched_food

    # 3. Soft fallback
    return Food.default(name)


def reload_registry():
    """Force a reload of the food registry (e.g. after editing foods.yaml)."""
    _get_registry.cache_clear()


def list_foods() -> List[Food]:
    """Return all foods in the registry (for display/editing)."""
    return list(_get_registry())


# ---------------------------------------------------------------------------
# Editing — round-trips foods.yaml via ruamel so comments/formatting in the
# file survive edits made through the Edit Ingredients page.
# ---------------------------------------------------------------------------

_yaml_rt = YAML()
_yaml_rt.preserve_quotes = True
_yaml_rt.width = 4096  # don't wrap long `names: [...]` lines


def _load_raw() -> CommentedSeq:
    with open(_FOODS_YAML) as f:
        return _yaml_rt.load(f)


def _save_raw(data: CommentedSeq) -> None:
    with open(_FOODS_YAML, "w") as f:
        _yaml_rt.dump(data, f)
    reload_registry()


def _find_index(data: CommentedSeq, primary_name: str) -> int:
    """Index of the entry whose first name matches `primary_name` (case-insensitive), or -1."""
    normalised = primary_name.lower().strip()
    for i, entry in enumerate(data):
        names = entry.get("names")
        first = names[0] if isinstance(names, list) else names
        if str(first).lower().strip() == normalised:
            return i
    return -1


def _flow_list(items: List[str]) -> CommentedSeq:
    """A CommentedSeq that renders as `[a, b]` instead of a multi-line block list."""
    seq = CommentedSeq(items)
    seq.fa.set_flow_style()
    return seq


def _apply_optional_fields(entry: dict, food: Food) -> None:
    """Set/clear the optional fields on `entry` to match `food`."""
    for key in ("preferred_unit", "min_amount", "likely_to_have", "preferred_vendor"):
        value = getattr(food, key)
        if value:
            entry[key] = value
        elif key in entry:
            del entry[key]


def create_food(data: dict) -> Food:
    """Validate `data` and append it as a new entry in foods.yaml."""
    food = Food(**data)
    raw = _load_raw()
    if _find_index(raw, food.get_name()) != -1:
        raise ValueError(f"A food named '{food.get_name()}' already exists.")

    entry = {"names": _flow_list(food.names), "category": food.category.value}
    _apply_optional_fields(entry, food)
    raw.append(entry)
    _save_raw(raw)
    return food


def update_food(original_name: str, data: dict) -> Food:
    """Validate `data` and overwrite the food previously known as `original_name`."""
    food = Food(**data)
    raw = _load_raw()
    idx = _find_index(raw, original_name)
    if idx == -1:
        raise KeyError(f"No food named '{original_name}' found.")

    # Renaming is fine, but not onto a *different* existing entry's name.
    collision_idx = _find_index(raw, food.get_name())
    if collision_idx != -1 and collision_idx != idx:
        raise ValueError(f"A food named '{food.get_name()}' already exists.")

    entry = raw[idx]
    entry["names"] = _flow_list(food.names)
    entry["category"] = food.category.value
    _apply_optional_fields(entry, food)
    _save_raw(raw)
    return food


def delete_food(name: str) -> None:
    """Remove the food entry named `name` from foods.yaml."""
    raw = _load_raw()
    idx = _find_index(raw, name)
    if idx == -1:
        raise KeyError(f"No food named '{name}' found.")
    del raw[idx]
    _save_raw(raw)
