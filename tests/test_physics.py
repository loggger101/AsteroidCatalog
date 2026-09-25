# -*- coding: utf-8 -*-
"""Nothing physically impossible reaches the catalog, however well sourced.

Every case here is a real row of the 2026-09-23 release (data contract 1.3.0),
reduced to the columns that made it wrong:

  * 1686 De Sitter, 6.76e18 kg on 29.7 km: 495 g/cm3, from MP3C alone.
  * 704 Interamnia, JPL GM 5.0 km^3/s^2 (one significant figure): a B-type at
    5.0 g/cm3.  10 Hygiea, GM 7.0: 1.05e20 kg where the literature has 8.7e19.
  * 15 Eunomia, SsODNet's mass beside JPL's radiometric diameter: 4.9 g/cm3;
    SsODNet's own diameter (271 km, adaptive optics) gives 3.1.
  * TNO binaries: SsODNet and MP3C give the SYSTEM mass, MP3C alone the
    primary's diameter, at an implied albedo up to 1.8.
  * 2003 QY90: a measured mass beside an H-derived diameter, 0.06 g/cm3.
  * 153 Hilda: a mass whose sigma is 23x the value.
  * 24 JPL albedos of exactly 1.000; 10-18 km bodies spinning in under an hour.
  * Pluto, Makemake, Haumea and Sedna typed as basalt from their albedo.
"""

import numpy as np
import pandas as pd
import pytest

import asteroid_catalog as ac
from asteroid_catalog.physics import (
    DENSITY_LIMITS_GCM3, bulk_density_gcm3, min_rotation_period_h,
    taxonomy_group,
)
from asteroid_catalog.release import check_release, physical_problems


def _merge(jpl, *supps):
    names = ["SsODNet", "NEOWISE", "MP3C"]
    sources = {"JPL SBDB": pd.DataFrame(jpl)}
    for name, s in zip(names, supps):
        if s is not None:
            sources[name] = pd.DataFrame(s)
    return ac.merge_sources(sources).set_index("designation")


def _build(jpl, *supps):
    """merge -> derive -> validate -> enrich, as build_catalog runs them."""
    names = ["SsODNet", "NEOWISE", "MP3C"]
    sources = {"JPL SBDB": pd.DataFrame(jpl)}
    for name, s in zip(names, supps):
        if s is not None:
            sources[name] = pd.DataFrame(s)
    m = ac.merge_sources(sources)
    d = ac.derive_missing_diameters(m, ac.CONFIG)
    v, _ = ac.validate_and_filter(d, ac.CONFIG)
    return ac.enrich_composition(v).set_index("designation")


# ---------------------------------------------------------------------------
# the limits themselves
# ---------------------------------------------------------------------------
def test_every_taxonomy_group_has_density_limits():
    """A class added to TAXONOMY_COMPOSITION under a new group would fall to
    the any-class limits silently; make it a decision instead."""
    groups = {v["group"] for v in ac.TAXONOMY_COMPOSITION.values()}
    assert groups <= set(DENSITY_LIMITS_GCM3), groups - set(DENSITY_LIMITS_GCM3)


def test_no_class_estimate_is_itself_impossible():
    for cls, row in ac.TAXONOMY_COMPOSITION.items():
        if row["density_est_gcm3"] is None:
            continue
        lo, hi = DENSITY_LIMITS_GCM3[row["group"]]
        assert lo <= row["density_est_gcm3"] <= hi, cls


@pytest.mark.parametrize("raw,group", [
    ("S(iv)", "S-complex"), ("Bk", "C-complex"), ("X:", "X-complex"),
    ("sq", "S-complex"), ("Z", "Unknown"), (None, "Unknown"), ("", "Unknown"),
])
def test_taxonomy_group_reads_classes_as_sources_spell_them(raw, group):
    assert taxonomy_group(raw) == group


def test_breakup_period():
    """3.3 h / sqrt(rho): the textbook form of sqrt(3 pi / G rho)."""
    assert min_rotation_period_h(1.0) == pytest.approx(3.30, abs=0.01)
    assert min_rotation_period_h(8.0) == pytest.approx(1.17, abs=0.01)


# ---------------------------------------------------------------------------
# masses
# ---------------------------------------------------------------------------
def test_an_impossible_mass_is_refused_and_derived_instead():
    """De Sitter: 6.76e18 kg on 29.7 km is 495 g/cm3."""
    jpl = {"designation": ["1686"], "semi_major_axis_au": [2.7],
           "absolute_magnitude_h": [11.16], "diameter_km": [29.661],
           "albedo": [0.088], "spectral_type": ["Cb"]}
    mp3c = {"designation": ["1686"], "diameter_km": [29.0],
            "estimated_mass_kg": [6.76e18], "estimated_mass_sigma_kg": [3.18e18]}
    row = _build(jpl, None, None, mp3c).loc["1686"]
    assert row["mass_screened_out"] == "MP3C"
    assert not row["mass_measured"] and pd.isna(row["mass_provider"])
    assert row["diameter_km"] == 29.661, "the well-supported diameter stays"
    assert row["density_gcm3"] == ac.TAXONOMY_COMPOSITION["Cb"]["density_est_gcm3"]


