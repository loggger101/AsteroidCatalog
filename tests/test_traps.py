# -*- coding: utf-8 -*-
"""The documented traps, executed.

Every test here is a rule that was written in prose first and cost somebody a
release before anything ran it.  A prose invariant is a comment nobody applied.

These were `verify_stage1.py` checks 1 to 5 in economicspace, ported when the
builder moved.  They need no catalog and no network, which is what keeps them
running: a check that needs 862 MB of input is a check CI skips.
"""

import contextlib
import io

import pandas as pd
import pytest

import asteroid_catalog as ac
from asteroid_catalog.taxonomy import _by_distinct

FRACTIONS = ("metal_fraction", "silicate_fraction", "carbon_fraction",
             "ice_fraction")


# ---------------------------------------------------------------------------
# 1. designations
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("raw,want", [
    ("1", "1"), ("00001", "1"), ("1 Ceres", "1"), ("433 Eros", "433"),
    ("(1) Ceres", "1"), ("2024 BX1", "2024 BX1"), ("1999 KW4", "1999 KW4"),
    ("Ceres", "Ceres"), ("", None), ("None", None),
])
def test_canonical_designation(raw, want):
    """A naive `^\\d+` yields "2024" for "2024 BX1".

    That is not null, not obviously wrong, and cross-matches an unrelated
    numbered body.  The empty and "None" cases matter as much as the
    interesting ones: they must land on a MISSING value rather than on the
    string "None", which joins to nothing and looks like a source that
    returned no rows.
    """
    got = ac._extract_canonical_designation(pd.Series([raw]))
    got = None if pd.isna(got.iloc[0]) else got.iloc[0]
    assert got == want


def test_float_typed_identifier_does_not_render_as_3_point_0():
    """The same trap one column along, and it cost NEOWISE four releases.

    A numeric identifier pandas has typed float64 renders as "3.0", which is
    not null, not obviously wrong, and joins nothing.  The source reported
    183,408 rows fetched and contributed exactly zero.
    """
    got = ac._extract_canonical_designation(
        pd.Series([1.0, 433.0, 69260.0], dtype="float64"))
    for g in got:
        assert not (isinstance(g, str) and g.endswith(".0")), \
            "float64 id rendered as %r (the NEOWISE merge-key trap)" % g


# ---------------------------------------------------------------------------
# 2. taxonomy
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", sorted(ac.TAXONOMY_COMPOSITION))
def test_composition_leaves_a_residual(name):
    """Every real class sums to strictly less than 1, so there IS a residual.

    THE PROPERTY IS ASSERTED, NOT THE INTERVAL, and the difference is the
    whole point.  Three documents quoted "0.76-0.96" forward for releases; the
    table has always said 0.73, because `Cgh` sums to 0.73 while `C` itself is
    exactly 0.76 and somebody generalised the C row to the complex.  The
    interval was wrong at birth and nothing executed it.

    Asserting the property is also what stops this going red the day somebody
    re-measures a taxonomy row, which is a legitimate act.
    """
    entry = ac.TAXONOMY_COMPOSITION[name]
    if name == "Unknown":
        pytest.skip("Unknown is the sentinel; see its own test")
    s = sum(float(entry.get(f) or 0.0) for f in FRACTIONS)
    assert 0.0 < s < 1.0, (
        "%s sums to %.4f, outside (0, 1): the residual is what a consumer "
        "floors at a bulk-silicate value" % (name, s))
    for f in FRACTIONS:
        v = entry.get(f)
        assert v is None or 0.0 <= float(v) <= 1.0


def test_unknown_is_the_all_none_sentinel():
    """`Unknown` leaves every fraction None, so the residual is the whole body.

    That is the honest answer for a body whose taxonomy nothing knows, and it
    is a deliberate exception rather than missing data.
    """
    entry = ac.TAXONOMY_COMPOSITION["Unknown"]
    assert all(entry.get(f) is None for f in FRACTIONS)


def test_m_type_is_not_a_bare_metal_core():
    """No M-type has ever been measured near iron-meteorite density.

    Psyche is ~3.8-3.9 g/cm3.  The 0.80 / 5.30 pair is what this table must
    never be "restored" to.
    """
    m = ac.TAXONOMY_COMPOSITION["M"]
    assert float(m["metal_fraction"]) < 0.80
    assert float(m["density_est_gcm3"]) < 5.0


