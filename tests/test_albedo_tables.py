# -*- coding: utf-8 -*-
"""tools/albedo_tables.py: the rules that recompute derive.py's albedo tables.

The rules are the claim.  Run on `data-2026-09-26` they reproduce every
committed median (46 of 47 classes to 0.005, every orbital bin to 0.001), so
what is pinned here is that each table is read off the sample it says it is:
measured albedos only, a source's class only, JPL's albedos in the belt, every
provider past Jupiter.
"""

import pandas as pd

from _support import load_tool

tables = load_tool("albedo_tables")


def _rows(n, **cols):
    return pd.DataFrame({k: [v] * n for k, v in cols.items()})


def _frame(*parts):
    return pd.concat(parts, ignore_index=True)


def test_a_class_median_counts_only_measured_albedos_of_source_classes():
    df = _frame(
        _rows(5, spectral_type="C", spectral_type_source="source", albedo=0.06),
        # an albedo this pipeline inferred the class FROM is not evidence for it
        _rows(9, spectral_type="C", spectral_type_source="albedo", albedo=0.09),
        _rows(9, spectral_type="C", spectral_type_source="albedo_assumed", albedo=0.09),
        # a fit at its ceiling, and no albedo at all
        _rows(9, spectral_type="C", spectral_type_source="source", albedo=1.0),
        _rows(9, spectral_type="C", spectral_type_source="source", albedo=float("nan")),
        # four is too few to be a median
        _rows(4, spectral_type="Q", spectral_type_source="source", albedo=0.25),
        _rows(5, spectral_type="G", spectral_type_source="tholen", albedo=0.08),
    )
    got = tables.by_class(df)
    assert got == {"C": (0.06, 5), "G": (0.08, 5)}


def test_belt_bins_read_jpl_albedos_and_neos_their_own_table():
    df = _frame(
        _rows(3, semi_major_axis_au=2.2, is_neo=False, albedo=0.19, albedo_provider="JPL SBDB"),
        _rows(9, semi_major_axis_au=2.2, is_neo=False, albedo=0.15, albedo_provider="SsODNet"),
        _rows(3, semi_major_axis_au=2.2, is_neo=True, albedo=0.137, albedo_provider="JPL SBDB"),
    )
    belt = {label: (m, n) for label, m, n in
            tables.by_orbit(df, tables.ALBEDO_BY_SEMI_MAJOR_AXIS_AU, neo=False)}
    neo = {label: (m, n) for label, m, n in
           tables.by_orbit(df, tables.ALBEDO_BY_SEMI_MAJOR_AXIS_AU_NEO, neo=True)}
    assert belt["inner belt"] == (0.19, 3)
    assert neo["NEO, inner belt"] == (0.137, 3)


def test_past_jupiter_every_provider_counts_and_h_picks_the_band():
    df = _frame(
        _rows(3, semi_major_axis_au=40.0, absolute_magnitude_h=4.0, albedo=0.15,
              albedo_provider="SsODNet"),
        _rows(3, semi_major_axis_au=40.0, absolute_magnitude_h=9.0, albedo=0.06,
              albedo_provider="MP3C"),
        _rows(3, semi_major_axis_au=5.2, absolute_magnitude_h=4.0, albedo=0.9,
              albedo_provider="SsODNet"),         # a Trojan, not past Jupiter
    )
    bands = {label: (m, n) for label, m, n in tables.beyond_jupiter(df)}
    assert bands["large TNO, H 3-6"] == (0.15, 3)
    assert bands["small TNO / Centaur, H > 8"] == (0.06, 3)
    assert bands["dwarf planet, H <= 3"][1] == 0


def test_drift_and_a_missing_class_are_reported():
    df = _frame(
        _rows(5, spectral_type="C", spectral_type_source="source", albedo=0.12),
        _rows(5, spectral_type="Zz", spectral_type_source="source", albedo=0.05),
    )
    _, problems = tables.compare(df, tolerance=0.05)
    assert any(p.startswith("class C:") for p in problems), problems
    assert any(p.startswith("class Zz:") and "absent" in p for p in problems), problems


def test_main_exits_nonzero_on_a_stale_table(tmp_path):
    path = tmp_path / "c.parquet"
    _rows(5, designation="1", spectral_type="C", spectral_type_source="source",
          albedo=0.5).to_parquet(path)
    assert tables.main([str(path)]) == 1
