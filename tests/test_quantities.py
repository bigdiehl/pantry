import pytest

from recipe_core.recipe_lib import _float_to_frac, parse_quantity


@pytest.mark.parametrize("raw, magnitude, unit", [
    ("1.5 cups", 1.5, "cup"),
    ("1/4 tsp", 0.25, "teaspoon"),
    ("2 cans", 2, "cans"),
    ("2 cloves", 2, "clove"),
    ("1 bunch", 1, "bunch"),
    ("3", 3, "dimensionless"),
])
def test_parse_quantity(raw, magnitude, unit):
    q = parse_quantity(raw)
    assert q.magnitude == pytest.approx(magnitude)
    assert str(q.units) == unit


@pytest.mark.parametrize("raw", ["", "   "])
def test_parse_quantity_unspecified(raw):
    assert parse_quantity(raw) is None


def test_parse_quantity_registers_unknown_unit():
    q = parse_quantity("2 zorbles")
    assert q.magnitude == 2
    assert q + parse_quantity("1 zorbles") == parse_quantity("3 zorbles")


def test_parse_quantity_rejects_garbage():
    with pytest.raises(ValueError):
        parse_quantity("a handful of something")


@pytest.mark.parametrize("value, expected", [
    (2.0, "2"), (0.25, "1/4"), (1.5, "1 1/2"), (0.333333, "1/3"),
])
def test_float_to_frac(value, expected):
    assert _float_to_frac(value) == expected
