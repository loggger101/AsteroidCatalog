# -*- coding: utf-8 -*-
"""A value travels with what qualifies it, and identity survives its spelling.

Each case here failed before 0.13.0 on synthetic rows (General_Research rc-229,
rc-257 to rc-260, rc-268 to rc-272): none is a claim about a published row.
"""

import numpy as np
import pandas as pd
import pytest

import asteroid_catalog as ac
from asteroid_catalog.designations import _designation_key, _extract_canonical_designation
from asteroid_catalog.enrich import _normalise_type
from asteroid_catalog.merge import deduplicate_catalog
from asteroid_catalog.neowise import combine_neowise_fits
from asteroid_catalog.physics import smallest_diameter_km
from asteroid_catalog.release import physical_problems


def canon(*values):
    return _extract_canonical_designation(pd.Series(list(values), dtype="object")).tolist()


# ── rc-268: designations ─────────────────────────────────────────────────────
@pytest.mark.parametrize("raw, expected", [
    ("1999 Kw4", "1999 KW4"), ("1999 kw4", "1999 KW4"), ("1936 Ub", "1936 UB"),
    ("2040 p-l", "2040 P-L"), ("3138 t-1", "3138 T-1"), ("1996 gq0", "1996 GQ"),
    ("3568 ASCII", "3568"), ("3568 ascii", "3568"), ("(3568) ASCII", "3568"),
    ("(1999) Hirayama", "1999"), ("1999 Hirayama", "1999"),
])
def test_grammar_comes_before_a_leading_number(raw, expected):
    assert canon(raw) == [expected]


@pytest.mark.parametrize("raw", [
    "1 Ceres", "(1) Ceres", "2024 BX1", "1999 KW4", "2040 P-L", "3138 T-1",
    "4015 Wilson-Harrington", "A801 AA", "Ceres", "1",
])
def test_every_form_that_already_worked_still_does(raw):
    assert canon(raw) == _extract_canonical_designation(
        pd.Series([canon(raw)[0]], dtype="object")).tolist(), "not idempotent"


@pytest.mark.parametrize("unknown", ["1999 KW4 extra", "12 AB3", "2024 IA"])
def test_unrecognised_input_is_not_mapped_onto_a_number(unknown):
    assert canon(unknown) == [unknown]


def test_case_variants_of_one_designation_compare_equal():
    assert _designation_key(pd.Series(["1999 KW4", "1999 Kw4"])).nunique() == 1


def test_a_case_variant_reaches_the_body_it_names():
    bb = pd.DataFrame({"designation": ["1999", "66391", "3568"],
                       "provisional_designation": ["1973 DR", "1999 KW4", "1936 UB"],
                       "semi_major_axis_au": [2.5, 0.64, 2.4]})
    supp = pd.DataFrame({"designation": ["1999 Kw4", "1936 Ub", "3568 ascii"],
                         "rotation_period_h": [4.25, 7.0, np.nan]})
    out = ac.merge_sources({"JPL SBDB": bb, "S": supp}).set_index("designation")
    assert len(out) == 3
    assert out.loc["66391", "rotation_period_h"] == 4.25
    assert out.loc["3568", "rotation_period_h"] == 7.0
    assert np.isnan(out.loc["1999", "rotation_period_h"])


# ── rc-258: a value and its sigma come from one row ──────────────────────────
def test_a_duplicate_does_not_lend_its_sigma():
    d = pd.DataFrame({"designation": ["7", "7"],
                      "estimated_mass_kg": [1e13, 1e18],
                      "estimated_mass_sigma_kg": [np.nan, 1e16],
                      "taxonomy": ["S", None], "note": [None, "kept"], "x": [1.0, np.nan]})
    row = deduplicate_catalog(d, label="t").iloc[0]
    assert row["estimated_mass_kg"] == 1e13
    assert np.isnan(row["estimated_mass_sigma_kg"])
    assert row["note"] == "kept", "complementary fields still fill"


def test_a_sigma_from_its_own_row_survives():
    d = pd.DataFrame({"designation": ["7", "7"], "diameter_km": [5.0, np.nan],
                      "diameter_sigma_km": [0.5, np.nan], "y": [np.nan, 1.0]})
    row = deduplicate_catalog(d, label="t").iloc[0]
    assert row["diameter_km"] == 5.0 and row["diameter_sigma_km"] == 0.5


