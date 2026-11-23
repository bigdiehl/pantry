import json
from types import SimpleNamespace

import pytest

from recipe_core import recipe_chat
from recipe_core.recipe_chat import ChatReply, RecipePick, build_catalog
from recipe_core.recipe_search import WebRecipe, format_duration, parse_recipe_page


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
    client = fake_client({"reply": "Try the soup.", "recipes": [{"slug": "soup", "reason": "warm"}]})
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
            recipes=[RecipePick(slug="butternut_squash_soup", reason="cozy", missing=["butternut squash", "bacon"]),
                     RecipePick(slug="made_up_recipe", reason="nope")],
            offer_search=True,
        )

    monkeypatch.setattr(app_module, "IMPORT_ENABLED", True)
    monkeypatch.setattr(app_module, "recipe_chat", fake_chat)
    data = client.post("/chat/message", json={"messages": [{"role": "user", "text": "soup?"}]}).get_json()

    assert "butternut_squash_soup | Butternut Squash Soup" in captured["catalog"]
    assert [r["slug"] for r in data["recipes"]] == ["butternut_squash_soup"]
    assert data["recipes"][0]["selected"] is False
    assert data["recipes"][0]["image_url"] is None      # fixtures have no photos
    assert data["offer_search"] is True and data["web_recipes"] == []
    assert data["recipes"][0]["missing"] == ["butternut squash", "bacon"]
    assert data["recipes"][0]["key_ingredients"] == []
    assert "<strong>soup</strong>" in data["reply_html"]
    assert "<script>" not in data["reply_html"]


def test_chat_route_runs_web_search(client, app_module, monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "IMPORT_ENABLED", True)
    monkeypatch.setattr(app_module, "recipe_chat", lambda *a, **k: ChatReply(
        reply="Here are a few:", web_search="lentil soup", offer_search=True))
    monkeypatch.setattr(app_module, "web_recipe_search", lambda q, exclude=None: calls.append((q, exclude)) or [
        WebRecipe(title="Lentil Soup", url="https://ex.com/lentil", site="Ex", image="https://ex.com/a.jpg")])

    data = client.post("/chat/message", json={"messages": [{"role": "user", "text": "yes"}]}).get_json()
    assert calls[0][0] == "lentil soup" and "Butternut Squash Soup" in calls[0][1]
    assert data["web_recipes"][0]["url"] == "https://ex.com/lentil"
    assert data["offer_search"] is False                 # already searched


RECIPE_PAGE = """<html><head>
<meta property="og:site_name" content="Example Kitchen">
<script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
  {"@type": "WebPage", "name": "page"},
  {"@type": ["Recipe"], "name": "Lemon  Chicken", "image": [{"url": "/img/lemon.jpg"}],
   "description": "<p>Bright and   easy.</p>", "totalTime": "PT1H15M",
   "recipeIngredient": ["2 lemons, zested", "1 1/2 lbs chicken thighs", "Kosher salt", "2 tbsp olive oil"]}]}</script>
</head><body></body></html>"""


def test_parse_recipe_page():
    r = parse_recipe_page(RECIPE_PAGE, "https://www.example.com/lemon-chicken/")
    assert r.title == "Lemon Chicken"
    assert r.site == "Example Kitchen"
    assert r.image == "https://www.example.com/img/lemon.jpg"
    assert r.summary == "Bright and easy."
    assert r.total_time == "1 hr 15 min"
    assert r.key_ingredients == ["lemons", "chicken thighs"]


def test_parse_non_recipe_page_is_none():
    assert parse_recipe_page("<html><head><title>Blog</title></head></html>", "https://ex.com") is None


@pytest.mark.parametrize("iso, out", [("PT45M", "45 min"), ("PT90M", "1 hr 30 min"), ("PT2H", "2 hr"), ("P0DT1H5M", "1 hr 5 min"), ("", ""), ("soon", "")])
def test_format_duration(iso, out):
    assert format_duration(iso) == out


