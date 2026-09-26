# -*- coding: utf-8 -*-
"""Reading a built catalog: lookup by identifier, slice by orbit or class."""

import pandas as pd

from ._log import say


# ─────────────────────────────────────────────────────────────────────────────
# QUERY UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
def read_catalog(path: str) -> pd.DataFrame:
    """Read a catalog CSV the way every reader must: designation as a string.

    A numbered asteroid's designation looks like an integer, so a slice in
    which every row happens to be numbered infers int64 and every string
    comparison against it matches nothing.
    """
    return pd.read_csv(path, low_memory=False,
                       dtype={"designation": str, "provisional_designation": str,
                              "name": str, "spk_id": str})


def lookup_asteroid(catalog: pd.DataFrame, query: str) -> pd.DataFrame:
    """
    Quick lookup by designation or name (case-insensitive substring match).

    Usage:
        lookup_asteroid(catalog, "Ceres")
        lookup_asteroid(catalog, "2024 BX1")
        lookup_asteroid(catalog, "(1) Ceres")

    regex=False, designations and names carry regex metacharacters, which
    pandas' default regex=True would interpret as a pattern: "(1) Ceres"
    silently matched "1 Ceres", and a stray bracket raised re.PatternError.

    MISSING VALUES MUST STAY MISSING.  `astype(str)` spells a missing name
    "nan" (or "<NA>"), so "NA" matched every one of the ~1.54 M unnamed bodies
    and "nan" nearly as many; `astype("string")` keeps them NA, and `na=False`
    then excludes them.  A blank query matches nothing, not everything.
    """
    q = query.strip().upper()
    if not q:
        say("Empty query - nothing to look up")
        return catalog.iloc[0:0]

    def matches(col: str) -> pd.Series:
        return catalog[col].astype("string").str.upper().str.contains(
            q, na=False, regex=False).astype(bool)

    mask = matches("designation")
    # `provisional_designation` so a numbered body is still found by the
    # designation it was discovered under ("1999 RQ36" finds Bennu).  Until
    # 1.3.0 that worked by accident, through SsODNet designations leaking into
    # `name`.
    for col in ("name", "provisional_designation"):
        if col in catalog.columns:
            mask |= matches(col)

    results = catalog[mask]
    if results.empty:
        say(f"No entries found matching '{query}'")
    return results


def filter_by_region(catalog: pd.DataFrame, lo_au: float, hi_au: float) -> pd.DataFrame:
    """
    Return catalog entries whose semi-major axis is in [lo_au, hi_au).

    Usage:
        mba = filter_by_region(catalog, 2.0, 3.3)       # main belt
        trojans = filter_by_region(catalog, 5.05, 5.35)  # Jupiter Trojans

    Semi-major axis, not distance: an NEO is defined by its PERIHELION
    (q < 1.3 AU), so select those with `catalog[catalog["is_neo"] == True]`
    rather than a band here, which would miss most Apollos and Amors.
    """
    if "semi_major_axis_au" not in catalog.columns:
        say("No orbital data available")
        return pd.DataFrame()
    a = pd.to_numeric(catalog["semi_major_axis_au"], errors="coerce")
    return catalog[(a >= lo_au) & (a < hi_au)].copy()


def filter_by_spectral_group(catalog: pd.DataFrame, *groups: str) -> pd.DataFrame:
    """
    Filter by composition group name (e.g. 'C-complex', 'S-complex', 'X-complex').

    Usage:
        metallic = filter_by_spectral_group(catalog, 'X-complex')
        cc = filter_by_spectral_group(catalog, 'C-complex', 'D-type')
    """
    if "comp_group" not in catalog.columns:
        say("No composition group data available")
        return pd.DataFrame()
    return catalog[catalog["comp_group"].isin(groups)].copy()
