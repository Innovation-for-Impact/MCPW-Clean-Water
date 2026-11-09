"""Tests for CERCLA RQ lookup and federal reporting checks."""

from src.services.cercla import check_federal_reporting_required, lookup_rq


class TestLookupRQ:
    def test_oil_fuel_substances(self):
        matches = lookup_rq("oil_fuel")
        assert len(matches) >= 4
        names = {s.substance for s in matches}
        assert "Gasoline" in names
        assert "Diesel fuel (No. 2)" in names

    def test_chemical_substances(self):
        matches = lookup_rq("chemical_hazmat")
        assert len(matches) >= 5

    def test_quantity_filter(self):
        # 100 lbs should exceed gasoline RQ (1 lb) but not all
        matches = lookup_rq("oil_fuel", quantity_lbs=100)
        assert len(matches) >= 1
        assert all(s.rq_lbs <= 100 for s in matches)

    def test_quantity_below_all(self):
        matches = lookup_rq("oil_fuel", quantity_lbs=0.01)
        assert len(matches) == 0

    def test_unknown_category(self):
        matches = lookup_rq("nonexistent")
        assert matches == []


class TestFederalReporting:
    def test_sewage_always_required(self):
        result = check_federal_reporting_required("sewage")
        assert result["required"] is True
        assert "CWA" in result["note"]

    def test_large_oil_spill_triggers(self):
        result = check_federal_reporting_required("oil_fuel", quantity_gallons=100)
        assert result["required"] is True
        assert len(result["triggered_substances"]) >= 1

    def test_small_quantity_no_trigger(self):
        result = check_federal_reporting_required("oil_fuel", quantity_gallons=0.001)
        assert result["required"] is False

    def test_unknown_quantity(self):
        result = check_federal_reporting_required("oil_fuel")
        assert result["required"] is False
        assert "unknown" in result["note"].lower()

    def test_chemical_with_lbs(self):
        result = check_federal_reporting_required("chemical_hazmat", quantity_lbs=5000)
        assert result["required"] is True
