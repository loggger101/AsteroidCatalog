# -*- coding: utf-8 -*-
"""Reading a built catalog: lookup by identifier, slice by orbit or class.

`lookup_asteroid` is also exported as `lookup_body`, and the alias is not
cosmetic -- see its docstring.
"""

import json
import os
import sys
import time as _time
import warnings
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from tqdm.auto import tqdm

from ._log import say, warn


# ─────────────────────────────────────────────────────────────────────────────
# QUERY UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
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
    """
    q = query.strip().upper()
    mask = (
        catalog["designation"].astype(str).str.upper().str.contains(
            q, na=False, regex=False)
    )
    if "name" in catalog.columns:
        mask |= catalog["name"].astype(str).str.upper().str.contains(
            q, na=False, regex=False)

    results = catalog[mask]
    if results.empty:
        say(f"No entries found matching '{query}'")
    return results


def filter_by_region(catalog: pd.DataFrame, lo_au: float, hi_au: float) -> pd.DataFrame:
    """
    Return catalog entries within a heliocentric distance band (AU).

    Usage:
        mba = filter_by_region(catalog, 2.0, 3.3)   # main belt
        neas = filter_by_region(catalog, 0.0, 1.3)   # NEAs
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
