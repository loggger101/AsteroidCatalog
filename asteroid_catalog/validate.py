# -*- coding: utf-8 -*-
"""The failsafes, and a log of everything they rejected.

Every drop is counted and the reason is kept, because a filter that silently
shrinks a catalog is indistinguishable from a fetcher that silently failed.
"""

from typing import Tuple

import numpy as np
import pandas as pd

from ._log import say, warn

from .config import CatalogConfig
from .taxonomy import _BLANK_CLASSES

# ─────────────────────────────────────────────────────────────────────────────
# VALIDATOR  (failsafes)
# ─────────────────────────────────────────────────────────────────────────────
def _blank(s: pd.Series) -> pd.Series:
    """True where a column holds nothing usable.

    NaN and the empty string both count, and so does whitespace: a source that
    writes `" "` for "no value" would otherwise pass as having one.
    """
    return s.isna() | (s.astype(str).str.strip() == "")


def _log_rejection(df: pd.DataFrame, mask: pd.Series, reason: str) -> dict:
    """Build a rejection-log record for the given mask."""
    count = int(mask.sum())
    examples = (
        df.loc[mask, "designation"].head(5).tolist()
        if count and "designation" in df.columns
        else []
    )
    return {"reason": reason, "rejected_count": count, "examples": str(examples)}


def _log_column_absent(reason: str, count: int) -> dict:
    """A rejection-log record for a rule that could not run row by row."""
    return {"reason": reason, "rejected_count": count, "examples": "N/A"}


