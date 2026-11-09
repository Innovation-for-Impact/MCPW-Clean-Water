"""Tests for unit conversion and material categorization service."""

import pytest

from src.services.units import categorize_material, convert_from_gallons, convert_to_gallons, convert_units


class TestConvertToGallons:
    def test_gallons_identity(self):
        assert convert_to_gallons(10, "gal") == 10.0

    def test_barrels_to_gallons(self):
        assert convert_to_gallons(1, "bbl") == 42.0

    def test_liters_to_gallons(self):
        result = convert_to_gallons(100, "L")
        assert 26.0 <= result <= 27.0  # ~26.42

    def test_pounds_to_gallons(self):
        result = convert_to_gallons(100, "lb")
        assert 11.0 <= result <= 13.0

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError, match="Unknown unit"):
            convert_to_gallons(10, "kg")


class TestConvertFromGallons:
    def test_gallons_identity(self):
        assert convert_from_gallons(42, "gal") == 42.0

    def test_gallons_to_barrels(self):
        assert convert_from_gallons(42, "bbl") == 1.0

    def test_gallons_to_liters(self):
        result = convert_from_gallons(1, "L")
        assert 3.7 <= result <= 3.8  # ~3.785

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError, match="Unknown unit"):
            convert_from_gallons(10, "m3")


class TestConvertUnits:
    def test_barrels_to_liters(self):
        result = convert_units(1, "bbl", "L")
        assert 158.0 <= result <= 160.0  # 1 bbl ≈ 159 L

    def test_roundtrip(self):
        original = 100.0
        gallons = convert_to_gallons(original, "L")
        back = convert_from_gallons(gallons, "L")
        assert abs(back - original) < 0.01


class TestCategorizeMaterial:
    def test_oil_keywords(self):
        assert categorize_material("diesel fuel spill") == "oil_fuel"
        assert categorize_material("gasoline leak") == "oil_fuel"
        assert categorize_material("motor oil") == "oil_fuel"
        assert categorize_material("hydraulic fluid") == "oil_fuel"

    def test_chemical_keywords(self):
        assert categorize_material("sulfuric acid spill") == "chemical_hazmat"
        assert categorize_material("chlorine gas leak") == "chemical_hazmat"
        assert categorize_material("hazardous waste") == "chemical_hazmat"

    def test_sewage_keywords(self):
        assert categorize_material("raw sewage overflow") == "sewage"
        assert categorize_material("septic tank leak") == "sewage"
        assert categorize_material("sanitary sewer overflow") == "sewage"

    def test_unknown(self):
        assert categorize_material("mystery substance") == "unknown_other"
        assert categorize_material("") == "unknown_other"

    def test_case_insensitive(self):
        assert categorize_material("DIESEL FUEL") == "oil_fuel"
        assert categorize_material("Ammonia") == "chemical_hazmat"
