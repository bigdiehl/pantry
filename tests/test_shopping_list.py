from recipe_core.foods import get_food
from recipe_core.recipe_lib import Ingredient, MergedIngredient, RecipeData, parse_quantity
from recipe_core.shopping_list import (
    find_recipe_dirs,
    generate_shopping_list_md,
    get_merged_shopping_list,
    get_shopping_list_data,
)


def _merged(*items):
    food = get_food("onion")
    m = MergedIngredient(food=food)
    for qty, src in items:
        m.add(Ingredient(food=food, quantity=parse_quantity(qty), source=src))
    return m


def test_compatible_units_sum():
    assert _merged(("1 cup", "a"), ("0.5 cup", "b")).format_quantity(["a", "b"]) == "1 1/2 cup"


def test_incompatible_units_stay_separate():
    m = _merged(("1 cup", "a"), ("2 cans", "b"))
    assert len(m.quantities) == 2
    assert m.format_quantity(["a", "b"]) == "1 cup + 2 cans"


def test_unspecified_is_tracked_by_source():
    m = _merged(("1 cup", "a"), ("", "b"))
    assert m.unspecified == ["b"]
    assert m.format_quantity(["a", "b"]) == "1 cup + unspecified from [2]"
    assert m.format_sources(["a", "b"]) == "[1], [2]"
    assert m.all_source_slugs() == ["a", "b"]


def test_food_lookup_exact_alias_and_fallback():
    assert get_food("Onion").get_name() == get_food("white onion").get_name()
    unknown = get_food("definitely not a food")
    assert unknown.get_name() == "definitely not a food"


def test_recipe_yaml_normalises_enums(fixtures_dir):
    r = RecipeData.from_yaml(fixtures_dir / "test_recipe" / "recipe.yaml")
    assert r.meal.value == "DINNER"
    assert r.category.value == "ENTREE"
    assert r.min_period_weeks == 4


def test_load_and_merge_fixture_recipes(fixtures_dir):
    assert len(find_recipe_dirs(str(fixtures_dir))) == 3
    lists, metas = get_shopping_list_data(str(fixtures_dir))
    assert set(lists) == {"test_recipe", "butternut_squash_soup", "black_bean_and_pepper_jack_tostadas"}

    slugs = ["butternut_squash_soup", "black_bean_and_pepper_jack_tostadas"]
    main, secondary = get_merged_shopping_list(slugs, lists)
    everything = [mi for group in (main, secondary) for items in group.values() for mi in items]
    beans = [mi for mi in everything if mi.food.has_name("black beans")]
    assert len(beans) == 1
    assert beans[0].format_quantity(slugs) == "2 cup + 2 cans"

    md = generate_shopping_list_md([metas[s].name for s in slugs], slugs, main, secondary)
    assert "Butternut Squash Soup" in md
    assert "black beans" in md.lower()


def test_missing_recipe_is_skipped(fixtures_dir):
    lists, _ = get_shopping_list_data(str(fixtures_dir))
    main, secondary = get_merged_shopping_list(["nope"], lists)
    assert main == {} or all(not v for v in main.values())