def test_mass_prefers_ssodnet_over_a_one_figure_jpl_gm():
    """Hygiea: JPL GM 7.0 -> 1.05e20 kg; SsODNet 8.74e19."""
    jpl = {"designation": ["10"], "semi_major_axis_au": [3.14],
           "diameter_km": [407.12], "estimated_mass_kg": [1.048799e20],
           "spectral_type": ["C"]}
    ssod = {"designation": ["10"], "diameter_km": [434.0],
            "estimated_mass_kg": [8.74e19], "estimated_mass_sigma_kg": [6.9e18]}
    row = _merge(jpl, ssod).loc["10"]
    assert row["estimated_mass_kg"] == 8.74e19
    assert row["mass_provider"] == "SsODNet"
    assert row["mass_n_sources"] == 2


def test_a_mass_impossible_for_its_class_is_refused():
    """Interamnia: JPL's 7.49e19 kg makes a B-type 5.0 g/cm3 (or 3.9 on
    SsODNet's diameter); carbonaceous rock tops out at 3.6."""
    jpl = {"designation": ["704"], "semi_major_axis_au": [3.06],
           "diameter_km": [306.313], "estimated_mass_kg": [7.491422e19],
           "spectral_type": ["B"]}
    ssod = {"designation": ["704"], "diameter_km": [332.0],
            "estimated_mass_kg": [3.5e19], "estimated_mass_sigma_kg": [5e18]}
    row = _merge(jpl, ssod).loc["704"]
    assert row["estimated_mass_kg"] == 3.5e19
    assert row["mass_screened_out"] == "JPL SBDB"


def test_a_mass_is_published_beside_its_own_diameter():
    """Eunomia: SsODNet's mass over JPL's 231.7 km is 4.9 g/cm3; over
    SsODNet's own 271.3 km, 3.06."""
    jpl = {"designation": ["15"], "semi_major_axis_au": [2.64],
           "diameter_km": [231.689], "spectral_type": ["S"]}
    ssod = {"designation": ["15"], "diameter_km": [271.3],
            "diameter_sigma_km": [5.0],
            "estimated_mass_kg": [3.197e19], "estimated_mass_sigma_kg": [4.5e17]}
    row = _merge(jpl, ssod).loc["15"]
    assert row["diameter_km"] == 271.3 and row["diameter_provider"] == "SsODNet"
    assert row["diameter_sigma_km"] == 5.0, "the sigma travels with its value"
    assert bulk_density_gcm3(row["estimated_mass_kg"], row["diameter_km"]) \
        == pytest.approx(3.06, abs=0.01)


def test_a_mass_without_a_determination_is_refused():
    """153 Hilda: 3.04e18 +/- 7.04e19 kg."""
    jpl = {"designation": ["153"], "semi_major_axis_au": [3.97],
           "diameter_km": [170.63], "spectral_type": ["P"]}
    ssod = {"designation": ["153"], "estimated_mass_kg": [3.04e18],
            "estimated_mass_sigma_kg": [7.04e19]}
    row = _merge(jpl, ssod).loc["153"]
    assert pd.isna(row["estimated_mass_kg"])
    assert row["mass_screened_out"] == "SsODNet"


def test_a_system_mass_beside_a_primary_diameter_drops_the_diameter():
    """2006 CH69: two sources give the binary's mass, one the primary's size
    (implied albedo 1.65).  The diameter goes, and is re-derived from the
    mass downstream."""
    jpl = {"designation": ["2006 CH69"], "semi_major_axis_au": [44.0],
           "absolute_magnitude_h": [6.58]}
    ssod = {"designation": ["2006 CH69"], "estimated_mass_kg": [8.3e17],
            "estimated_mass_sigma_kg": [2.75e17]}
    mp3c = {"designation": ["2006 CH69"], "diameter_km": [50.0],
            "estimated_mass_kg": [8.3e17], "estimated_mass_sigma_kg": [2e17]}
    merged = _merge(jpl, ssod, None, mp3c).loc["2006 CH69"]
    assert pd.isna(merged["diameter_km"])
    assert merged["diameter_screened_out"] == "MP3C"
    assert merged["estimated_mass_kg"] == 8.3e17

    row = _build(jpl, ssod, None, mp3c).loc["2006 CH69"]
    assert row["diameter_source"] == "derived_mass"
    assert row["mass_measured"]
    rho = bulk_density_gcm3(row["estimated_mass_kg"], row["diameter_km"])
    assert rho == pytest.approx(row["density_gcm3"])
    lo, hi = DENSITY_LIMITS_GCM3[ac.TAXONOMY_COMPOSITION[row["spectral_type"]]["group"]]
    assert lo <= rho <= hi