def test_every_class_carries_the_schema():
    keys = {"group", "composition", "minerals", "density_est_gcm3"}
    for name, entry in ac.TAXONOMY_COMPOSITION.items():
        assert keys <= set(entry), "%s is missing %s" % (name, keys - set(entry))


# ---------------------------------------------------------------------------
# 3. PGM enrichment
# ---------------------------------------------------------------------------
def test_pgm_falls_back_by_first_character_then_to_one():
    """An unlisted sub-type inherits its parent class, not chondritic.

    And the default is 1.0 rather than 0.0, so an unknown body is valued as
    ordinary rather than as worthless.
    """
    parent = ac.PGM_ENRICHMENT_BY_TYPE["M"]
    assert ac.pgm_enrichment_for_type("M") == parent
    assert ac.pgm_enrichment_for_type("Mq") == parent
    assert ac.pgm_enrichment_for_type("Zz") == 1.0
    assert ac.pgm_enrichment_for_type(None) == 1.0
    assert ac.pgm_enrichment_for_type("") == 1.0


def test_pgm_direction_matches_differentiation_history():
    """Core fragments are enriched, basaltic crust is depleted."""
    assert ac.pgm_enrichment_for_type("M") > 1.0     # core fragment
    assert ac.pgm_enrichment_for_type("V") < 1.0     # Vesta / HED crust
    assert ac.pgm_enrichment_for_type("C") == 1.0    # never differentiated


# ---------------------------------------------------------------------------
# 4. _by_distinct
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("data", [
    ["C", "M", None, "V", "Cgh", float("nan"), "M"],
    [None, None],
    ["Zz", "Zz", "C"],
    [],
])
def test_by_distinct_equals_a_per_row_apply(data):
    """The distinct-value optimisation still equals the `.apply` it replaced.

    It was argued from "all 12 derived columns identical" on one catalog,
    which is a measurement of one run rather than a property.

    THE NaN CASES ARE THE POINT.  Two NaNs are not equal, so this is exactly
    where a missing value falls through a lookup that `nan != nan` breaks.

    AND THE FIXTURE'S LOOKUP MUST BE TOTAL, OR THIS TEST CANNOT FAIL.  Written
    as `TAXONOMY_COMPOSITION.get(t, {}).get("group")` it returns None for an
    unknown key, so an implementation that DROPS NaN keys and one that handles
    them agree on NaN -- both give a missing value -- and the path this test
    exists for goes invisible.  The real chain falls back to `Unknown`, so the
    fixture does too, and a dropped key then shows as a missing value where a
    real one is owed.
    """
    def fn(t):
        return (ac.TAXONOMY_COMPOSITION.get(t)
                or ac.TAXONOMY_COMPOSITION["Unknown"]).get("group")

    s = pd.Series(data, dtype="object")
    fast = list(_by_distinct(s, fn).fillna("<NA>"))
    slow = list(s.apply(fn).fillna("<NA>")) if len(s) else []
    assert fast == slow


# ---------------------------------------------------------------------------
# 5. lookup
# ---------------------------------------------------------------------------
def _quiet(frame, query):
    """`lookup_asteroid` with its report suppressed.

    It prints on a miss, which is right for somebody at a prompt and is noise
    in a test whose expected result on one probe IS a miss.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return ac.lookup_asteroid(frame, query)


def test_lookup_survives_regex_metacharacters():
    """`str.contains` without `regex=False` is the trap.

    "(1) Ceres" made an unbalanced bracket raise `re.PatternError`, and made
    the bracketed form match the unbracketed one.
    """
    meta = pd.DataFrame({"designation": ["1", "2024 BX1"],
                         "name": ["(1) Ceres", "z"]})
    assert len(_quiet(meta, "(1) Ceres")) == 1
    assert len(_quiet(meta, "1 Ceres")) == 0, \
        "'1 Ceres' cross-matched: the bracketed form is not a regex"


def test_lookup_handles_an_int64_designation_column():
    """A numbered asteroid's designation looks like an integer.

    A frame built from a slice where every row happens to be numbered comes
    back int64, and a string comparison then matches nothing: "expected one
    row, found 0" about a body that is right there in the file.
    """
    ints = pd.DataFrame({"designation": pd.Series([1, 433, 69260], dtype="int64"),
                         "name": ["Ceres", "Eros", "x"]})
    assert len(_quiet(ints, "433")) == 1
