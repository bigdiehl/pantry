"""Shared fixtures. Points the app at a throwaway data dir built from recipe_core/test."""

import os
import shutil
import yaml
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "recipe_core" / "test"

# web/app.py reads RECIPES_DATA_DIR at import time, so set it before any test imports it.
_DATA_DIR = Path(tempfile.mkdtemp(prefix="pantry_test_data_"))
os.environ["RECIPES_DATA_DIR"] = str(_DATA_DIR)
for var in ("GMAIL_SENDER", "GMAIL_APP_PASSWORD", "GEMINI_API_KEY"):
    os.environ.pop(var, None)

sys.path.insert(0, str(ROOT / "web"))


def _populate(data_dir: Path) -> None:
    saved = data_dir / "recipes" / "saved" / "dinner"
    for sub in ("pending", "archived"):
        (data_dir / "recipes" / sub).mkdir(parents=True, exist_ok=True)
    for recipe in FIXTURES.iterdir():
        shutil.copytree(recipe, saved / recipe.name)
        name = yaml.safe_load((recipe / "recipe.yaml").read_text())["name"]
        (saved / recipe.name / "recipe.md").write_text(f"# {name}\n\nCook it.\n")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    """The Flask app module, with fresh recipe data and an isolated state/output dir."""
    shutil.rmtree(_DATA_DIR / "recipes", ignore_errors=True)
    _populate(_DATA_DIR)

    import app as app_mod

    monkeypatch.setattr(app_mod, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(app_mod, "OUTPUT_DIR", str(tmp_path / "output"))
    from recipe_core.push import PushStore
    monkeypatch.setattr(app_mod, "PUSH", PushStore(str(tmp_path / "instance")))
    app_mod._invalidate_shopping_list_cache()
    app_mod.app.config["TESTING"] = True
    return app_mod


@pytest.fixture
def client(app_module):
    return app_module.app.test_client()


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_DATA_DIR, ignore_errors=True)
