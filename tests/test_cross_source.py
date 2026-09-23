# -*- coding: utf-8 -*-
"""One body, one row, every source's knowledge in it.

The defects these guard were all measured against the live sources on
2026-09-22, and every one of them was silent: the build succeeded, the counts
looked plausible, and the damage was visible only by joining the output back
to the inputs.

  * NEOWISE spells an uncycled provisional designation "1996 GQ0"; nobody else
    does, so those bodies joined nothing and were dropped.
  * A source that still carries a body under its provisional designation
    missed the number JPL has since given it: 10,627 NEOWISE bodies lost.
  * An old ssoBFT carried bodies under a SECOND provisional designation, and
    because SsODNet rows bring their own orbit they survived validation as
    duplicates of JPL bodies: 182 in the 2026-08-11 build.
  * Duplicates were culled, not combined; and a sigma could be filled from a
    different source than the value beside it.
  * Orbital periods were days in a column named years, and SsODNet's
    provisional designations filled 1.5 M empty `name` cells.
"""

import numpy as np
import pandas as pd
import pytest

import asteroid_catalog as ac
from asteroid_catalog.designations import (
    _looks_like_designation, _provisional_from_full_name, _unpack_mpc_number,
)
from asteroid_catalog.identity import build_alias_map, resolve_designations
from asteroid_catalog.jpl import _jpl_derived_columns
from asteroid_catalog.merge import MEASURED_FIELDS
from asteroid_catalog.neowise import combine_neowise_fits


def one(s):
    v = ac._extract_canonical_designation(pd.Series([s])).iloc[0]
    return None if pd.isna(v) else v


# ---------------------------------------------------------------------------
# designation shapes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,want", [
    ("1996 GQ0", "1996 GQ"),        # NEOWISE's uncycled form
    ("2024 BX10", "2024 BX10"),     # a real cycle count ending in 0 is kept
    ("1996 GQ", "1996 GQ"),
])
def test_neowise_zero_cycle_count(raw, want):
    assert one(raw) == want


def test_nullable_string_na_is_not_the_string_na():
    """`.astype(str)` renders pandas' nullable-string NA as "<NA>"."""
    got = ac._extract_canonical_designation(pd.Series([pd.NA, "433"], dtype="string"))
    assert pd.isna(got.iloc[0]) and got.iloc[1] == "433"


@pytest.mark.parametrize("packed,want", [
    ("00001", "1"), ("00433", "433"), ("A1955", "101955"),
    ("a0001", "360001"), ("~0000", "620000"), ("~000z", "620061"),
    ("Ceres", None), ("K05C33Q", None), (None, None),
])
def test_mpc_packed_numbers(packed, want):
    got = _unpack_mpc_number(pd.Series([packed], dtype="object")).iloc[0]
    assert (None if pd.isna(got) else got) == want


def test_provisional_from_jpl_full_name():
    got = _provisional_from_full_name(pd.Series(
        ["     1 Ceres (A801 AA)", "876218 (2007 TE344)", "(2019 JD121)", None]))
    assert got.tolist()[:3] == ["A801 AA", "2007 TE344", "2019 JD121"]
    assert pd.isna(got.iloc[3])


@pytest.mark.parametrize("value,is_des", [
    ("2006 WZ117", True), ("1996 GQ", True), ("2040 P-L", True),
    ("3138 T-1", True), ("Ceres", False), ("Bennu", False), ("'Ailo'ahi", False),
])
def test_a_designation_is_not_a_name(value, is_des):
    """ssoBFT puts the provisional designation in `name` for unnamed bodies."""
    assert bool(_looks_like_designation(pd.Series([value])).iloc[0]) is is_des


# ---------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------
BACKBONE = pd.DataFrame({
    "designation": ["1", "433", "2015 KN450"],
    "name": ["Ceres", "Eros", None],
    "provisional_designation": ["A801 AA", "A898 PA", "2015 KN450"],
    "semi_major_axis_au": [2.77, 1.46, 2.26],
})


def test_offline_aliases_reach_the_number():
    amap = build_alias_map(BACKBONE)
    got = resolve_designations(
        pd.Series(["A898 PA", "Ceres", "433", "2015 KN450", "1999 ZZ9"]), amap)
    assert got.tolist() == ["433", "1", "433", "2015 KN450", "1999 ZZ9"], \
        "an unresolvable designation must pass through unchanged, not vanish"


def test_mpc_links_place_secondary_designations():
    """The MPC names the body by number or principal designation; either may
    itself be a backbone alias, so its answer goes through the map again."""
    links = {"2001 FF217": "2015 KN450",     # secondary -> principal
             "1898 PA": "433",               # old designation -> number
             "2009 UH126": "583031"}         # a body the backbone lacks
    got = resolve_designations(
        pd.Series(["2001 FF217", "1898 PA", "433", "2009 UH126", "1999 ZZ9"]),
        build_alias_map(BACKBONE), links)
    assert got.tolist() == ["2015 KN450", "433", "433", "583031", "1999 ZZ9"]