def test_chat_route_search_button_skips_model(client, app_module, monkeypatch):
    monkeypatch.setattr(app_module, "IMPORT_ENABLED", True)
    monkeypatch.setattr(app_module, "recipe_chat", lambda *a, **k: pytest.fail("model should not be called"))
    monkeypatch.setattr(app_module, "web_recipe_search", lambda q, exclude=None: [
        WebRecipe(title=q.title(), url="https://ex.com/r", site="ex.com")])
    data = client.post("/chat/message", json={"search": "chicken fajitas",
                                              "messages": [{"role": "user", "text": "Look for new recipes"}]}).get_json()
    assert data["web_recipes"][0]["title"] == "Chicken Fajitas"


def test_title_from_url():
    from recipe_core.recipe_search import _title_from_url
    assert _title_from_url("https://www.budgetbytes.com/slow-cooker-italian-chicken-and-peppers/") == "Slow Cooker Italian Chicken And Peppers"
    assert _title_from_url("https://ex.com/recipes/12345-easy-fajitas-recipe.html") == "Easy Fajitas"


def test_revise_recipe_keeps_passthrough_fields():
    from recipe_core.recipe_revise import revise_recipe
    reply = {"recipe": {"name": "Tacos", "servings": 8, "category": "entree", "meal": "dinner",
                        "ingredients": [{"food": "ground beef", "quantity": "2 lb"}],
                        "ingredients_md": "- 2 lb ground beef", "instructions_md": "1. Brown."},
             "note": "Doubled."}
    client = fake_client(reply)
    out = revise_recipe({"name": "Tacos", "servings": 4, "category": "ENTREE", "meal": "DINNER",
                         "ingredients": [{"food": "ground beef", "quantity": "1 lb"}],
                         "ingredients_md": "- 1 lb ground beef", "instructions_md": "1. Brown.",
                         "image_url": "https://ex.com/t.jpg", "min_period_weeks": 3},
                        "double it", history=[{"instruction": "hi", "note": "ok"}], client=client)
    assert out["note"] == "Doubled."
    assert out["draft"]["servings"] == 8 and out["draft"]["category"] == "ENTREE"
    assert out["draft"]["image_url"] == "https://ex.com/t.jpg" and out["draft"]["min_period_weeks"] == 3
    roles = [c.role for c in client.models.calls[0]["contents"]]
    assert roles == ["user", "model", "user"]


def test_key_ingredients_strips_amounts_and_staples():
    from recipe_core.recipe_search import key_ingredients
    lines = ["2 lbs boneless chicken thighs, trimmed", "1 tablespoon olive oil", "Salt and pepper",
             "1 (14 oz) can diced tomatoes", "1 large red bell pepper, sliced", "Freshly ground black pepper",
             "water", "3 cloves garlic, minced"]
    assert key_ingredients(lines) == ["boneless chicken thighs", "diced tomatoes", "red bell pepper", "garlic"]


def test_generate_falls_back_on_quota(monkeypatch):
    from google.genai import errors
    from recipe_core import gemini

    tried = []

    class Models:
        def generate_content(self, model, contents, config=None):
            tried.append(model)
            if model == "primary":
                raise errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
            return SimpleNamespace(text="ok")

    monkeypatch.setattr(gemini, "PRIMARY_MODEL", "primary")
    monkeypatch.setattr(gemini, "FALLBACK_MODELS", ["backup"])
    assert gemini.generate(SimpleNamespace(models=Models()), contents="hi").text == "ok"
    assert tried == ["primary", "backup"]


def test_generate_does_not_retry_other_errors(monkeypatch):
    from google.genai import errors
    from recipe_core import gemini

    class Models:
        def generate_content(self, model, contents, config=None):
            raise errors.ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}})

    monkeypatch.setattr(gemini, "FALLBACK_MODELS", ["backup"])
    with pytest.raises(errors.ClientError):
        gemini.generate(SimpleNamespace(models=Models()), contents="hi")
    assert "daily free limit" in gemini.friendly_error(errors.ClientError(429, {"error": {"code": 429, "message": "q"}}))
