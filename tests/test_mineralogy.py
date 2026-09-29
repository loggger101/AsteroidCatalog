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


# ─────────────────────────────────────────────────────────────────────────────
# Data contract 1.8.0: `comp_phases_detailed` refines `comp_phases`
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("cls", CLASSES)
def test_detailed_names_only_known_phases(cls):
    fracs = mi.detailed_fractions(cls)
    assert fracs, "%s has no detailed phases" % cls
    unknown = set(fracs) - set(mi.PHASE_GROUP)
    assert not unknown, (cls, unknown)


@pytest.mark.parametrize("cls", CLASSES)
def test_detailed_resolves_the_alloy_everywhere(cls):
    """"nickel-iron" stood for kamacite + taenite; the detailed column names them."""
    assert "nickel-iron" not in mi.detailed_fractions(cls), cls


@pytest.mark.parametrize("cls", CLASSES)
def test_detail_splits_sum_to_one_inside_the_parent_group(cls):
    for parent, split in mi.PHASE_DETAIL[cls].items():
        assert sum(split.values()) == pytest.approx(1.0, abs=1e-12), (cls, parent)
        for finer in split:
            assert mi.PHASE_GROUP[finer] == mi.PHASE_GROUP[parent], (cls, parent, finer)


@pytest.mark.parametrize("cls", CLASSES)
def test_every_coarse_phase_is_the_sum_of_its_detail(cls):
    """Each `comp_phases` entry adds back from its detailed phases."""
    coarse = mi.phase_fractions(cls)
    fine = mi.detailed_fractions(cls)
    split = mi.PHASE_DETAIL[cls]
    new = mi.DETAIL_ACCESSORIES.get(cls, {})
    got: dict = {}
    for parent, frac in coarse.items():
        for finer, share in split.get(parent, {parent: 1.0}).items():
            got[finer] = got.get(finer, 0.0) + frac * share
    for phase, frac in new.items():
        got[phase] = got.get(phase, 0.0) + frac
    assert set(got) == set(fine), cls
    for phase in fine:
        assert fine[phase] == pytest.approx(got[phase], abs=1e-15), (cls, phase)


@pytest.mark.parametrize("cls", CLASSES)
def test_detailed_groups_add_back_to_the_coarse_fractions(cls):
    fine = mi.detailed_fractions(cls)
    for group, field in mi.GROUP_FIELDS.items():
        got = sum(f for p, f in fine.items() if mi.PHASE_GROUP[p] == group)
        assert got == pytest.approx(T[cls].get(field) or 0.0, abs=1e-12), (cls, group)


@pytest.mark.parametrize("cls", CLASSES)
def test_detailed_accessories_fit_inside_the_residual(cls):
    residual = 1.0 - sum(T[cls].get(f) or 0.0 for f in mi.GROUP_FIELDS.values())
    acc = sum(f for p, f in mi.detailed_fractions(cls).items()
              if mi.PHASE_GROUP[p] == mi.ACCESSORY)
    assert 0.0 <= acc <= residual + 1e-12, (cls, acc, residual)


def test_new_accessories_are_new():
    """DETAIL_ACCESSORIES adds phases; refining an existing one is PHASE_DETAIL's job."""
    for cls, extra in mi.DETAIL_ACCESSORIES.items():
        clash = set(extra) & set(mi.phase_fractions(cls))
        assert not clash, (cls, clash)


@pytest.mark.parametrize("row", X_SPLIT_ROWS)
def test_x_detail_is_the_mixture_of_p_m_and_e(row):
    """Each parent of X divides as its members' metal/sulfide would, mixed by mass."""
    n = dict(zip(X_SPLIT_CLASSES, X_SPLIT_COUNTS[row]))
    mass = {c: n[c] * T[c]["density_est_gcm3"] for c in n}
    fine = {}
    parent_mass = {}
    for c, m in mass.items():
        for p, f in mi.phase_fractions(c).items():
            parent_mass[p] = parent_mass.get(p, 0.0) + m * f
            for q, s in mi.PHASE_DETAIL[c].get(p, {p: 1.0}).items():
                fine.setdefault(p, {})
                fine[p][q] = fine[p].get(q, 0.0) + m * f * s
    for p, split in mi.PHASE_DETAIL[row].items():
        for q, s in split.items():
            assert s == pytest.approx(fine[p][q] / parent_mass[p], abs=1e-12), (row, p, q)


def test_oc_metal_is_nickel_richer_than_iron_meteorite_metal():
    """The point of the split: LL-leaning chondrite metal carries more Ni.

    Checked through the shares at the consumer's nominal alloy Ni (6.5 / 30 /
    50 wt%), so a split that lost its taenite would turn this red."""
    ni = {"kamacite": 0.065, "taenite": 0.30, "tetrataenite": 0.50, "cohenite": 0.03}
    def metal_ni(cls):
        s = mi.PHASE_DETAIL[cls]["nickel-iron"]
        return sum(share * ni[p] for p, share in s.items())
    assert metal_ni("S") > 0.15 > 0.08 < metal_ni("M") < 0.11


def test_detailed_json_round_trips_and_is_ordered():
    order = list(mi.PHASE_GROUP)
    groups = list(mi.GROUP_FIELDS) + [mi.ACCESSORY]
    for cls in CLASSES:
        text = mi.phases_detailed_json(cls)
        assert json.loads(text) == mi.detailed_fractions(cls)
        keys = list(json.loads(text))
        rank = [(groups.index(mi.PHASE_GROUP[k]), order.index(k)) for k in keys]
        assert rank == sorted(rank), cls
    assert mi.phases_detailed_json("Unknown") is None


def test_the_detail_checks_can_fail(monkeypatch):
    """A split that no longer sums to one must turn the add-back check red."""
    bad = {p: dict(s) for p, s in mi.PHASE_DETAIL["S"].items()}
    bad["nickel-iron"]["taenite"] += 0.1
    monkeypatch.setitem(mi.PHASE_DETAIL, "S", bad)
    fine = mi.detailed_fractions("S")
    got = sum(f for p, f in fine.items() if mi.PHASE_GROUP[p] == "metal")
    assert got != pytest.approx(T["S"]["metal_fraction"], abs=1e-12)


def test_enrich_writes_comp_phases_detailed_beside_comp_phases():
    df = pd.DataFrame({
        "designation": ["a", "b", "c", "d"],
        "spectral_type": ["S", "X", "X", None],
        "albedo": [0.25, 0.05, float("nan"), float("nan")],
    })
    out = ac.enrich_composition(df)
    by = dict(zip(out["designation"], out["comp_phases_detailed"]))
    assert json.loads(by["a"]) == mi.detailed_fractions("S")
    assert json.loads(by["b"]) == mi.detailed_fractions("P")
    assert json.loads(by["c"]) == mi.detailed_fractions("X")
    # and the 1.7.0 column is exactly what it was
    for d, cls in zip(out["designation"], out["comp_class"]):
        want = mi.phases_json(cls)
        got = dict(zip(out["designation"], out["comp_phases"]))[d]
        assert (got is None or pd.isna(got)) if want is None else got == want