def test_mpc_links_are_parsed_from_the_real_layout(tmp_path):
    """Layout copied from mpcorb_extended.json.gz on 2026-09-22."""
    import gzip
    from asteroid_catalog.identity import _parse_mpc_links
    text = ('[\n{\n"H": 3.34,\n"Number": "(1)",\n"Name": "Ceres",\n'
            '"Principal_desig": "A801 AA",\n"Other_desigs": [\n"A899 OF",\n'
            '"1943 XB"\n],\n"a": 2.7655526\n},\n{\n"H": 19.1,\n'
            '"Principal_desig": "2015 KN450",\n"Other_desigs": [\n'
            '"2001 FF217"\n],\n"a": 2.26\n}\n]\n')
    p = tmp_path / "m.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write(text)
    got = _parse_mpc_links(str(p))
    assert sorted(zip(got["alias"], got["to"])) == sorted([
        ("A801 AA", "1"), ("Ceres", "1"), ("A899 OF", "1"), ("1943 XB", "1"),
        ("2015 KN450", "2015 KN450"), ("2001 FF217", "2015 KN450")])


def test_an_alias_naming_two_bodies_is_left_unresolved():
    bb = pd.DataFrame({"designation": ["10", "20"], "name": ["Twin", "Twin"]})
    got = resolve_designations(pd.Series(["Twin"]), build_alias_map(bb))
    assert got.tolist() == ["Twin"], "a guessed identity is worse than none"


# ---------------------------------------------------------------------------
# the merge
# ---------------------------------------------------------------------------
def test_supplement_under_an_old_designation_joins_not_duplicates():
    supp = pd.DataFrame({"designation": ["A898 PA", "2001 FF217"],
                         "albedo": [0.25, 0.07],
                         "semi_major_axis_au": [1.46, 2.26],
                         "source_x": [True, True]})
    out = ac.merge_sources({"JPL SBDB": BACKBONE, "X": supp},
                           links={"2001 FF217": "2015 KN450"})
    assert len(out) == 3 and out["designation"].is_unique
    eros = out.set_index("designation").loc["433"]
    assert eros["albedo"] == 0.25 and eros["n_sources"] == 2
    assert eros["sources"] == "JPL SBDB;X"
    assert out.set_index("designation").loc["1", "n_sources"] == 1


def test_duplicates_are_combined_not_culled():
    df = pd.DataFrame({"designation": ["5", "5", "6"],
                       "diameter_km": [10.0, None, 3.0],
                       "albedo": [None, 0.2, 0.1],
                       "family": [None, "Vesta", None]})
    out = ac.deduplicate_catalog(df).set_index("designation")
    assert len(out) == 2
    assert out.loc["5", "diameter_km"] == 10.0
    assert out.loc["5", "albedo"] == 0.2, "the second row's data was thrown away"
    assert out.loc["5", "family"] == "Vesta"


def test_measured_value_keeps_its_own_sigma():
    """A value from one catalog must not sit beside another's error bar."""
    bb = pd.DataFrame({"designation": ["1", "2"], "diameter_km": [100.0, None],
                       "semi_major_axis_au": [2.5, 2.6]})
    supp = pd.DataFrame({"designation": ["1", "2"], "diameter_km": [108.0, 50.0],
                         "diameter_sigma_km": [4.0, 2.0]})
    out = ac.merge_sources({"JPL SBDB": bb, "S": supp}).set_index("designation")
    assert out.loc["1", "diameter_km"] == 100.0
    assert pd.isna(out.loc["1", "diameter_sigma_km"]), \
        "JPL's diameter was given S's sigma"
    assert out.loc["1", "diameter_provider"] == "JPL SBDB"
    assert out.loc["2", "diameter_km"] == 50.0
    assert out.loc["2", "diameter_sigma_km"] == 2.0
    assert out.loc["2", "diameter_provider"] == "S"


def test_agreement_columns():
    bb = pd.DataFrame({"designation": ["1", "2", "3"],
                       "diameter_km": [100.0, 100.0, 100.0],
                       "semi_major_axis_au": [2.5, 2.6, 2.7]})
    supp = pd.DataFrame({"designation": ["1", "2"],
                         "diameter_km": [105.0, 150.0]})
    out = ac.merge_sources({"JPL SBDB": bb, "S": supp}).set_index("designation")
    assert out.loc["1", "diameter_n_sources"] == 2
    assert out.loc["1", "diameter_spread"] == pytest.approx(0.05)
    assert out.loc["1", "diameter_sources_agree"] == True       # noqa: E712
    assert out.loc["2", "diameter_sources_agree"] == False      # noqa: E712
    assert out.loc["3", "diameter_n_sources"] == 1
    assert pd.isna(out.loc["3", "diameter_sources_agree"]), \
        "one source can neither agree nor disagree"


def test_h_spread_is_a_difference_in_magnitudes():
    bb = pd.DataFrame({"designation": ["1"], "absolute_magnitude_h": [15.0],
                       "semi_major_axis_au": [2.5]})
    supp = pd.DataFrame({"designation": ["1"], "absolute_magnitude_h": [15.2]})
    out = ac.merge_sources({"JPL SBDB": bb, "S": supp})
    assert out.loc[0, "h_spread"] == pytest.approx(0.2)
    assert out.loc[0, "h_sources_agree"] == True                # noqa: E712
    assert MEASURED_FIELDS["absolute_magnitude_h"]["kind"] == "diff"