def test_a_measured_mass_refutes_an_h_derived_diameter():
    """2003 QY90: 5.2e17 kg on an H-derived 257 km is 0.06 g/cm3."""
    jpl = {"designation": ["2003 QY90"], "semi_major_axis_au": [43.7],
           "absolute_magnitude_h": [6.47]}
    ssod = {"designation": ["2003 QY90"], "estimated_mass_kg": [5.17e17],
            "estimated_mass_sigma_kg": [1.8e16]}
    row = _build(jpl, ssod).loc["2003 QY90"]
    assert row["diameter_source"] == "derived_mass"
    assert row["derived_diameter_is_estimate"]
    assert row["estimated_mass_kg"] == 5.17e17 and row["mass_measured"]
    assert row["density_gcm3"] == pytest.approx(
        ac.TAXONOMY_COMPOSITION["D"]["density_est_gcm3"])
    assert not row["density_measured"], "a density from an assumed one is not measured"


# ---------------------------------------------------------------------------
# the row agrees with itself
# ---------------------------------------------------------------------------
def test_mass_is_density_times_volume_in_every_row():
    jpl = {"designation": ["1", "2", "3"], "semi_major_axis_au": [2.77, 2.77, 2.5],
           "absolute_magnitude_h": [3.34, 4.12, 15.0],
           "diameter_km": [939.4, 513.0, np.nan],
           "estimated_mass_kg": [9.3835e20, np.nan, np.nan],
           "spectral_type": ["C", "B", np.nan]}
    ssod = {"designation": ["2"], "diameter_km": [513.0],
            "estimated_mass_kg": [2.04e20], "estimated_mass_sigma_kg": [3e18],
            "density_gcm3": [2.90]}
    out = _build(jpl, ssod)
    implied = bulk_density_gcm3(out["estimated_mass_kg"], out["diameter_km"])
    assert np.allclose(implied, out["density_gcm3"], rtol=1e-12)
    assert out.loc["1", "density_measured"] and out.loc["1", "mass_measured"]
    assert not out.loc["3", "density_measured"]


def test_a_source_density_impossible_for_its_class_is_dropped():
    """A C-type at 6.25 g/cm3 is denser than any carbonaceous rock."""
    jpl = {"designation": ["799"], "semi_major_axis_au": [2.54],
           "diameter_km": [47.185], "spectral_type": ["C"]}
    ssod = {"designation": ["799"], "density_gcm3": [6.25]}
    row = _build(jpl, ssod).loc["799"]
    assert row["density_gcm3"] == ac.TAXONOMY_COMPOSITION["C"]["density_est_gcm3"]
    assert not row["density_measured"]


# ---------------------------------------------------------------------------
# albedo, spin, and the outer Solar System
# ---------------------------------------------------------------------------
def test_an_albedo_at_its_fit_ceiling_is_refused():
    jpl = {"designation": ["4440"], "semi_major_axis_au": [1.9],
           "diameter_km": [2.093], "albedo": [1.0]}
    ssod = {"designation": ["4440"], "albedo": [0.61]}
    row = _merge(jpl, ssod).loc["4440"]
    assert row["albedo"] == 0.61 and row["albedo_provider"] == "SsODNet"
    assert row["albedo_screened_out"] == "JPL SBDB"


def test_a_large_body_cannot_spin_faster_than_breakup():
    """2530 Shipka: JPL 1.02 h on a 12.4 km C-type; SsODNet 180.2 h."""
    jpl = {"designation": ["2530", "small"], "semi_major_axis_au": [2.5, 2.2],
           "diameter_km": [12.403, 0.3], "rotation_period_h": [1.02, 0.1],
           "spectral_type": ["C", "S"]}
    ssod = {"designation": ["2530"], "rotation_period_h": [180.2]}
    out = _merge(jpl, ssod)
    assert out.loc["2530", "rotation_period_h"] == 180.2
    assert out.loc["2530", "rotation_period_screened_out"] == "JPL SBDB"
    assert out.loc["small", "rotation_period_h"] == 0.1, \
        "a 300 m body can be held by cohesion; it is not judged"


def test_h_alone_bounds_the_size_for_the_spin_limit():
    """578993: no diameter, H 3.5, 0.5 h.  At albedo 1 it is still 265 km."""
    jpl = {"designation": ["578993"], "semi_major_axis_au": [44.0],
           "absolute_magnitude_h": [3.5], "rotation_period_h": [0.5]}
    out = _merge(jpl)
    assert pd.isna(out.loc["578993", "rotation_period_h"])


