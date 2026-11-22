import pytest


@pytest.mark.parametrize("path", ["/", "/recipes_list", "/chat", "/manage", "/plan", "/editor", "/import", "/ingredients",
                                  "/service-worker.js", "/api/features", "/editor/recipes"])
def test_pages_load(client, path):
    assert client.get(path).status_code == 200


def test_features_disabled_without_keys(client):
    assert client.get("/api/features").get_json() == {"email_enabled": False, "import_enabled": False}


def test_recipes_are_discovered(app_module):
    slugs = {r.slug for r in app_module.get_all_recipes()}
    assert slugs == {"test_recipe", "butternut_squash_soup", "black_bean_and_pepper_jack_tostadas"}


def test_toggle_selection_drives_shopping_list(client, app_module):
    assert app_module.get_shopping_list_items() == {"main": {}, "secondary": {}}

    resp = client.post("/recipes_list/toggle/butternut_squash_soup")
    assert resp.get_json() == {"success": True, "selected": True}

    items = app_module.get_shopping_list_items()
    names = [i["name"] for group in items.values() for cat in group.values() for i in cat]
    assert "black beans" in names

    client.post("/deselect/butternut_squash_soup")
    assert app_module.get_shopping_list_items() == {"main": {}, "secondary": {}}


def test_toggle_unknown_recipe_404(client):
    assert client.post("/recipes_list/toggle/no_such_recipe").status_code == 404


def test_recipe_markdown_served(client):
    resp = client.get("/markdown/recipe/Butternut Squash Soup")
    assert resp.status_code == 200
    assert "Cook it." in resp.get_json()["content"]


@pytest.mark.parametrize("path", ["/archive/shopping_list", "/archive/shopping_demo"])
def test_archived_pages_unhooked(client, path):
    assert client.get(path).status_code == 404


def _fake_extract(calls):
    from recipe_core.gemini_importer import ImportResult
    from recipe_core.recipe_lib import RecipeData

    def fake(url=None, text=None, images=None, on_progress=None):
        calls.append({"url": url, "text": text, "images": images})
        data = RecipeData(name="Card Soup", servings=2, meal="dinner", category="entree",
                          ingredients=[{"food": "onion", "quantity": "1"}])
        return ImportResult(recipe_data=data, markdown="# Card Soup", slug="card_soup",
                            source="photo (1 image)", validation_errors=[])
    return fake


def _wait_for_job(client, job_id):
    import time
    for _ in range(50):
        data = client.get(f"/import/status/{job_id}").get_json()
        if data["status"] != "running":
            return data
        time.sleep(0.05)
    raise AssertionError("import job did not finish")


def test_import_photo_upload(client, app_module, monkeypatch):
    import io
    calls = []
    monkeypatch.setattr(app_module, "IMPORT_ENABLED", True)
    monkeypatch.setattr(app_module, "extract_recipe", _fake_extract(calls))

    resp = client.post("/import/extract", data={
        "text": "double it",
        "images": [(io.BytesIO(b"\xff\xd8fakejpeg"), "card.jpg", "image/jpeg")],
    }, content_type="multipart/form-data")
    assert resp.status_code == 200, resp.get_json()

    data = _wait_for_job(client, resp.get_json()["job_id"])
    assert data["status"] == "done"
    assert data["result"]["slug"] == "card_soup"
    assert calls[0]["text"] == "double it"
    assert calls[0]["images"] == [(b"\xff\xd8fakejpeg", "image/jpeg")]