# ---------------------------------------------------------------------------
# per-source fixes
# ---------------------------------------------------------------------------
def test_neowise_repeat_fits_are_weighted_not_dropped():
    df = pd.DataFrame({
        "designation": ["3", "3", "4"],
        "diameter_km": [246.6, 337.9, 50.0],
        "diameter_sigma_km": [10.6, 87.8, 1.0],
        "albedo": [0.214, 0.145, 0.1],
        "albedo_sigma": [0.026, 0.055, None],
        "neowise_fit_code": ["DV-I", "DV--", "DV--"],
        "neowise_reference": ["Mas12", "Nug15", "Mas11"],
    })
    out = combine_neowise_fits(df).set_index("designation")
    assert len(out) == 2
    juno = out.loc["3"]
    w = np.array([1 / 10.6 ** 2, 1 / 87.8 ** 2])
    assert juno["diameter_km"] == pytest.approx((w * [246.6, 337.9]).sum() / w.sum())
    assert juno["diameter_sigma_km"] >= (1 / w.sum()) ** 0.5
    assert juno["neowise_n_fits"] == 2
    assert juno["neowise_reference"] == "Mas12|Nug15"
    assert out.loc["4", "diameter_km"] == 50.0 and out.loc["4", "neowise_n_fits"] == 1


def test_neowise_body_under_two_designations_is_averaged_in_the_merge():
    """Two NEOWISE designations of one body are two sets of fits of it."""
    neo = combine_neowise_fits(pd.DataFrame({
        "designation": ["2010 AE84", "2010 NN46", "2010 NN46"],
        "diameter_km": [3.878, 2.887, 2.9], "diameter_sigma_km": [0.113, 0.179, 0.2],
        "neowise_reference": ["Mas11", "Mas12", "Nug15"]}))
    bb = pd.DataFrame({"designation": ["2010 AE84"], "semi_major_axis_au": [2.5]})
    out = ac.merge_sources({"JPL SBDB": bb, "NEOWISE": neo},
                           links={"2010 NN46": "2010 AE84"})
    assert len(out) == 1
    row = out.iloc[0]
    assert row["neowise_n_fits"] == 3
    assert 2.9 < row["diameter_km"] < 3.878, "one designation's value just won"
    assert row["neowise_reference"].split("|") == ["Mas11", "Mas12", "Nug15"]


def test_neowise_assumed_values_are_not_measurements():
    """fit_code slot '-' (or 'F') means the parameter was assumed for the fit."""
    from asteroid_catalog.neowise import mask_unfitted_neowise
    df = pd.DataFrame({
        "neowise_fit_code": ["DV--", "DVB-", "DVF-", "DVBI"],
        "diameter_km": [1.0, 2.0, 3.0, 4.0],
        "diameter_sigma_km": [0.1, 0.0, 0.3, 0.4],
        "albedo": [0.1] * 4, "albedo_sigma": [0.01] * 4,
        "neowise_beaming_param": [1.0, 1.3, 0.0, 0.9],
        "neowise_beaming_param_sigma": [0.2, 0.1, 0.0, 0.1],
        "albedo_ir": [-0.999, 0.2, 0.2, 0.3],
        "albedo_ir_sigma": [-0.999, 0.05, 0.05, 0.05],
    })
    out = mask_unfitted_neowise(df)
    assert out["neowise_beaming_param"].isna().tolist() == [True, False, True, False]
    assert out["albedo_ir"].isna().tolist() == [True, True, True, False]
    assert pd.isna(out.loc[1, "diameter_sigma_km"]), "a zero sigma is no sigma"
    assert out["diameter_km"].notna().all()


def test_mp3c_placeholders_are_missing():
    from asteroid_catalog.mp3c import _mask_mp3c_sentinels
    df = pd.DataFrame({"absolute_magnitude_h": [0.0, 99.99, 17.2, -1.2],
                       "diameter_km": [0.0, 1.0, 2.0, 2300.0],
                       "diameter_sigma_km": [0.1, 0.1, 0.1, 10.0]})
    out = _mask_mp3c_sentinels(df)
    assert out["absolute_magnitude_h"].isna().tolist() == [True, True, False, False]
    assert out["diameter_km"].isna().tolist() == [True, False, False, False]
    assert pd.isna(out.loc[0, "diameter_sigma_km"])


def test_jpl_period_is_years_and_gm_is_a_mass():
    df = pd.DataFrame({"orbital_period_yr": [1679.853119758983],
                       "full_name": ["     1 Ceres (A801 AA)"],
                       "GM": ["62.6284"]})
    out = _jpl_derived_columns(df)
    assert out.loc[0, "orbital_period_yr"] == pytest.approx(4.599, abs=1e-3), \
        "SBDB `per` is days"
    assert out.loc[0, "estimated_mass_kg"] == pytest.approx(9.38e20, rel=1e-3)
    assert out.loc[0, "provisional_designation"] == "A801 AA"
    assert "full_name" not in out.columns and "GM" not in out.columns