def test_a_value_filled_from_the_second_row_brings_its_sigma():
    d = pd.DataFrame({"designation": ["7", "7"], "diameter_km": [np.nan, 5.0],
                      "diameter_sigma_km": [np.nan, 0.5], "a": [1.0, np.nan],
                      "b": [2.0, np.nan]})
    row = deduplicate_catalog(d, label="t").iloc[0]
    assert row["diameter_km"] == 5.0 and row["diameter_sigma_km"] == 0.5


def test_an_orphan_sigma_is_dropped():
    d = pd.DataFrame({"designation": ["7", "7"], "albedo": [np.nan, np.nan],
                      "albedo_sigma": [np.nan, 0.1], "q": [1.0, np.nan]})
    assert np.isnan(deduplicate_catalog(d, label="t").iloc[0]["albedo_sigma"])


def test_the_preferred_mass_survives_the_screen_a_lent_sigma_failed():
    bb = pd.DataFrame({"designation": ["7"], "semi_major_axis_au": [2.3],
                       "diameter_km": [3.0], "spectral_type": ["S"]})
    supp = pd.DataFrame({"designation": ["7", "7"], "estimated_mass_kg": [1e13, 1e18],
                         "estimated_mass_sigma_kg": [np.nan, 1e16],
                         "z": [1.0, np.nan], "w": [1.0, np.nan]})
    assert ac.merge_sources({"JPL SBDB": bb, "S": supp}).iloc[0]["estimated_mass_kg"] == 1e13


# ── rc-257: a dropped mass takes its sigma with it ───────────────────────────
def _unfit_row(mass):
    return pd.DataFrame({
        "designation": ["7"], "spectral_type": ["S"], "semi_major_axis_au": [2.3],
        "absolute_magnitude_h": [15.0], "diameter_km": [2.0],
        "derived_diameter_is_estimate": [True], "diameter_source": ["taxonomy_albedo"],
        "estimated_mass_kg": [mass], "estimated_mass_sigma_kg": [mass / 10],
        "mass_provider": ["S"], "mass_screened_out": [pd.NA]})


@pytest.mark.parametrize("mass", [1e9, 1e20])
def test_a_refused_mass_leaves_no_sigma_on_its_replacement(mass):
    row = ac.enrich_composition(_unfit_row(mass)).iloc[0]
    assert not row["mass_measured"]
    assert row["estimated_mass_kg"] != mass
    assert np.isnan(row["estimated_mass_sigma_kg"])


def test_the_gate_refuses_a_sigma_on_a_derived_mass():
    out = ac.enrich_composition(_unfit_row(1e20))
    assert not [p for p in physical_problems(out) if "sigma" in p]
    out["estimated_mass_sigma_kg"] = 1e8
    assert [p for p in physical_problems(out) if "sigma" in p]


# ── rc-260: infinity is no measurement ───────────────────────────────────────
def test_an_infinite_source_value_is_refused_and_named():
    bb = pd.DataFrame({"designation": ["7", "8"], "semi_major_axis_au": [2.3, 2.3],
                       "diameter_km": [np.inf, 3.0], "albedo": [0.2, np.inf],
                       "absolute_magnitude_h": [15.0, 15.0]})
    out = ac.merge_sources({"JPL SBDB": bb}).set_index("designation")
    assert np.isnan(out.loc["7", "diameter_km"])
    assert out.loc["7", "diameter_screened_out"] == "JPL SBDB"
    assert np.isnan(out.loc["8", "albedo"])
    assert out.loc["8", "albedo_screened_out"] == "JPL SBDB"


def test_validation_refuses_infinite_size_and_orbit_by_name():
    df = pd.DataFrame({"designation": ["1", "2", "3"], "diameter_km": [np.inf, 1.0, 1.0],
                       "semi_major_axis_au": [2.0, np.inf, 2.0]})
    kept, log = ac.validate_and_filter(df, ac.CONFIG)
    assert kept["designation"].tolist() == ["3"]
    assert set(log["reason"]) == {"Non-finite diameter", "Non-finite semi-major axis"}


def test_an_overflowing_computation_is_rejected_after_enrichment():
    df = pd.DataFrame({"designation": ["1", "2"], "diameter_km": [1e120, 1.0],
                       "estimated_mass_kg": [np.inf, 1e12], "density_gcm3": [2.0, np.nan]})
    kept, log = ac.apply_final_gates(df, ac.CONFIG)
    assert kept["designation"].tolist() == ["2"]
    assert log["reason"].tolist() == ["Non-finite computed estimated_mass_kg"]


