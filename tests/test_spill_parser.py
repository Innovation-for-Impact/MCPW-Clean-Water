"""Tests for spill parser — driven by parser-test-cases.json."""

import json
from pathlib import Path

import pytest

from src.services.spill_parser import parse_spill_text

_CASES_PATH = Path(__file__).parent / "parser-test-cases.json"
_CASES = json.loads(_CASES_PATH.read_text())


def _case_id(case: dict) -> str:
    return f"{case['id']}: {case['description']}"


@pytest.mark.parametrize("case", _CASES, ids=[_case_id(c) for c in _CASES])
def test_parse_spill_text(case):
    result = parse_spill_text(case["input"])
    expected = case["expected"]

    for key, val in expected.items():
        if key == "has_time_observed":
            if val:
                assert "time_observed" in result, f"Expected time_observed in result for {case['id']}"
            continue
        assert key in result, f"Missing key '{key}' in result for {case['id']}"
        if isinstance(val, float):
            assert abs(result[key] - val) < 0.01, f"Key '{key}' mismatch for {case['id']}: {result[key]} != {val}"
        elif isinstance(val, dict):
            for dk, dv in val.items():
                assert abs(result[key][dk] - dv) < 0.001, (
                    f"Key '{key}.{dk}' mismatch for {case['id']}: {result[key][dk]} != {dv}"
                )
        else:
            assert result[key] == val, f"Key '{key}' mismatch for {case['id']}: {result[key]} != {val}"


class TestParserEdgeCases:
    def test_comma_separated_quantity(self):
        result = parse_spill_text("about 1,500 gallons of diesel")
        assert result["quantity"] == 1500.0
        assert result["quantity_gallons"] == 1500.0

    def test_mt_clemens_abbreviation(self):
        result = parse_spill_text("spill near Mt. Clemens")
        assert result["address_hint"] == "Mt. Clemens"

    def test_case_insensitive_water_body(self):
        result = parse_spill_text("spill in CLINTON RIVER")
        assert result["water_body"] == "clinton_river"

    def test_case_insensitive_material(self):
        result = parse_spill_text("DIESEL fuel leak")
        assert result["material"] == "oil_fuel"
        assert result["material_detail"] == "diesel"

    def test_minutes_ago(self):
        result = parse_spill_text("gasoline spill 30 minutes ago")
        assert "time_observed" in result

    def test_this_morning(self):
        result = parse_spill_text("oil sheen spotted this morning")
        assert "time_observed" in result
