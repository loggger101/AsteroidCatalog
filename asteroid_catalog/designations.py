# -*- coding: utf-8 -*-
"""The canonical identifier every source is merged on.

A NAIVE `^\\d+` IS THE DEFECT THIS MODULE EXISTS TO AVOID.  For "2024 BX1"
that yields "2024", which is not null, is not obviously wrong, and
cross-matches unrelated bodies.
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
# SHARED: CANONICAL DESIGNATION
# ─────────────────────────────────────────────────────────────────────────────
# JPL's `pdes` field is the canonical identifier we merge on:
#   • Numbered asteroids → integer string, e.g. "1" (Ceres), "433" (Eros)
#   • Unnumbered         → provisional designation, e.g. "2024 BX1", "1999 KW4"
#
# Other sources spell the same identifier differently: VizieR uses
# "(1) Ceres", some catalogs render "1 Ceres", others zero-pad to "00001".
# This helper collapses every common surface form to the JPL form so the
# merge key is consistent across every source.
#
# CRITICAL CORRECTNESS NOTE
# A naive `^\d+` regex (which earlier versions of this pipeline used) is
# WRONG: for "2024 BX1" it extracts "2024", which would silently fail to
# match JPL's "2024 BX1" in the join AND would dedup-collapse every "2024 X*"
# provisional designation onto a single row.  This helper distinguishes
# numbered-with-name from provisional by checking what follows the digits.

def _extract_canonical_designation(s: pd.Series) -> pd.Series:
    """
    Normalise a Series of raw asteroid designations to JPL-pdes form.

    Surface form               -> Canonical
    --------------------------    ---------
    "1"                           "1"
    "00001"                       "1"             (lstrip zeros)
    "1 Ceres"                     "1"             (number + Title-Case name)
    "433 Eros"                    "433"
    "(1) Ceres"                   "1"             (paren-wrapped number)
    "2024 BX1"                    "2024 BX1"      (PROVISIONAL; KEEP WHOLE)
    "1999 KW4"                    "1999 KW4"
    "Ceres"                       "Ceres"         (bare name, kept as-is)
    "" / NaN / "None"             pd.NA

    Distinguishes numbered-with-name from provisional designations by the
    character class that follows the leading digits: a Title-Case name
    (capital + at least one lowercase) marks a numbered asteroid; ALL-CAPS
    letters that may include digits mark a provisional designation.
    """
    raw = s.astype(str).str.strip()

    # Pre-clean: "(N) Name" → "N Name"
    cleaned = raw.str.replace(
        r"^\s*\(\s*(\d+)\s*\)\s*", r"\1 ", regex=True
    )

    # Pre-clean: "3.0" → "3".  A float-typed identifier column stringified by
    # pandas is the single most likely way a caller hands us a broken key, and
    # it is silent, "3.0" is not null, so nothing downstream complains; it just
    # never joins.  That is exactly how NEOWISE contributed zero rows to every
    # large run before v1.1.0 (see fetch_neowise).  Only a trailing .0 (or .000)
    # is stripped, so a genuine identifier is never truncated.
    cleaned = cleaned.str.replace(r"^(\d+)\.0+$", r"\1", regex=True)

    # Case A: numbered asteroid with a name, extract the leading number.
    # The name part must start with a capital + lowercase letter, which is
    # what distinguishes "1 Ceres" from a provisional like "2024 BX1".
    numbered_with_name = cleaned.str.extract(
        r"^(\d+)\s+[A-Z][a-z]", expand=False
    )

    # Case B: pure number (with possible leading zeros and trailing whitespace).
    pure_number = cleaned.str.extract(r"^(\d+)\s*$", expand=False)

    # Combine: numbered_with_name wins, then pure_number, else keep cleaned.
    result = numbered_with_name
    result = result.where(result.notna(), pure_number)
    result = result.where(result.notna(), cleaned)

    # For purely numeric results, strip leading zeros ("00001" → "1").
    # Don't apply to provisional designations like "1999 KW4".
    is_numeric  = result.str.match(r"^\d+$", na=False)
    stripped_num = result.str.lstrip("0").replace({"": "0"})
    result      = result.where(~is_numeric, stripped_num)

    return result.replace(
        {"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "None": pd.NA, "none": pd.NA}
    )