def test_the_gate_sees_infinity_and_a_nan_density_but_not_a_missing_estimate():
    base = {"designation": ["1"], "diameter_km": [1.0], "semi_major_axis_au": [2.0]}
    assert [p for p in physical_problems(pd.DataFrame({**base, "semi_major_axis_au": [np.inf]}))
            if "not finite" in p]
    assert [p for p in physical_problems(pd.DataFrame(
        {**base, "estimated_mass_kg": [1e12], "density_gcm3": [np.nan]})) if "no density" in p]
    assert not physical_problems(pd.DataFrame(
        {**base, "estimated_mass_kg": [np.nan], "density_gcm3": [np.nan]}))
    assert not physical_problems(pd.DataFrame({**base, "estimated_mass_kg": [1e12]})), \
        "a catalog without the column is not judged on it"


# ── rc-271: the floor judges the final diameter ──────────────────────────────
def test_the_floor_reads_the_diameter_enrichment_settled():
    low = ac.CatalogConfig(min_diameter_km=5.0)
    df = pd.DataFrame({"designation": ["1", "2", "3"],
                       "diameter_km": [4.0, 10.0, np.nan]})
    kept, log = ac.apply_final_gates(df, low)
    assert kept["designation"].tolist() == ["2", "3"]
    assert log["reason"].tolist() == ["diameter < 5.0 km"]


def test_validation_no_longer_drops_on_a_diameter_that_can_still_move():
    df = pd.DataFrame({"designation": ["1"], "diameter_km": [1.0],
                       "semi_major_axis_au": [2.0]})
    kept, _ = ac.validate_and_filter(df, ac.CatalogConfig(min_diameter_km=5.0))
    assert len(kept) == 1


# ── rc-272: one list of what "no class" looks like ───────────────────────────
@pytest.mark.parametrize("marker", ["-", "nan", "NaN", "None", "none", "NA", "<NA>", "  -  "])
def test_a_placeholder_is_no_class_in_strict_mode(marker):
    df = pd.DataFrame({"designation": ["1", "2"], "diameter_km": [1.0, 1.0],
                       "semi_major_axis_au": [2.0, 2.0],
                       "spectral_type": ["S", marker]})
    kept, _ = ac.validate_and_filter(df, ac.CatalogConfig(require_spectral_type=True))
    assert kept["designation"].tolist() == ["1"]


def test_a_tholen_placeholder_does_not_block_the_albedo_fallback():
    assert pd.isna(_normalise_type("-")) and _normalise_type("sq") == "Sq"
    df = pd.DataFrame({"designation": ["1"], "spectral_type": [np.nan],
                       "spectral_type_tholen": ["-"], "albedo": [0.2], "diameter_km": [1.0],
                       "semi_major_axis_au": [2.3]})
    row = ac.enrich_composition(df).iloc[0]
    assert row["spectral_type"] == "S" and row["spectral_type_source"] == "albedo"
    assert row["spectral_type_tholen"] == "-", "the raw cell is kept"


# ── rc-259: NEOWISE fits are pooled once, from the raw fits ──────────────────
def _fits():
    return pd.DataFrame({"designation": ["2010 AA", "2010 AA", "2010 BB"],
                         "diameter_km": [10.0, 12.0, 14.0],
                         "diameter_sigma_km": [1.0, 1.0, 1.0],
                         "neowise_n_fits": [1, 1, 1]})


def test_a_body_under_two_designations_pools_its_raw_fits():
    bb = pd.DataFrame({"designation": ["2010 AA"], "semi_major_axis_au": [2.5]})
    out = ac.merge_sources({"JPL SBDB": bb, "NEOWISE": _fits()},
                           links={"2010 BB": "2010 AA"})
    row = out.iloc[0]
    assert row["diameter_km"] == pytest.approx(12.0)
    assert row["diameter_sigma_km"] == pytest.approx(np.sqrt(8 / 3))
    assert row["neowise_n_fits"] == 3


def test_a_fit_with_no_sigma_has_no_weight_beside_one_that_has():
    fits = _fits().assign(diameter_sigma_km=[1.0, np.nan, np.nan])
    bb = pd.DataFrame({"designation": ["2010 AA"], "semi_major_axis_au": [2.5]})
    out = ac.merge_sources({"JPL SBDB": bb, "NEOWISE": fits}, links={"2010 BB": "2010 AA"})
    assert out.iloc[0]["diameter_km"] == 10.0


