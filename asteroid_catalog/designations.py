# -*- coding: utf-8 -*-
"""The canonical identifier every source is merged on.

A NAIVE `^\\d+` IS THE DEFECT THIS MODULE EXISTS TO AVOID.  For "2024 BX1"
that yields "2024", which is not null, is not obviously wrong, and
cross-matches unrelated bodies.
"""

import pandas as pd


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

    # Pre-clean: "1996 GQ0" → "1996 GQ".  NEOWISE writes a provisional
    # designation with no cycle count as a trailing ZERO, where JPL, the MPC and
    # every other source here write nothing.  "0" is never a real cycle count,
    # so the rewrite cannot collide with a genuine designation; without it 3,000+
    # NEOWISE bodies matched nothing and were dropped at validation for having
    # no orbit.
    cleaned = cleaned.str.replace(r"^(\d{4} [A-Z]{2})0$", r"\1", regex=True)

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

    # "<NA>" is what `.astype(str)` makes of a missing value in pandas' nullable
    # "string" dtype.  Left in, it is a ghost key: not null, and equal to every
    # other missing designation.
    return result.replace(
        {"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "None": pd.NA, "none": pd.NA,
         "<NA>": pd.NA}
    )


def _designation_key(s: pd.Series) -> pd.Series:
    """The COMPARISON form of a designation: canonical, then upper-cased.

    For matching and duplicate detection only, never for output.  It is the
    same extractor the fetchers run to produce `designation`, so "(1) Ceres",
    "1 Ceres" and "00001" all compare equal to JPL's "1" while "2024 BX1"
    stays whole; upper-casing stops case variation fragmenting a group.
    """
    return _extract_canonical_designation(s).str.upper().str.strip()


# ─────────────────────────────────────────────────────────────────────────────
# SHARED: DESIGNATION SHAPES
# ─────────────────────────────────────────────────────────────────────────────
# A provisional designation ("2024 BX1", "1996 GQ") or a Palomar-Leiden /
# Trojan survey designation ("2040 P-L", "3138 T-1").  Used to tell a real IAU
# NAME from a designation sitting in a column called `name`: SsODNet fills its
# `name` with the provisional designation for every unnamed body, and letting
# that through turned 1.5 M unnamed asteroids into "named" ones.
_DESIGNATION_SHAPE = r"^(\d{4} [A-Z]{2}\d*|\d{4} (P-L|T-[123]))$"


def _looks_like_designation(s: pd.Series) -> pd.Series:
    """True where a value is a provisional or survey designation, not a name."""
    return s.astype("string").str.strip().str.match(_DESIGNATION_SHAPE, na=False)


# MPC packed numbers: "00433" is 433, "A1955" is 101955 (A = 10, a = 36), and
# from 620,000 on "~" plus four base-62 digits.  MP3C lists a numbered body's
# number only in this form.
_MPC_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _unpack_mpc_number(packed: pd.Series) -> pd.Series:
    """Decode MPC packed asteroid numbers to plain number strings; NA otherwise."""
    def one(p) -> object:
        """One packed number, or NA for anything that is not one."""
        if not isinstance(p, str) or len(p) != 5:
            return pd.NA
        try:
            if p[0] == "~":
                v = 0
                for ch in p[1:]:
                    v = v * 62 + _MPC_BASE62.index(ch)
                return str(620_000 + v)
            if not p[1:].isdigit():
                return pd.NA
            return str(_MPC_BASE62.index(p[0]) * 10_000 + int(p[1:]))
        except ValueError:
            return pd.NA
    return packed.map(one).astype("string")


def _provisional_from_full_name(full_name: pd.Series) -> pd.Series:
    """The primary provisional designation in a JPL `full_name`.

    "     1 Ceres (A801 AA)" gives "A801 AA", "  433 Eros (A898 PA)" gives
    "A898 PA", "(2019 JD121)" gives "2019 JD121".  It is what lets a source that
    still carries a body under its provisional designation join the number JPL
    has since given it.
    """
    return (full_name.astype("string")
            .str.extract(r"\(([^)]+)\)\s*$", expand=False)
            .str.strip()
            .replace({"": pd.NA}))
