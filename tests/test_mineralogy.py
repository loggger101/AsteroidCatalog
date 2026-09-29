# -*- coding: utf-8 -*-
"""The mineral-phase tables (data contract 1.7.0) hold to the coarse fractions.

`comp_phases` is DETAIL, not a second composition: every phase belongs to one
of the four coarse groups or to the residual, the phases of a group add back to
the row's coarse fraction, and the accessories fit inside what the four leave.
If any of that fails, a consumer summing phases gets a different body from one
reading the coarse columns, which is two answers in one row.
"""

import json

import pandas as pd
import pytest

import asteroid_catalog as ac
from asteroid_catalog import mineralogy as mi
from asteroid_catalog.taxonomy import X_SPLIT_CLASSES, X_SPLIT_COUNTS, X_SPLIT_ROWS

T = ac.TAXONOMY_COMPOSITION
CLASSES = [c for c in T if c != "Unknown"]


@pytest.mark.parametrize("cls", CLASSES)
def test_every_class_has_phases_and_only_known_ones(cls):
    fracs = mi.phase_fractions(cls)
    assert fracs, "%s has no phases" % cls
    unknown = set(fracs) - set(mi.PHASE_GROUP)
    assert not unknown, "%s names phases outside PHASE_GROUP: %s" % (cls, unknown)


def test_unknown_has_none():
    """Unknown has no coarse fractions, so it can have no phases either."""
    assert mi.phase_fractions("Unknown") is None
    assert mi.phases_json("Unknown") is None


@pytest.mark.parametrize("cls", CLASSES)
def test_typed_shares_sum_to_one_per_group(cls):
    for group, shares in mi.PHASE_SHARES[cls].items():
        assert sum(shares.values()) == pytest.approx(1.0, abs=1e-12), (cls, group)
        assert all(mi.PHASE_GROUP[p] == group for p in shares), (cls, group)


@pytest.mark.parametrize("cls", CLASSES)
def test_every_nonzero_group_is_divided(cls):
    """A coarse fraction with no shares would vanish from `comp_phases`."""
    for group, field in mi.GROUP_FIELDS.items():
        if T[cls].get(field):
            assert group in mi.PHASE_SHARES[cls], (cls, group)


@pytest.mark.parametrize("cls", CLASSES)
def test_groups_add_back_to_the_coarse_fractions(cls):
    fracs = mi.phase_fractions(cls)
    for group, field in mi.GROUP_FIELDS.items():
        got = sum(f for p, f in fracs.items() if mi.PHASE_GROUP[p] == group)
        assert got == pytest.approx(T[cls].get(field) or 0.0, abs=1e-12), (cls, group)


@pytest.mark.parametrize("cls", CLASSES)
def test_accessories_fit_inside_the_residual(cls):
    residual = 1.0 - sum(T[cls].get(f) or 0.0 for f in mi.GROUP_FIELDS.values())
    acc = sum(f for p, f in mi.phase_fractions(cls).items()
              if mi.PHASE_GROUP[p] == mi.ACCESSORY)
    assert 0.0 <= acc <= residual + 1e-12, (cls, acc, residual)


@pytest.mark.parametrize("row", X_SPLIT_ROWS)
def test_x_rows_are_the_mixture_of_p_m_and_e(row):
    """Recomputed here rather than trusted, as test_traps does the coarse ones."""
    n = dict(zip(X_SPLIT_CLASSES, X_SPLIT_COUNTS[row]))
    mass = {c: n[c] * T[c]["density_est_gcm3"] for c in n}
    total = sum(mass.values())
    mixed = {}
    for c, m in mass.items():
        for p, f in mi.phase_fractions(c).items():
            mixed[p] = mixed.get(p, 0.0) + m * f / total
    got = mi.phase_fractions(row)
    for p, f in mixed.items():
        if mi.PHASE_GROUP[p] == mi.ACCESSORY:
            assert got[p] == pytest.approx(f, abs=1e-12), (row, p)
    # Within a group, the mixture's SHARES survive the rescale to the row's own
    # coarse fraction.
    for group in mi.GROUP_FIELDS:
        want = {p: f for p, f in mixed.items() if mi.PHASE_GROUP[p] == group}
        if not want:
            continue
        s_want = sum(want.values())
        s_got = sum(got[p] for p in want)
        for p in want:
            assert got[p] / s_got == pytest.approx(want[p] / s_want, abs=1e-12)


def test_json_round_trips_to_the_same_doubles():
    for cls in CLASSES:
        assert json.loads(mi.phases_json(cls)) == mi.phase_fractions(cls)


def test_json_order_is_fixed():
    """Byte-identical per class on every build: group order, then table order."""
    order = list(mi.PHASE_GROUP)
    groups = list(mi.GROUP_FIELDS) + [mi.ACCESSORY]
    for cls in CLASSES:
        keys = list(json.loads(mi.phases_json(cls)))
        rank = [(groups.index(mi.PHASE_GROUP[k]), order.index(k)) for k in keys]
        assert rank == sorted(rank), cls


def test_the_checks_can_fail(monkeypatch):
    """A share table that no longer sums to one must turn the suite red.

    Feeding the check a wrong answer, because a check nobody has seen fail is
    a check nobody has seen."""
    bad = {g: dict(s) for g, s in mi.PHASE_SHARES["S"].items()}
    bad["silicate"]["olivine"] += 0.1
    monkeypatch.setitem(mi.PHASE_SHARES, "S", bad)
    fracs = mi.phase_fractions("S")
    got = sum(f for p, f in fracs.items() if mi.PHASE_GROUP[p] == "silicate")
    assert got != pytest.approx(T["S"]["silicate_fraction"], abs=1e-12)


def test_enrich_writes_comp_phases_from_comp_class():
    """The column is read off the same row as every other comp_* column,
    including an X with an albedo, which takes P, M or E."""
    df = pd.DataFrame({
        "designation": ["a", "b", "c", "d"],
        "spectral_type": ["S", "X", "X", None],
        "albedo": [0.25, 0.05, float("nan"), float("nan")],
    })
    out = ac.enrich_composition(df)
    by = dict(zip(out["designation"], out["comp_phases"]))
    assert json.loads(by["a"]) == mi.phase_fractions("S")
    assert json.loads(by["b"]) == mi.phase_fractions("P")
    assert json.loads(by["c"]) == mi.phase_fractions("X")
    for d, cls in zip(out["designation"], out["comp_class"]):
        want = mi.phases_json(cls)
        assert (by[d] is None or pd.isna(by[d])) if want is None else by[d] == want
