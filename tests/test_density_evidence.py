# -*- coding: utf-8 -*-
"""tools/density_evidence.py: the rule that holds class densities to a
catalog's own masses.

What is pinned is the selection (only a measured density on a class a source
gave, from a mass known to 20%, inside Jupiter's orbit), the grouping (by the
row a body's composition is read from, so a dark X-type counts toward P),
the rule (DENSITY_EVIDENCE's: never above mean + 2 SD, below mean - 2 SD only
with a stated reason, nothing judged on fewer than three bodies) and the
recount of the X/Xc split.  Run on data-2026-09-26b it passes every row it
can test; before the split it failed Xc.
"""

import pandas as pd
import pytest

from _support import load_tool

evidence = load_tool("density_evidence")


def _rows(n, **cols):
    return pd.DataFrame({k: [v] * n for k, v in cols.items()})


def _body(cls, rho, n=1, rel=0.1, **over):
    cols = dict(designation="x", spectral_type=cls, spectral_type_source="source",
                density_gcm3=rho, estimated_mass_kg=1e18, estimated_mass_sigma_kg=rel * 1e18,
                mass_measured=True, density_measured=True, semi_major_axis_au=2.7,
                albedo=0.05)
    cols.update(over)
    return _rows(n, **cols)


def _frame(*parts):
    return pd.concat(parts, ignore_index=True)


def test_only_measured_densities_on_source_classes_count():
    df = _frame(
        _body("C", 1.5),
        _body("C", 9.0, spectral_type_source="albedo"),     # a class this pipeline inferred
        _body("C", 9.0, density_measured=False),            # the class estimate
        _body("C", 9.0, rel=0.5),                           # a mass good to 50%
        _body("C", 9.0, rel=0.0),                           # a zero sigma is no sigma
        _body("C", 9.0, estimated_mass_sigma_kg=float("nan")),
        _body("C", 9.0, semi_major_axis_au=40.0),           # composition is D's out there
        _body("C", 1.7, spectral_type_source="tholen"),
    )
    got = evidence.measured_bodies(df)
    assert sorted(got["rho"]) == [1.5, 1.7]


def test_an_estimate_above_its_bodies_fails_and_one_inside_passes():
    # Xk's estimate (3.80) against three light bodies; C's (1.50) inside its own.
    df = _frame(_body("Xk", 1.0), _body("Xk", 1.4), _body("Xk", 1.8),
                _body("C", 1.2), _body("C", 1.5), _body("C", 1.9))
    lines, problems = evidence.compare(df)
    assert [p.split(":")[0] for p in problems] == ["Xk"]
    assert any(line.split()[:1] == ["C"] and line.rstrip().endswith("ok") for line in lines)


def test_below_needs_a_reason_and_fewer_than_three_is_not_judged():
    # B sits below large B-types with DENSITY_EVIDENCE's reason (Bennu);
    # V has no reason, but two bodies are not a sample.
    df = _frame(_body("B", 2.4, n=3), _body("B", 2.5), _body("V", 9.0, n=2))
    lines, problems = evidence.compare(df)
    assert problems == []
    assert any("with DENSITY_EVIDENCE's reason" in line for line in lines)
    assert any(line.split()[:1] == ["V"] and "not judged" in line for line in lines)


def test_the_x_complex_is_split_by_albedo():
    df = _frame(_body("X", 1.3, albedo=0.05), _body("Xk", 3.9, albedo=0.15),
                _body("M", 3.7, albedo=0.20), _body("E", 3.0, albedo=0.50),
                _body("C", 1.5, albedo=0.05))                 # not X-complex
    bins = dict(evidence.x_by_albedo(evidence.measured_bodies(df)))
    assert [bins[label]["n"] for _lo, _hi, label in evidence.X_ALBEDO_BINS] == [1, 2, 1]
    assert bins[evidence.X_ALBEDO_BINS[1][2]]["mean"] == pytest.approx(3.8)


def test_a_dark_x_type_counts_toward_p_and_a_built_row_is_believed():
    # No comp_class: recomputed from the label and the albedo.
    split = evidence.measured_bodies(_frame(_body("X", 1.3, albedo=0.05),
                                            _body("X", 3.9, albedo=0.15),
                                            _body("X", 2.0, albedo=float("nan"))))
    assert split["class"].tolist() == ["P", "M", "X"]
    # With it, the column a 1.6.0 build wrote is what counts.
    built = evidence.measured_bodies(_body("X", 1.3, albedo=0.05, comp_class="M"))
    assert built["class"].tolist() == ["M"]


def test_the_split_is_recounted_and_a_drifted_mixture_fails():
    # All of X's albedos dark: the mixture is P's 1.20, far from the row.
    df = _frame(_body("X", 1.2, n=3, albedo=0.05),
                _body("X", 1.2, n=2, albedo=0.05, mass_measured=False))
    assert evidence.x_split_counts(df)["X"] == (5, 0, 0)
    _, problems = evidence.compare(df)
    assert any(p.startswith("X:") and "mixture" in p for p in problems), problems


def test_main_exits_nonzero_when_a_class_fails(tmp_path):
    bad, good = tmp_path / "bad.parquet", tmp_path / "good.parquet"
    _body("Xk", 1.2, n=3).to_parquet(bad)
    _body("C", 1.5, n=3).to_parquet(good)
    assert evidence.main([str(bad)]) == 1
    assert evidence.main([str(good)]) == 0
