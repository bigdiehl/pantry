import pytest


@pytest.mark.parametrize("path", ["/", "/recipes_list", "/editor", "/archive/shopping_list",
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