def validate_and_filter(
    df: pd.DataFrame,
    config: CatalogConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply validation rules and drop entries with missing critical data.

    Failsafes applied in order:
      1. No designation                                       → drop
      2. No diameter, or a non-finite or ≤ 0 one              → drop
      3. No semi-major axis (a), or a non-finite or ≤ 0 one   → drop
      4. If strict mode: no Bus-DeMeo AND no Tholen type      → drop

    `min_diameter_km` is not here: it judges the final diameter, which
    enrichment can still change (`apply_final_gates`, after enrichment).

    Returns:
        (filtered_df, rejection_log_df)
    """
    say("\n  Validating entries ...")

    if df.empty:
        say("     WARN  Nothing to validate")
        return df.copy(), pd.DataFrame()

    total      = len(df)
    valid_mask = pd.Series(True, index=df.index)
    log        = []

    # ── 1. Designation required ───────────────────────────────────────────────
    if "designation" not in df.columns:
        warn("     FAIL  'designation' column missing - cannot build catalog")
        return pd.DataFrame(), pd.DataFrame()

    bad = _blank(df["designation"])
    log.append(_log_rejection(df, bad & valid_mask, "Missing designation"))
    valid_mask &= ~bad

    # ── 2. Diameter required, finite and positive ───────────────────────────
    if "diameter_km" in df.columns:
        diam = pd.to_numeric(df["diameter_km"], errors="coerce")

        bad_inf = pd.Series(np.isinf(diam), index=df.index)
        log.append(_log_rejection(df, bad_inf & valid_mask, "Non-finite diameter"))
        valid_mask &= ~bad_inf

        bad_missing = diam.isna() | (diam <= 0)
        log.append(_log_rejection(df, bad_missing & valid_mask,
                                  "Missing or non-positive diameter"))
        valid_mask &= ~bad_missing
    else:
        log.append(_log_column_absent("diameter_km column absent",
                                      int(valid_mask.sum())))
        valid_mask[:] = False

    # ── 3. Semi-major axis required, finite and positive ─────────────────────
    if "semi_major_axis_au" in df.columns:
        a   = pd.to_numeric(df["semi_major_axis_au"], errors="coerce")
        bad = pd.Series(np.isinf(a), index=df.index)
        log.append(_log_rejection(df, bad & valid_mask, "Non-finite semi-major axis"))
        valid_mask &= ~bad
        bad = a.isna() | (a <= 0)
        log.append(_log_rejection(df, bad & valid_mask, "Missing semi-major axis"))
        valid_mask &= ~bad
    else:
        log.append(_log_column_absent(
            "semi_major_axis_au column absent — coordinate mapping disabled", 0))
        say("     WARN  No orbital elements - coordinate mapping will be unavailable")

    # ── 4. Strict spectral type (optional) ───────────────────────────────────
    # Validate runs BEFORE enrich_composition's Tholen fallback, so we have to
    # consult `spectral_type` AND `spectral_type_tholen` here, otherwise a row
    # carrying only a Tholen letter (e.g. JPL `spec_T="G"`) would be wrongly
    # rejected, contradicting the CONFIG comment that says strict mode requires
    # "Bus / Tholen".  A row passes if EITHER column has a non-blank value.
    if config.require_spectral_type:
        def _has(col: str) -> pd.Series:
            if col not in df.columns:
                return pd.Series(False, index=df.index)
            # The taxonomy's own list of how a source spells "no class": "-"
            # is not a class, whatever the column's dtype makes of it.
            marker = df[col].astype("string").str.strip().isin(_BLANK_CLASSES)
            return ~(_blank(df[col]) | marker)

        has_bus, has_tholen = _has("spectral_type"), _has("spectral_type_tholen")

        if not (has_bus.any() or has_tholen.any()):
            log.append(_log_column_absent(
                "no spectral_type / spectral_type_tholen columns (strict mode ON)",
                int(valid_mask.sum())))
            valid_mask[:] = False
        else:
            bad = ~(has_bus | has_tholen)
            log.append(_log_rejection(df, bad & valid_mask,
                                      "Missing Bus AND Tholen spectral type (strict mode ON)"))
            valid_mask &= ~bad

    # ── Apply ─────────────────────────────────────────────────────────────────
    filtered  = df[valid_mask].copy()
    n_kept    = len(filtered)
    n_dropped = total - n_kept

    rejection_df = pd.DataFrame([r for r in log if r["rejected_count"] > 0])

    say(f"     OK  Accepted : {n_kept:,}")
    # FAIL only when something was dropped: a clean run's log said
    # "FAIL  Rejected : 0 (0.0%)" in every build summary.
    say(f"     {'FAIL' if n_dropped else 'OK'}  Rejected : {n_dropped:,}  "
        f"({n_dropped/total*100:.1f}%)")
    if not rejection_df.empty:
        for _, row in rejection_df.iterrows():
            say(f"         * {row['reason']:55s} -> {row['rejected_count']:,} dropped")

    return filtered, rejection_df


def apply_final_gates(
    df: pd.DataFrame,
    config: CatalogConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """The rules that judge what enrichment settled, run after it.

      1. Diameter, mass or density computed to a non-finite value  → drop
      2. Diameter < min_diameter_km                                → drop

    Enrichment can replace an H-derived diameter with the one a measured mass
    gives, in either direction, so the floor read before it let bodies ship
    under the floor and discarded bodies a mass would have put above it.  A
    missing estimate (an Unknown class has no density or mass) is not a failed
    computation and stays.

    Returns:
        (filtered_df, rejection_log_df)
    """
    valid_mask = pd.Series(True, index=df.index)
    log = []

    for col in ("diameter_km", "estimated_mass_kg", "density_gcm3"):
        if col in df.columns:
            bad = pd.Series(np.isinf(pd.to_numeric(df[col], errors="coerce")), index=df.index)
            log.append(_log_rejection(df, bad & valid_mask, f"Non-finite computed {col}"))
            valid_mask &= ~bad

    if "diameter_km" in df.columns:
        diam = pd.to_numeric(df["diameter_km"], errors="coerce")
        bad = diam < config.min_diameter_km
        log.append(_log_rejection(df, bad & valid_mask,
                                  f"diameter < {config.min_diameter_km} km"))
        valid_mask &= ~bad

    rejection_df = pd.DataFrame([r for r in log if r["rejected_count"] > 0])
    if not rejection_df.empty:
        say("\n  Final gates ...")
        for _, row in rejection_df.iterrows():
            say(f"         * {row['reason']:55s} -> {row['rejected_count']:,} dropped")
    return df[valid_mask].copy(), rejection_df