def test_import_rejects_non_image(client, app_module, monkeypatch):
    import io
    monkeypatch.setattr(app_module, "IMPORT_ENABLED", True)
    resp = client.post("/import/extract", data={
        "images": [(io.BytesIO(b"hello"), "notes.txt", "text/plain")],
    }, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_import_confirm_writes_safe_yaml(client, app_module, monkeypatch):
    """Regression: pending recipe.yaml used to contain !!python/object tags for enums."""
    import yaml
    from recipe_core.recipe_lib import RecipeData
    calls = []
    monkeypatch.setattr(app_module, "IMPORT_ENABLED", True)
    monkeypatch.setattr(app_module, "extract_recipe", _fake_extract(calls))
    job = client.post("/import/extract", json={"text": "soup"}).get_json()["job_id"]
    assert _wait_for_job(client, job)["status"] == "done"
    assert client.post("/import/confirm").status_code == 200

    path = f"{app_module.PENDING_DIR}/card_soup/recipe.yaml"
    text = open(path).read()
    assert "!!python" not in text
    data = RecipeData(**yaml.safe_load(text))
    assert data.category.value == "ENTREE" and data.meal.value == "DINNER"
    loaded = client.get("/editor/recipe/pending/card_soup").get_json()
    assert loaded["yaml_error"] is None and loaded["metadata"]["servings"] == 2


def _draft(**over):
    d = {"name": "Weeknight Tacos", "servings": 4, "category": "ENTREE", "meal": "DINNER",
         "enabled": True, "min_period_weeks": 3,
         "ingredients": [{"food": "ground beef", "quantity": "1 lb"}, {"food": "tortillas", "quantity": ""}],
         "ingredients_md": "- 1 lb ground beef\n- 8 tortillas", "instructions_md": "1. Brown the beef.\n2. Fill.",
         "image_url": None, "source": "https://ex.com/tacos"}
    d.update(over)
    return d


def test_import_confirm_saved_with_edited_draft(client, app_module):
    import os
    resp = client.post("/import/confirm", json={"draft": _draft(), "destination": "saved"})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json() == {"success": True, "slug": "weeknight_tacos", "status": "saved"}
    d = os.path.join(app_module.RECIPES_DIR, "dinner", "weeknight_tacos")
    md = open(os.path.join(d, "recipe.md")).read()
    assert md.startswith("# Weeknight Tacos") and "## Instructions" in md and "1. Brown the beef." in md
    assert open(os.path.join(d, "source.txt")).read() == "https://ex.com/tacos"
    assert "weeknight_tacos" in {r.slug for r in app_module.get_all_recipes()}


def test_import_confirm_pending_and_conflict(client, app_module):
    assert client.post("/import/confirm", json={"draft": _draft(category="SIDE"), "destination": "pending"}).status_code == 200
    again = client.post("/import/confirm", json={"draft": _draft(), "destination": "saved"})
    assert again.status_code == 409
    bad = client.post("/import/confirm", json={"draft": _draft(name="X", meal="BRUNCH"), "destination": "saved"})
    assert bad.status_code == 400


def test_draft_from_import_splits_markdown():
    import app as app_mod
    from recipe_core.gemini_importer import ImportResult
    from recipe_core.recipe_lib import RecipeData
    md = ('# Soup\n\nServings: 2\n<img src="https://ex.com/soup.jpg" width=400>\n\n'
          '## Ingredients\n- 1 onion\n\n## Instructions\n1. Cook.\n')
    data = RecipeData(name="Soup", servings=2, meal="dinner", category="entree",
                      ingredients=[{"food": "onion", "quantity": "1"}])
    draft = app_mod._draft_from_import(ImportResult(recipe_data=data, markdown=md, slug="soup", source="x"))
    assert draft["ingredients_md"] == "- 1 onion" and draft["instructions_md"] == "1. Cook."
    assert draft["image_url"] == "https://ex.com/soup.jpg" and draft["category"] == "ENTREE"


def test_recipe_revise_route(client, app_module, monkeypatch):
    seen = {}

    def fake_revise(draft, instruction, history=None, api_key=None):
        seen.update(draft=draft, instruction=instruction)
        return {"draft": {**draft, "servings": 8}, "note": "Doubled it."}

    monkeypatch.setattr(app_module, "IMPORT_ENABLED", True)
    monkeypatch.setattr(app_module, "revise_recipe", fake_revise)
    data = client.post("/recipe/revise", json={"draft": _draft(), "instruction": "double it"}).get_json()
    assert data["note"] == "Doubled it." and data["draft"]["servings"] == 8
    assert seen["instruction"] == "double it"
    assert client.post("/recipe/revise", json={"draft": _draft(), "instruction": ""}).status_code == 400
