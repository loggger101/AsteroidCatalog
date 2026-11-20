# -*- coding: utf-8 -*-
"""The SsODNet property-reference map (General_Research rc-768), offline."""

import pandas as pd

from asteroid_catalog import CatalogConfig
from asteroid_catalog import ssodnet_refs as R
from asteroid_catalog.release import SSODNET_REFS_CSV

_BIB = [{"shortbib": "Russell+2016", "bibcode": "2016Sci...353.1008R",
         "doi": "10.1126/science.aaf4219"}]


def _card(cid, number, mass=9.38e20, diameter=939.4):
    return {"id": cid, "number": number,
            "ssocard": {"version": "1.2.4", "datetime": "2026-09-14T23:00:01+00:00"},
            "parameters": {"physical": {
                "diameter": {"value": diameter, "bibref": _BIB},
                "mass": {"value": mass, "bibref": _BIB},
                "density": {"value": 2160.0, "bibref": []},
                "absolute_magnitude": {"H": {"value": 3.3}, "bibref": _BIB},
                "taxonomy": {"class": "C", "bibref": _BIB}}}}


def _frame():
    return pd.DataFrame({
        "designation": ["1", "469705", "2"],
        "ssodnet_id": ["Ceres", "��Kagara", "Pallas"],
        "estimated_mass_kg": [9.38e20, 1.0e18, None],
        "density_gcm3": [2.16, None, None],
        "diameter_km": [939.4, 170.0, 513.0],
        "spectral_type": ["C", None, "B"],
        "absolute_magnitude_h": [3.3, None, 4.1],
    })


class _Resp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def test_only_bodies_with_a_mass_or_density_are_mapped():
    assert list(R.bodies_to_map(_frame())["ssodnet_id"]) == ["Ceres", "��Kagara"]


def test_the_map_names_each_values_reference(monkeypatch):
    asked = []

    def fake_get(url, timeout):
        asked.append(url)
        if "Ceres" in url:          # the garbled id finds nothing
            return _Resp([_card("Ceres", 1)])
        return _Resp([_card("Kagara", 469705, mass=1.0e18, diameter=170.0)])

    monkeypatch.setattr(R.requests, "get", fake_get)
    monkeypatch.setattr(R, "PAUSE_S", 0)
    df = R.property_refs(_frame(), CatalogConfig())
    assert len(asked) == 2, "one batch, then the number retry"
    assert "469705" in asked[1]
    ceres = df[df["ssodnet_id"] == "Ceres"].set_index("property")
    assert ceres.loc["estimated_mass_kg", "bibcode"] == "2016Sci...353.1008R"
    assert ceres.loc["estimated_mass_kg", "status"] == "resolved"
    assert ceres.loc["density_gcm3", "status"] == "no bibref in card"
    assert abs(ceres.loc["density_gcm3", "card_value"] - 2.16) < 1e-12, "kg/m^3 to g/cm^3"
    assert ceres.loc["spectral_type", "values_agree"]
    kag = df[df["designation"] == "469705"]
    assert set(kag["status"]) == {"resolved"}, "found again by number"
    assert "Pallas" not in set(df["ssodnet_id"])


def test_a_card_whose_value_differs_is_flagged():
    row = pd.Series({"designation": "1", "ssodnet_id": "Ceres",
                     "estimated_mass_kg": 9.0e20})
    out = R.property_rows(row, _card("Ceres", 1))
    assert out[0]["status"].startswith("card value differs")


def test_a_failed_request_marks_its_bodies_unavailable(monkeypatch):
    def boom(url, timeout):
        raise R.requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(R.requests, "get", boom)
    df = R.property_refs(_frame(), CatalogConfig())
    assert set(df["status"]) == {"card unavailable"}
    assert R.refs_summary(df)["bodies"] == 2


def test_the_two_filenames_agree():
    assert R.REFS_FILENAME == SSODNET_REFS_CSV