def test_with_no_sigma_at_all_every_fit_counts_equally():
    out = combine_neowise_fits(_fits().assign(designation="2010 AA", diameter_sigma_km=np.nan))
    assert out.iloc[0]["diameter_km"] == pytest.approx(12.0)


def test_distinct_bodies_stay_apart():
    out = combine_neowise_fits(_fits())
    assert sorted(out["designation"]) == ["2010 AA", "2010 BB"]


# ── rc-269, rc-270: an orbit is one record ───────────────────────────────────
ELEMENTS = {"semi_major_axis_au": 1.0, "eccentricity": 0.1, "inclination_deg": 5.0,
            "longitude_asc_node_deg": 10.0, "arg_perihelion_deg": 20.0,
            "mean_anomaly_deg": 30.0, "element_epoch_jd": 2451645.0}


def _orbit(designation, **over):
    return pd.DataFrame([{"designation": designation, **ELEMENTS, **over}])


def test_a_complete_backbone_orbit_is_left_alone():
    bb = _orbit("7", element_epoch_timescale="TDB")
    supp = _orbit("7", mean_anomaly_deg=99.0, element_epoch_jd=2451545.0)
    row = ac.merge_sources({"JPL SBDB": bb, "SsODNet": supp}).iloc[0]
    assert row["mean_anomaly_deg"] == 30.0 and row["element_epoch_jd"] == 2451645.0
    assert row["orbit_provider"] == "JPL SBDB"


def test_a_gap_is_not_filled_from_another_epoch():
    bb = _orbit("7", mean_anomaly_deg=np.nan)
    supp = _orbit("7", mean_anomaly_deg=10.0, element_epoch_jd=np.nan)
    row = ac.merge_sources({"JPL SBDB": bb, "SsODNet": supp}).iloc[0]
    assert np.isnan(row["mean_anomaly_deg"]), "another source's angle beside JPL's epoch"
    assert row["element_epoch_jd"] == 2451645.0


def test_an_incomplete_orbit_takes_a_complete_one_whole():
    bb = _orbit("7", mean_anomaly_deg=np.nan, element_epoch_timescale="TDB", mean_motion_deg_day=1.0)
    supp = _orbit("7", semi_major_axis_au=1.5, element_epoch_jd=2451545.0)
    row = ac.merge_sources({"JPL SBDB": bb, "SsODNet": supp}).iloc[0]
    assert row["orbit_provider"] == "SsODNet"
    assert row["semi_major_axis_au"] == 1.5 and row["mean_anomaly_deg"] == 30.0
    assert row["element_epoch_jd"] == 2451545.0
    assert pd.isna(row["element_epoch_timescale"]) and np.isnan(row["mean_motion_deg_day"])


def test_a_source_only_body_keeps_its_own_epoch_and_label():
    bb = _orbit("7")
    supp = _orbit("8", element_epoch_jd=2461300.5, element_epoch_timescale="TT")
    out = ac.merge_sources({"JPL SBDB": bb, "SsODNet": supp}).set_index("designation")
    assert out.loc["8", "element_epoch_jd"] == 2461300.5
    assert out.loc["8", "element_epoch_timescale"] == "TT"
    assert out.loc["8", "orbit_provider"] == "SsODNet"


def test_a_supplement_with_no_orbit_changes_nothing():
    bb = _orbit("7")
    supp = pd.DataFrame({"designation": ["7", "8"], "rotation_period_h": [5.0, 6.0]})
    out = ac.merge_sources({"JPL SBDB": bb, "S": supp}).set_index("designation")
    assert out.loc["7", "orbit_provider"] == "JPL SBDB"
    assert pd.isna(out.loc["8", "orbit_provider"])


def test_duplicates_do_not_mix_two_orbits():
    d = pd.DataFrame({"designation": ["7", "7"], "semi_major_axis_au": [1.0, 2.0],
                      "mean_anomaly_deg": [np.nan, 99.0], "element_epoch_jd": [1.0, 2.0],
                      "x": [1.0, np.nan]})
    row = deduplicate_catalog(d, label="t").iloc[0]
    assert row["semi_major_axis_au"] == 1.0 and row["element_epoch_jd"] == 1.0
    assert np.isnan(row["mean_anomaly_deg"])


# ── rc-283: H alone is a bound only at an assumed albedo ─────────────────────
def test_the_h_only_size_is_the_size_at_the_ceiling():
    assert smallest_diameter_km(np.nan, 15.0) == pytest.approx(1329.0 * 10 ** -3)
