# -*- coding: utf-8 -*-
"""The failsafes, and a log of everything they rejected.

Every drop is counted and the reason is kept, because a filter that silently
shrinks a catalog is indistinguishable from a fetcher that silently failed.
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

from .config import CatalogConfig

# ─────────────────────────────────────────────────────────────────────────────
# VALIDATOR  (failsafes)
# ─────────────────────────────────────────────────────────────────────────────
def _log_rejection(df: pd.DataFrame, mask: pd.Series, reason: str) -> dict:
    """Build a rejection-log record for the given mask."""
    count = int(mask.sum())
    examples = (
        df.loc[mask, "designation"].head(5).tolist()
        if count and "designation" in df.columns
        else []
    )
    return {"reason": reason, "rejected_count": count, "examples": str(examples)}


def validate_and_filter(
    df: pd.DataFrame,
    config: CatalogConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply validation rules and drop entries with missing critical data.

    Failsafes applied in order:
      1. No designation                                       → drop
      2. No diameter, or diameter ≤ 0                         → drop
      3. Diameter < min_diameter_km                           → drop
      4. No semi-major axis (a)                               → drop
      5. If strict mode: no Bus-DeMeo AND no Tholen type      → drop

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

    bad = df["designation"].isna() | (df["designation"].astype(str).str.strip() == "")
    log.append(_log_rejection(df, bad & valid_mask, "Missing designation"))
    valid_mask &= ~bad

    # ── 2/3. Diameter required, positive, and ≥ min_diameter_km ─────────────
    if "diameter_km" in df.columns:
        diam = pd.to_numeric(df["diameter_km"], errors="coerce")

        bad_missing = diam.isna() | (diam <= 0)
        log.append(_log_rejection(df, bad_missing & valid_mask,
                                  "Missing or non-positive diameter"))
        valid_mask &= ~bad_missing

        bad_small = diam < config.min_diameter_km
        log.append(_log_rejection(df, bad_small & valid_mask,
                                  f"diameter < {config.min_diameter_km} km"))
        valid_mask &= ~bad_small
    else:
        log.append({"reason": "diameter_km column absent",
                    "rejected_count": int(valid_mask.sum()), "examples": "N/A"})
        valid_mask[:] = False

    # ── 4. Semi-major axis required ───────────────────────────────────────────
    if "semi_major_axis_au" in df.columns:
        a   = pd.to_numeric(df["semi_major_axis_au"], errors="coerce")
        bad = a.isna() | (a <= 0)
        log.append(_log_rejection(df, bad & valid_mask, "Missing semi-major axis"))
        valid_mask &= ~bad
    else:
        log.append({"reason": "semi_major_axis_au column absent — coordinate mapping disabled",
                    "rejected_count": 0, "examples": "N/A"})
        say("     WARN  No orbital elements - coordinate mapping will be unavailable")

    # ── 5. Strict spectral type (optional) ───────────────────────────────────
    # Validate runs BEFORE enrich_composition's Tholen fallback, so we have to
    # consult `spectral_type` AND `spectral_type_tholen` here, otherwise a row
    # carrying only a Tholen letter (e.g. JPL `spec_T="G"`) would be wrongly
    # rejected, contradicting the CONFIG comment that says strict mode requires
    # "Bus / Tholen".  A row passes if EITHER column has a non-blank value.
    if config.require_spectral_type:
        def _blank(s: pd.Series) -> pd.Series:
            """True where a taxonomy column holds nothing usable.

            NaN and the empty string both count, and so does whitespace: a
            source that writes `" "` for "no classification" would otherwise
            pass strict mode with a blank type.
            """
            return s.isna() | (s.astype(str).str.strip() == "")

        has_bus    = (~_blank(df["spectral_type"]))           if "spectral_type"        in df.columns else pd.Series(False, index=df.index)
        has_tholen = (~_blank(df["spectral_type_tholen"]))    if "spectral_type_tholen" in df.columns else pd.Series(False, index=df.index)

        if not (has_bus.any() or has_tholen.any()):
            log.append({"reason": "no spectral_type / spectral_type_tholen columns (strict mode ON)",
                        "rejected_count": int(valid_mask.sum()), "examples": "N/A"})
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
    say(f"     FAIL  Rejected : {n_dropped:,}  ({n_dropped/total*100:.1f}%)")
    if not rejection_df.empty:
        for _, row in rejection_df.iterrows():
            say(f"         * {row['reason']:55s} -> {row['rejected_count']:,} dropped")

    return filtered, rejection_df
