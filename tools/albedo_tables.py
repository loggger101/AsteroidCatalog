# -*- coding: utf-8 -*-
"""Recompute derive.py's albedo tables from a built catalog, and compare.

    python tools/albedo_tables.py asteroid_catalog.parquet
    python tools/albedo_tables.py asteroid_catalog.parquet --tolerance 0.05

The tables that size ~1.4 M bodies (ALBEDO_BY_SPECTRAL_TYPE, the two orbital
tables and ALBEDO_BEYOND_JUPITER_BY_H) are medians over a release.  Until
this tool they were backed by a comment that said so; now the claim can be
re-run.  Each table has ONE selection rule, the one that reproduces the
committed values from `data-2026-09-26` (46 of 47 classes to 0.005, every
orbital bin to 0.001):

  by class          a SOURCE-given class (`spectral_type_source == "source"`,
                    or "tholen"), a measured 0 < albedo < 1, n >= 5
  belt bins         JPL's albedos (`albedo_provider == "JPL SBDB"`), non-NEOs
  NEO bins          JPL's albedos, NEOs
  beyond Jupiter    a >= 5.5 AU, EVERY provider (JPL has few there), by H
  fallback          every JPL albedo

WHY NOT THE ALBEDO_ASSUMED ROWS: a table recomputed over the bodies it sized
would be the table's own output fed back as its input.  Only measured albedos
count, which the `albedo` column always is.

Read-only; no network.  Exit status 1 when any committed median has drifted
from the catalog's by more than `--tolerance` (relative), or a class with
n >= 5 in the catalog is missing from the table: that is the day to recompute
the table and move the data contract, not to edit the number by hand.
"""

import argparse
import sys
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from asteroid_catalog._frame import flag, numeric
from asteroid_catalog.derive import (
    ALBEDO_BEYOND_JUPITER_BY_H, ALBEDO_BY_SEMI_MAJOR_AXIS_AU,
    ALBEDO_BY_SEMI_MAJOR_AXIS_AU_NEO, ALBEDO_BY_SPECTRAL_TYPE, ALBEDO_FALLBACK,
)
from asteroid_catalog.query import read_catalog

JPL = "JPL SBDB"
MIN_CLASS_N = 5
BEYOND_JUPITER_AU = ALBEDO_BY_SEMI_MAJOR_AXIS_AU[-1][0]


def _read(path: str) -> pd.DataFrame:
    if path.endswith(".parquet"):
        return pd.read_parquet(path)
    return read_catalog(path)


def _measured(df: pd.DataFrame) -> pd.Series:
    a = numeric(df, "albedo")
    return (a > 0) & (a < 1)


def _jpl(df: pd.DataFrame) -> pd.Series:
    if "albedo_provider" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["albedo_provider"].astype("string").eq(JPL).fillna(False)


def by_class(df: pd.DataFrame) -> Dict[str, Tuple[float, int]]:
    """{class: (median, n)} over source-given classes with n >= 5."""
    src = df.get("spectral_type_source", pd.Series("", index=df.index))
    keep = _measured(df) & src.isin(["source", "tholen"])
    g = numeric(df, "albedo")[keep].groupby(df.loc[keep, "spectral_type"]).agg(["median", "size"])
    g = g[g["size"] >= MIN_CLASS_N]
    return {str(k): (float(r["median"]), int(r["size"])) for k, r in g.iterrows()}


def by_orbit(df: pd.DataFrame, table, neo: bool) -> List[Tuple[str, float, int]]:
    """(label, median, n) per bin of an orbital table, JPL albedos only."""
    a = numeric(df, "semi_major_axis_au")
    who = flag(df, "is_neo") if neo else ~flag(df, "is_neo")
    alb = numeric(df, "albedo")
    base = _measured(df) & _jpl(df) & who
    out = []
    for a_min, a_max, _p, label in table:
        m = base & (a >= a_min) & (a < a_max)
        out.append((label, float(alb[m].median()) if m.any() else np.nan, int(m.sum())))
    return out


def beyond_jupiter(df: pd.DataFrame) -> List[Tuple[str, float, int]]:
    """(label, median, n) per H band past Jupiter, every provider."""
    a, h, alb = (numeric(df, c) for c in ("semi_major_axis_au", "absolute_magnitude_h", "albedo"))
    base = _measured(df) & (a >= BEYOND_JUPITER_AU)
    out, lower = [], -np.inf
    for h_max, _p, label in ALBEDO_BEYOND_JUPITER_BY_H:
        m = base & (h > lower) & (h <= h_max)
        out.append((label, float(alb[m].median()) if m.any() else np.nan, int(m.sum())))
        lower = h_max
    return out


