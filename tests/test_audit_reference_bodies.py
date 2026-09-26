# -*- coding: utf-8 -*-
"""The audit's reference-body check: five measured sizes stay `measured`.

Synthetic frames only, like the rest of the suite.  `tools/` is not a package,
so the module is loaded from its path.
"""

import pandas as pd
import pytest

from _support import load_tool

audit = load_tool("audit_catalog")


def _frame(designations=("1", "2", "4", "16", "433"), source="measured"):
    return pd.DataFrame({
        "designation": list(designations),
        "diameter_source": [source] * len(designations),
        "diameter_km": [939.4, 512.6, 525.4, 223.1, 17.6][:len(designations)],
    })


def test_all_five_measured_is_clean():
    rows, bad = audit.reference_bodies(_frame())
    assert len(rows) == 5
    assert bad == []


def test_a_derived_diameter_is_flagged_by_name():
    df = _frame()
    df.loc[df["designation"] == "433", "diameter_source"] = "derived"
    _, bad = audit.reference_bodies(df)
    assert bad == ["Eros diameter_source is 'derived', not 'measured'"]


def test_a_missing_body_is_flagged_by_name():
    _, bad = audit.reference_bodies(_frame(("1", "2", "4", "433")))
    assert bad == ["Psyche (16) is not in the catalog"]


def test_integer_designations_still_match():
    """A parquet can come back with numbered designations as ints."""
    df = _frame()
    df["designation"] = df["designation"].astype(int)
    rows, bad = audit.reference_bodies(df)
    assert len(rows) == 5
    assert bad == []


def test_no_designation_column_is_a_failure_not_a_pass():
    _, bad = audit.reference_bodies(_frame().drop(columns="designation"))
    assert bad == ["no designation column"]


@pytest.mark.parametrize("source", ["measured", "derived"])
def test_main_exits_nonzero_only_when_a_reference_body_fails(tmp_path, source):
    path = str(tmp_path / "catalog.parquet")
    df = _frame()
    df.loc[df["designation"] == "4", "diameter_source"] = source
    df.to_parquet(path)
    assert audit.main([path]) == (0 if source == "measured" else 1)
