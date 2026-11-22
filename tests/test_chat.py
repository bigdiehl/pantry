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
            recipes=[RecipePick(slug="butternut_squash_soup", reason="cozy"),
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
   "description": "<p>Bright and   easy.</p>", "totalTime": "PT1H15M"}]}</script>
</head><body></body></html>"""


def test_parse_recipe_page():
    r = parse_recipe_page(RECIPE_PAGE, "https://www.example.com/lemon-chicken/")
    assert r.title == "Lemon Chicken"
    assert r.site == "Example Kitchen"
    assert r.image == "https://www.example.com/img/lemon.jpg"
    assert r.summary == "Bright and easy."
    assert r.total_time == "1 hr 15 min"


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