def fallback(df: pd.DataFrame) -> Tuple[float, int]:
    m = _measured(df) & _jpl(df)
    return float(numeric(df, "albedo")[m].median()) if m.any() else np.nan, int(m.sum())


def _drift(committed: float, now: float) -> float:
    return abs(now / committed - 1.0) if committed and np.isfinite(now) else np.inf


def compare(df: pd.DataFrame, tolerance: float = 0.05) -> Tuple[List[str], List[str]]:
    """(report lines, problems).  A problem is drift over `tolerance`, a
    class the catalog has n >= 5 of and the table lacks, or a committed bin
    the catalog cannot fill."""
    lines, problems = [], []

    def row(table, label, committed, now, n):
        d = _drift(committed, now)
        bad = d > tolerance
        lines.append("  %-28s %-6s committed %.4f  catalog %s  n=%-6s%s"
                     % (label, table, committed,
                        "%.4f" % now if np.isfinite(now) else "  -   ", format(n, ","),
                        "  <-- %.1f%%" % (100 * d) if bad and np.isfinite(d) else
                        ("  <-- no sample" if bad else "")))
        if bad:
            problems.append("%s %s: committed %.4f, catalog %s (n=%d)"
                            % (table, label, committed,
                               "%.4f" % now if np.isfinite(now) else "none", n))

    lines.append("BY SPECTRAL TYPE  (source-given class, n >= %d)" % MIN_CLASS_N)
    cls = by_class(df)
    for k, committed in ALBEDO_BY_SPECTRAL_TYPE.items():
        now, n = cls.get(k, (np.nan, 0))
        row("class", k, committed, now, n)
    for k in sorted(set(cls) - set(ALBEDO_BY_SPECTRAL_TYPE)):
        problems.append("class %s: n=%d in the catalog and absent from the table" % (k, cls[k][1]))
        lines.append("  %-28s class  ABSENT from the table        catalog %.4f  n=%d"
                     % (k, cls[k][0], cls[k][1]))

    for title, table, neo in (("BELT BINS  (JPL albedos, non-NEOs)", ALBEDO_BY_SEMI_MAJOR_AXIS_AU, False),
                              ("NEO BINS  (JPL albedos, NEOs)", ALBEDO_BY_SEMI_MAJOR_AXIS_AU_NEO, True)):
        lines.append(title)
        for (label, now, n), (_lo, _hi, committed, _l) in zip(by_orbit(df, table, neo), table):
            if label == ALBEDO_BY_SEMI_MAJOR_AXIS_AU[-1][3]:
                # The fallback for a body past Jupiter with no H: every
                # provider, like the H bands, so it is judged below with them.
                continue
            if not neo and table[0][3] == label and n == 0:
                # Under 1.3 AU every body is a NEO; the belt row exists only
                # so a non-NEO there (none today) still gets a value.
                continue
            row("orbit", label, committed, now, n)

    lines.append("BEYOND JUPITER  (a >= %.1f AU, every provider)" % BEYOND_JUPITER_AU)
    for (label, now, n), (_h, committed, _l) in zip(beyond_jupiter(df), ALBEDO_BEYOND_JUPITER_BY_H):
        row("H", label, committed, now, n)
    a = numeric(df, "semi_major_axis_au")
    m = _measured(df) & (a >= BEYOND_JUPITER_AU)
    row("orbit", ALBEDO_BY_SEMI_MAJOR_AXIS_AU[-1][3], ALBEDO_BY_SEMI_MAJOR_AXIS_AU[-1][2],
        float(numeric(df, "albedo")[m].median()) if m.any() else np.nan, int(m.sum()))

    lines.append("FALLBACK  (every JPL albedo)")
    now, n = fallback(df)
    row("all", "whole sample", ALBEDO_FALLBACK, now, n)
    return lines, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("catalog", help="asteroid_catalog.csv[.gz] or .parquet")
    ap.add_argument("--tolerance", type=float, default=0.05,
                    help="relative drift allowed before a median counts as stale (default 0.05)")
    args = ap.parse_args(argv)

    df = _read(args.catalog)
    stamp = ""
    if "pipeline_version" in df.columns and len(df):
        stamp = " (data contract %s, built %s)" % (df["pipeline_version"].iloc[0],
                                                  df.get("catalog_date", pd.Series([""])).iloc[0])
    print("%s: %s rows%s\n" % (args.catalog, format(len(df), ","), stamp))
    lines, problems = compare(df, args.tolerance)
    print("\n".join(lines))
    print("\nSTALE  (over %.0f%% drift, or missing)" % (100 * args.tolerance))
    for p in problems or ["none"]:
        print("  - " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
