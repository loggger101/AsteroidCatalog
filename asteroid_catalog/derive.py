# -*- coding: utf-8 -*-
"""Diameter from absolute magnitude, when nothing measured one.

    D_km = (1329 / sqrt(p_V)) * 10 ** (-H / 5)        Fowler & Chillemi (1992)

H is measured, so the ONLY estimated quantity is the geometric albedo.  Every
row this produces is tagged in `diameter_source` and flagged in
`derived_diameter_is_estimate`; a measured diameter always wins.

READ THE PROVENANCE BEFORE COMPARING TWO CATALOGS.  Mass scales as p_V ** -1.5,
so two runs with the same row count and a different measured/derived split are
not the same population.
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
# DERIVED DIAMETERS  (v1.1.0)
# ─────────────────────────────────────────────────────────────────────────────
#
# validate_and_filter drops any body with no diameter, and that single rule is
# what has bounded this pipeline's population since v1.0.0.  Of JPL's 1,554,321
# asteroids only 139,582 have a measured diameter: 9.0%.  1,553,817 have an
# absolute magnitude H.
#
# Diameter follows from H and the geometric albedo with no free parameters:
#
#     D_km = (1329 / sqrt(p_V)) * 10 ** (-H / 5)
#
# (Fowler & Chillemi 1992; the 1329 km constant is 2 AU_km * 10**(-V_sun/5)
# with the Sun's V = -26.762, and is the same constant JPL and the MPC use.)
#
# So the ONLY estimated quantity is p_V, and everything below is about getting
# the best available p_V for each row and recording which one was used.
#
# ⚠️  READ THIS BEFORE TRUSTING A DERIVED ROW.  D scales as p_V**-0.5, and this
# pipeline turns D into MASS as D**3, so mass scales as p_V**-1.5.  Get the
# albedo wrong by 2x and the mass is wrong by 2.8x.  Every consumer that ranks
# on mass is therefore much more exposed to this than the diameter column
# suggests, which is why `diameter_source` and `derived_diameter_is_estimate`
# exist and why nothing here ever overwrites a measurement.
#
# ⚠️  AND THE ALBEDO SAMPLE BELOW IS BIASED, in the optimistic direction.  Both
# tables are medians over the 138,437 bodies that HAVE a measured albedo, and
# those measurements are overwhelmingly NEOWISE, a thermal-infrared survey.
# At a fixed H a darker body must be larger, and a larger warmer body is easier
# for a thermal survey to detect, so the measured sample over-represents dark
# bodies relative to the 1.4 M that were never measured.  A median that is too
# LOW yields a diameter that is too LARGE and a mass that is too large by the
# 1.5 power.  Do not "correct" this by raising the table to taste; that is the
# same move CLAUDE.md rejects for IN_SPACE_UTILITY.  Quantifying it needs a
# debiased size-frequency model, which this module does not have.

# Median measured geometric albedo per spectral type.  DERIVED, not asserted:
# computed 2026-08-08 over every JPL SBDB asteroid with 0 < albedo < 1 and a
# Bus-DeMeo (spec_B) or, failing that, Tholen (spec_T) classification: 1,897
# bodies.  Sample size is carried on each row because it varies by two orders
# of magnitude across the table and a reader deserves to see which entries are
# solid.  Types with n < 5 are deliberately ABSENT rather than guessed; they
# fall through the chain in `_albedo_for_derivation` below.
ALBEDO_BY_SPECTRAL_TYPE: Dict[str, float] = {
    "A":   0.2980,   # n=16
    "B":   0.0670,   # n=65
    "C":   0.0540,   # n=195
    "Cb":  0.0520,   # n=35
    "Cg":  0.0490,   # n=9
    "Cgh": 0.0720,   # n=15
    "Ch":  0.0504,   # n=136
    "D":   0.0509,   # n=39
    "F":   0.0466,   # n=20
    "K":   0.1423,   # n=34
    "L":   0.1680,   # n=35
    "Ld":  0.1610,   # n=12
    "M":   0.1310,   # n=15
    "O":   0.1905,   # n=6
    "P":   0.0435,   # n=22
    "Q":   0.2475,   # n=10
    "S":   0.2439,   # n=534
    "Sa":  0.2650,   # n=33
    "Sk":  0.2340,   # n=19
    "Sl":  0.2240,   # n=51
    "Sq":  0.2760,   # n=59
    "Sr":  0.3180,   # n=17
    "T":   0.0645,   # n=16
    "V":   0.3880,   # n=36
    "X":   0.0855,   # n=156
    "Xc":  0.0750,   # n=61
    "Xe":  0.2090,   # n=27
    "Xk":  0.0955,   # n=42
}

# ⚠️  E-types are the known casualty of the n >= 5 rule.  Only four measured
# E-types carry a JPL taxonomy, so "E" is absent, its root letter is itself, and
# an E-type with no measured albedo therefore falls all the way to its orbital
# bin, which will be far too dark for an enstatite surface (real E-types run
# p_V ~ 0.4-0.5) and will size the body much too large.  It is left absent
# rather than filled from literature so that the table stays one thing, 
# medians over this catalog; instead of a mixture nobody can audit.  E-types
# with a MEASURED albedo are unaffected, and that is most of the ones that
# matter.  Same applies to G and R.

# Median measured geometric albedo by semi-major axis, same 138,437-body
# sample.  THIS is the branch that actually sizes the catalog: a body with a
# taxonomy almost always has a diameter too, so the taxonomy table above fires
# rarely, while ~1.4 M bodies have nothing but H and an orbit.
#
# The gradient is the well-known compositional zoning of the belt, S-complex
# inner, C-complex outer, and it is strong enough to be worth binning for:
# 0.2885 at 1.3-2.0 AU against 0.0660 in the outer belt is a factor of 4.4 in
# albedo, which is a factor of 2.1 in derived diameter and 9.4 in derived mass.
# Bin edges are the classical Kirkwood-gap boundaries, not fitted.
ALBEDO_BY_SEMI_MAJOR_AXIS_AU: Tuple[Tuple[float, float, float, str], ...] = (
    # (a_min, a_max, median p_V, label)
    (0.000,  1.300, 0.1870, "NEA"),                    # n=296
    (1.300,  2.000, 0.2885, "Mars-crosser / inner"),   # n=906
    (2.000,  2.500, 0.1890, "inner belt"),             # n=29,921
    (2.500,  2.820, 0.0860, "middle belt"),            # n=45,912
    (2.820,  3.270, 0.0660, "outer belt"),             # n=57,161
    (3.270,  3.700, 0.0570, "Cybele"),                 # n=1,126
    (3.700,  5.200, 0.0610, "Hilda / Trojan"),         # n=1,884
    (5.200,  1e9,   0.0690, "Centaur / TNO"),          # n=1,228
)

# Overall median across the whole measured sample.  Last resort only: used for
# a body with no albedo, no usable taxonomy and no semi-major axis, which in
# practice cannot happen because validate_and_filter requires an orbit anyway.
ALBEDO_FALLBACK = 0.0780

# D_km = _H_DIAMETER_CONSTANT / sqrt(p_V) * 10**(-H/5)
_H_DIAMETER_CONSTANT = 1329.0


def _albedo_for_derivation(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """
    Best available geometric albedo per row, plus a label saying where it came
    from.  Preference order, most to least trustworthy:

        1. `albedo`                    - a real measurement
        2. ALBEDO_BY_SPECTRAL_TYPE     - exact type, then root letter
        3. ALBEDO_BY_SEMI_MAJOR_AXIS   - the belt's albedo gradient
        4. ALBEDO_FALLBACK             - whole-sample median

    Returns (albedo, source_label) aligned to df.index.
    """
    n = len(df)
    albedo = pd.Series(np.nan, index=df.index, dtype="float64")
    label  = pd.Series("",     index=df.index, dtype="object")

    # ── 1. Measured ───────────────────────────────────────────────────────────
    if "albedo" in df.columns:
        measured = pd.to_numeric(df["albedo"], errors="coerce")
        # An albedo outside (0, 1) is unphysical and shows up in real catalogs
        # as a fit that did not converge.  Reject rather than propagate it into
        # a square root.
        measured = measured.where((measured > 0) & (measured < 1))
        albedo   = albedo.fillna(measured)
        label[measured.notna()] = "measured_albedo"

    # ── 2. Taxonomy ───────────────────────────────────────────────────────────
    # Consult both classification columns; Bus-DeMeo wins where present.  This
    # runs BEFORE enrich_composition, so the albedo-inferred spectral types that
    # step invents are not visible here, which is deliberate.  Inferring a type
    # from albedo and then an albedo from that type would be a closed loop that
    # launders one guess into two columns.
    tax = pd.Series(pd.NA, index=df.index, dtype="object")
    for col in ("spectral_type", "spectral_type_tholen"):
        if col in df.columns:
            candidate = df[col].astype("string").str.strip()
            candidate = candidate.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            tax = tax.where(tax.notna(), candidate)

    need = albedo.isna() & tax.notna()
    if need.any():
        def _from_taxonomy(t: object) -> float:
            """Median geometric albedo for a spectral type, or NaN if unknown.

            Falls back to the ROOT letter ("Sq2" to "S"), matching the fallback
            `_lookup()` already uses for composition, so a sub-type nobody
            tabulated still sizes off its complex rather than dropping out of
            the catalog.
            """
            if not isinstance(t, str) or not t:
                return np.nan
            s = t.strip()
            if s in ALBEDO_BY_SPECTRAL_TYPE:
                return ALBEDO_BY_SPECTRAL_TYPE[s]
            # Root letter, matching the fallback _lookup() already uses for
            # composition: "Sq2" → "S".
            return ALBEDO_BY_SPECTRAL_TYPE.get(s[0].upper(), np.nan)

        derived_tax = tax[need].map(_from_taxonomy)
        albedo.loc[need] = derived_tax
        label[need & albedo.notna()] = "taxonomy_albedo"

    # ── 3. Orbital bin ────────────────────────────────────────────────────────
    if "semi_major_axis_au" in df.columns:
        a = pd.to_numeric(df["semi_major_axis_au"], errors="coerce")
        for a_min, a_max, p_v, _lbl in ALBEDO_BY_SEMI_MAJOR_AXIS_AU:
            band = albedo.isna() & a.notna() & (a >= a_min) & (a < a_max)
            albedo.loc[band] = p_v
            label[band] = "orbit_albedo"

    # ── 4. Whole-sample median ────────────────────────────────────────────────
    last = albedo.isna()
    albedo.loc[last] = ALBEDO_FALLBACK
    label[last] = "fallback_albedo"

    assert len(albedo) == n and albedo.notna().all(), \
        "every row must end with an albedo: the fallback cannot be skipped"
    return albedo, label


def derive_missing_diameters(
    df: pd.DataFrame,
    config: CatalogConfig,
) -> pd.DataFrame:
    """
    Fill `diameter_km` from absolute magnitude H where no diameter was measured.

    Runs between merge and validation, because validation is what drops rows
    with no diameter and the entire point is to have one by then.

    Adds two provenance columns, following the `spectral_type_source` /
    `density_measured` convention already used in this module:

        diameter_source                 "measured"
                                        "derived_h_measured_albedo"
                                        "derived_h_taxonomy_albedo"
                                        "derived_h_orbit_albedo"
                                        "derived_h_fallback_albedo"
                                        "none"
        derived_diameter_is_estimate    bool, one thing to filter on

    A measured diameter is NEVER overwritten, whatever the gate is set to.
    """
    df = df.copy()

    if "diameter_km" not in df.columns:
        df["diameter_km"] = np.nan
    diam = pd.to_numeric(df["diameter_km"], errors="coerce")
    measured = diam > 0

    df["diameter_source"] = np.where(measured, "measured", "none")
    df["derived_diameter_is_estimate"] = ~measured

    if not config.derive_diameter_from_h:
        say("\n  Diameter derivation OFF - measured diameters only "
              f"({int(measured.sum()):,} of {len(df):,} rows will survive validation)")
        df["diameter_km"] = diam
        return df

    say("\n  Deriving diameters from absolute magnitude ...")

    if "absolute_magnitude_h" not in df.columns:
        # Every source supplies H, so its total absence means something upstream
        # broke rather than that the data is simply unavailable.  Say so; a
        # silent no-op here costs 1.4 M rows.
        say("     WARN  No `absolute_magnitude_h` column - nothing to derive from. "
              "Check that the JPL fetcher requested the H field.")
        df["diameter_km"] = diam
        return df

    H = pd.to_numeric(df["absolute_magnitude_h"], errors="coerce")
    target = (~measured) & H.notna()
    n_target = int(target.sum())

    if not n_target:
        say("     NOTE   Every row already carries a measured diameter")
        df["diameter_km"] = diam
        return df

    albedo, albedo_label = _albedo_for_derivation(df)

    derived = (
        _H_DIAMETER_CONSTANT / np.sqrt(albedo) * np.power(10.0, -H / 5.0)
    )

    # Floor applies to DERIVED rows only.  A measured diameter below the floor
    # is governed by `min_diameter_km` in validate_and_filter, which is a
    # separate decision about what is worth cataloguing at all.
    if config.min_derived_diameter_km > 0:
        too_small = target & (derived < config.min_derived_diameter_km)
        n_small = int(too_small.sum())
        if n_small:
            say(f"        {n_small:,} derived below "
                  f"{config.min_derived_diameter_km} km - left unfilled "
                  f"(min_derived_diameter_km)")
        target &= ~too_small

    # Guard against a non-finite result reaching the catalog.  H is occasionally
    # absurd in a raw catalog and 10**(-H/5) underflows to 0 for large H.
    target &= np.isfinite(derived) & (derived > 0)

    diam = diam.where(~target, derived)
    df["diameter_km"] = diam
    df.loc[target, "diameter_source"] = (
        "derived_h_" + albedo_label[target].astype(str)
    )
    df["derived_diameter_is_estimate"] = ~measured

    # Publish the albedo this step assumed, in its OWN column, never merged
    # into `albedo`, which must keep meaning "measured".
    #
    # enrich_composition reads it as the last fallback for spectral type, and
    # that is a consistency requirement rather than a convenience.  Assuming
    # p_V = 0.066 for an outer-belt body IS assuming the body is carbonaceous;
    # sizing it on that number and then recording its composition as "Unknown"
    # would leave the catalog holding two incompatible beliefs about the same
    # rock, and "Unknown" carries None for every composition fraction, so the
    # body would get no density, no mass, and be skipped by Stage 4 anyway.
    # That would make the whole derivation pointless: 1.4 M rows with a
    # diameter and nothing to do with it.
    #
    # Note the direction of the dependency, because the reverse WOULD be
    # circular: one assumption (albedo) produces two outputs (size, class).
    # Inferring the class first and then reading an albedo back off the class
    # would launder a single guess into two apparently independent columns.
    df.loc[target, "albedo_assumed_for_diameter"] = albedo[target]

    counts = df["diameter_source"].value_counts()
    say(f"     OK  {int(target.sum()):,} diameters derived  "
          f"(measured kept: {int(measured.sum()):,})")
    for src, n in counts.items():
        if src == "none":
            continue
        say(f"         * {str(src):32s} -> {int(n):,}")
    still = int((pd.to_numeric(df['diameter_km'], errors='coerce').fillna(0) <= 0).sum())
    if still:
        say(f"         * {'no diameter (will be dropped)':32s} -> {still:,}")

    return df