def test_icy_bodies_are_not_typed_as_basalt():
    """Makemake (p_V 0.81) was V: 2.9 g/cm3 of basaltic crust."""
    jpl = {"designation": ["136472", "4"], "semi_major_axis_au": [45.4, 2.36],
           "absolute_magnitude_h": [-0.25, 3.25], "diameter_km": [1430.0, 522.8],
           "albedo": [0.81, 0.42]}
    out = _build(jpl)
    assert out.loc["136472", "spectral_type"] == "D"
    assert out.loc["136472", "spectral_type_source"] == "orbit"
    assert out.loc["4", "spectral_type"] == "S", \
        "a bright main-belt body is stony by inference: V was right 22% of the time"


def test_a_source_class_beyond_jupiter_is_kept():
    jpl = {"designation": ["136199"], "semi_major_axis_au": [67.9],
           "diameter_km": [2400.0], "spectral_type": ["Bk"]}
    out = _build(jpl)
    assert out.loc["136199", "spectral_type"] == "Bk"
    assert out.loc["136199", "spectral_type_source"] == "source"


# ---------------------------------------------------------------------------
# the release gate
# ---------------------------------------------------------------------------
def test_the_gate_refuses_every_kind_of_impossible_row():
    df = pd.DataFrame({
        "designation": ["1686", "1", "4440", "2530", "ok"],
        "diameter_km": [29.661, 939.4, 2.0, 12.4, 10.0],
        "estimated_mass_kg": [6.76e18, 9.38e20, 1e13, 1.5e15, 1e15],
        "density_gcm3": [1.4, 1.0, 2.4, 1.5,
                         float(bulk_density_gcm3(1e15, 10.0))],
        "albedo": [0.09, 0.09, 1.0, 0.05, 0.1],
        "absolute_magnitude_h": [11.2, 3.3, 13.9, 11.0, 12.0],
        "rotation_period_h": [5.0, 9.1, 3.0, 1.02, 5.0],
    })
    got = " | ".join(physical_problems(df))
    assert "outside 0.25-8" in got and "1686" in got
    assert "not density_gcm3 x volume" in got
    assert "albedo of 1" in got and "4440" in got
    assert "breakup" in got and "2530" in got
    assert "'ok'" not in got


def test_the_gate_is_part_of_check_release():
    df = pd.DataFrame({"designation": ["1686"], "diameter_km": [29.661],
                       "estimated_mass_kg": [6.76e18]})
    assert any("bulk density" in p for p in check_release(df, floors={
        "rows": 0, "measured_diameters": 0, "JPL SBDB": 0, "SsODNet": 0,
        "NEOWISE": 0, "MP3C": 0}))


def test_pairing_and_dropping_need_no_diameter_sigma():
    """No source here carries a diameter sigma; the column never exists."""
    jpl = {"designation": ["15", "2006 CH69"], "semi_major_axis_au": [2.64, 44.0],
           "absolute_magnitude_h": [5.43, 6.58], "diameter_km": [231.689, np.nan],
           "spectral_type": ["S", np.nan]}
    ssod = {"designation": ["15", "2006 CH69"], "diameter_km": [271.3, np.nan],
            "estimated_mass_kg": [3.197e19, 8.3e17]}
    mp3c = {"designation": ["2006 CH69"], "diameter_km": [50.0],
            "estimated_mass_kg": [8.3e17]}
    out = _merge(jpl, ssod, None, mp3c)
    assert out.loc["15", "diameter_km"] == 271.3
    assert pd.isna(out.loc["2006 CH69", "diameter_km"])


def test_a_subclass_in_capitals_sizes_off_its_own_median():
    """"SQ" is Sq (p_V 0.276), not S (0.2439): 663 bodies in 2026-09-23."""
    from asteroid_catalog.derive import ALBEDO_BY_SPECTRAL_TYPE
    df = pd.DataFrame({"designation": ["a", "b"], "absolute_magnitude_h": [15.0, 15.0],
                       "semi_major_axis_au": [2.3, 2.3], "spectral_type": ["SQ", "Sq"]})
    out = ac.derive_missing_diameters(df, ac.CONFIG)
    assert (out["albedo_assumed_for_diameter"] == ALBEDO_BY_SPECTRAL_TYPE["Sq"]).all()


def test_class_albedo_table_covers_the_subclasses_sources_use():
    """Ds sized as D (0.051) was 58% too large; its own median is 0.1265."""
    from asteroid_catalog.derive import ALBEDO_BY_SPECTRAL_TYPE
    for cls in ("Ds", "Dl", "Ls", "Kl", "E", "Z"):
        assert cls in ALBEDO_BY_SPECTRAL_TYPE
    assert all(0 < v < 1 for v in ALBEDO_BY_SPECTRAL_TYPE.values())
