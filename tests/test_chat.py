import json
from types import SimpleNamespace

import pytest

from recipe_core import recipe_chat
from recipe_core.recipe_chat import ChatReply, RecipeIdea, RecipePick, build_catalog


class FakeModels:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed=None, text=json.dumps(self.reply))


def fake_client(reply):
    return SimpleNamespace(models=FakeModels(reply))


def test_build_catalog_line_format():
    line = build_catalog([{
        "slug": "clam_chowder", "name": "Clam Chowder", "category": "ENTREE", "meal": "DINNER",
        "ingredients": ["clams", "potato"], "last_used": "2026-09-13", "selected": True,
    }])
    assert line == "clam_chowder | Clam Chowder | entree, dinner | last made 2026-09-13 | on list | clams, potato"


def test_chat_maps_roles_and_parses_json():
    client = fake_client({"reply": "Try the soup.", "recipes": [{"slug": "soup", "reason": "warm"}], "ideas": []})
    out = recipe_chat.chat(
        [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "hello"}, {"role": "user", "text": "dinner?"}],
        "catalog", client=client,
    )
    assert out.reply == "Try the soup."
    assert out.recipes[0].slug == "soup"
    contents = client.models.calls[0]["contents"]
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert "catalog" in client.models.calls[0]["config"].system_instruction


def test_chat_requires_trailing_user_message():
    with pytest.raises(ValueError):
        recipe_chat.chat([{"role": "assistant", "text": "hello"}], "catalog", client=fake_client({}))


def test_chat_route_disabled_without_key(client):
    resp = client.post("/chat/message", json={"messages": [{"role": "user", "text": "hi"}]})
    assert resp.status_code == 503


def test_chat_route_filters_unknown_slugs(client, app_module, monkeypatch):
    captured = {}

    def fake_chat(messages, catalog, api_key=None):
        captured["catalog"] = catalog
        return ChatReply(
            reply="Make **soup** <script>x</script>",
            recipes=[RecipePick(slug="butternut_squash_soup", reason="cozy"),
                     RecipePick(slug="made_up_recipe", reason="nope")],
            ideas=[RecipeIdea(name="Shakshuka", summary="Eggs in tomato sauce")],
        )

    monkeypatch.setattr(app_module, "IMPORT_ENABLED", True)
    monkeypatch.setattr(app_module, "recipe_chat", fake_chat)
    data = client.post("/chat/message", json={"messages": [{"role": "user", "text": "soup?"}]}).get_json()

    assert "butternut_squash_soup | Butternut Squash Soup" in captured["catalog"]
    assert [r["slug"] for r in data["recipes"]] == ["butternut_squash_soup"]
    assert data["recipes"][0]["selected"] is False
    assert data["ideas"] == [{"name": "Shakshuka", "summary": "Eggs in tomato sauce"}]
    assert "<strong>soup</strong>" in data["reply_html"]
    assert "<script>" not in data["reply_html"]
