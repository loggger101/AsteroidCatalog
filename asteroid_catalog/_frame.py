# -*- coding: utf-8 -*-
"""Column access that tolerates an absent column, written once.

Every stage reads columns a given build may not have -- a source toggled off,
a field an upstream schema dropped -- and each had re-spelled the same
"coerce it, or stand in a column of NaN" expression inline, a dozen times.
"""

from typing import Iterable

import numpy as np
import pandas as pd


def numeric(df: pd.DataFrame, col: str) -> pd.Series:
    """`df[col]` as numbers, NaN where unparseable; all NaN if absent."""
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(np.nan, index=df.index, dtype="float64")


def flag(df: pd.DataFrame, col: str) -> pd.Series:
    """`df[col]` as bool, missing read as False; all False if absent."""
    if col in df.columns:
        return df[col].fillna(False).astype(bool)
    return pd.Series(False, index=df.index)


def coerce_numeric(df: pd.DataFrame, cols: Iterable[str]) -> None:
    """Coerce, in place, every one of `cols` that `df` has."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
