# -*- coding: utf-8 -*-
"""Derived composition columns, from taxonomy alone.

EVERYTHING HERE IS A LOOKUP KEYED ON A TAXONOMY CLASS, and there are ~76 of
them across ~1.55 M rows, so every pass goes through `_by_distinct`.  Written
per row it was ~19 million calls to produce ~800 answers.
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

from .taxonomy import TAXONOMY_COMPOSITION, _by_distinct, pgm_enrichment_for_type

# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITION ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────────
def enrich_composition(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add composition columns derived from the spectral taxonomy lookup table.

    Steps:
      1. Normalise spectral_type strings  (Title-case, strip blank-ish values).
      2a. Where spectral_type is absent, fall back to spectral_type_tholen.
      2b. Where it's STILL absent, infer a coarse type from geometric albedo.
      2c. Where there is no measured albedo either, fall back to the albedo
          ASSUMED when the diameter was derived from H (v1.1.0).
          A `spectral_type_source` column records provenance:
            • "source"         → arrived from a fetcher (JPL spec_B, SsODNet
                                 taxonomy.class, MP3C taxonomy, …)
            • "tholen"         → filled from spectral_type_tholen (step 2a)
            • "albedo"         → inferred from measured albedo (step 2b)
            • "albedo_assumed" → inferred from the assumed albedo behind an
                                 H-derived diameter (step 2c), the weakest
                                 class, and the bulk of a default v1.1.0 run
            • "unknown"        → still missing after every fallback
      3. Look up TAXONOMY_COMPOSITION fields for each type → `comp_*` cols.
      4. Fill density_gcm3 from taxonomy estimate where no measurement exists;
         `density_measured` flag tracks provenance.
      5. Compute estimated_mass_kg, preserving any value already supplied by a
         fetcher (SsODNet) and filling gaps with (4/3)π r³ ρ from
         diameter × density; `mass_measured` flag tracks provenance.
    """
    say("\n  Enriching composition data ...")
    df = df.copy()

    # ── 1. Normalise spectral_type ────────────────────────────────────────────
    if "spectral_type" not in df.columns:
        df["spectral_type"] = pd.NA

    df["spectral_type"] = (
        df["spectral_type"]
        .astype(str)
        .str.strip()
        .replace({"nan": pd.NA, "None": pd.NA, "": pd.NA, "-": pd.NA,
                  "NaN": pd.NA, "none": pd.NA, "NA": pd.NA})
    )

    # Capitalise to match Bus-DeMeo convention (e.g. "sq" → "Sq")
    def normalise_type(t):
        """One spectral type in Bus-DeMeo capitalisation, or NA.

        First letter upper, rest lower, so "sq" and "SQ" both become "Sq" and
        meet the taxonomy tables' keys. Run through `_by_distinct`, so it is
        called once per class rather than once per row.
        """
        if pd.isna(t) or not isinstance(t, str):
            return pd.NA
        t = t.strip()
        return t[0].upper() + t[1:].lower() if t else pd.NA

    df["spectral_type"] = _by_distinct(df["spectral_type"], normalise_type)

    # `spectral_type_source` tracks WHERE the final classification came from so
    # consumers can filter on confidence:
    #   "source"  - supplied by a fetcher (Bus-DeMeo from JPL spec_B, or a
    #               curated mix from SsODNet / MP3C)
    #   "tholen"  - filled from spectral_type_tholen because Bus wasn't there
    #   "albedo"  - crude inference from geometric albedo
    #   "unknown", still missing after every fallback
    df["spectral_type_source"] = np.where(df["spectral_type"].notna(), "source", "unknown")

    # ── 2a. Fall back to Tholen classification where Bus-DeMeo is missing ────
    # JPL (`spec_T`) supplies Tholen; we hold it in
    # `spectral_type_tholen`.  Most Tholen letters (S, C, X, V, …) overlap with
    # Bus-DeMeo directly; the Tholen-only ones (M, E, P, F, G) are now in
    # TAXONOMY_COMPOSITION too, so the lookup at step 3 handles them uniformly.
    if "spectral_type_tholen" in df.columns:
        tholen = _by_distinct(df["spectral_type_tholen"], normalise_type)
        fill_mask = df["spectral_type"].isna() & tholen.notna()
        df.loc[fill_mask, "spectral_type"]        = tholen[fill_mask]
        df.loc[fill_mask, "spectral_type_source"] = "tholen"
        n_thol = int(fill_mask.sum())
        if n_thol:
            say(f"       Spectral type filled from Tholen for {n_thol:,} entries")

    # ── 2b. Infer from albedo where type is still missing ────────────────────
    def _infer_from_albedo(a: float) -> str:
        """Coarse spectral-type inference from geometric albedo."""
        if a < 0.10: return "C"     # dark      → carbonaceous
        if a < 0.35: return "S"     # moderate  → stony
        return "V"                  # bright    → basaltic or E-type

    if "albedo" in df.columns:
        alb = pd.to_numeric(df["albedo"], errors="coerce")
        infer_mask = df["spectral_type"].isna() & alb.notna()

        df.loc[infer_mask, "spectral_type"]        = alb[infer_mask].apply(_infer_from_albedo)
        df.loc[infer_mask, "spectral_type_source"] = "albedo"
        n_inf = int(infer_mask.sum())
        if n_inf:
            say(f"       Spectral type inferred from albedo for {n_inf:,} entries")

    # ── 2c. Infer from the albedo ASSUMED when the diameter was derived ──────
    # Separate from 2b and separately labelled, because the input is an
    # assumption rather than a measurement.  It exists so a derived body's size
    # and its composition rest on the SAME assumption instead of contradicting
    # each other; see the note in derive_missing_diameters().  Without this the
    # 1.4 M H-derived bodies would all land on TAXONOMY_COMPOSITION["Unknown"],
    # whose fractions are None, so they would carry no density, no mass, and be
    # skipped by Stage 4 for having no mass at all.
    if "albedo_assumed_for_diameter" in df.columns:
        assumed = pd.to_numeric(df["albedo_assumed_for_diameter"], errors="coerce")
        assume_mask = df["spectral_type"].isna() & assumed.notna()

        df.loc[assume_mask, "spectral_type"]        = assumed[assume_mask].apply(_infer_from_albedo)
        df.loc[assume_mask, "spectral_type_source"] = "albedo_assumed"
        n_ass = int(assume_mask.sum())
        if n_ass:
            say(f"       Spectral type inferred from the ASSUMED albedo for "
                  f"{n_ass:,} entries (H-derived diameters)")

    # ── 3. Look up composition fields ────────────────────────────────────────
    # `minerals` and `notes` are included because for a mining-profitability
    # pipeline the dominant minerals + the literature note are first-class
    # outputs; a user looking at one row wants to know what's actually there.
    comp_fields = [
        "group", "composition", "minerals", "notes",
        "density_est_gcm3",
        "metal_fraction", "silicate_fraction", "carbon_fraction", "ice_fraction",
    ]

    def _lookup(spec_type, field):
        """Return composition field for a given spectral type."""
        if pd.isna(spec_type) or not isinstance(spec_type, str):
            return TAXONOMY_COMPOSITION["Unknown"][field]
        if spec_type in TAXONOMY_COMPOSITION:
            return TAXONOMY_COMPOSITION[spec_type][field]
        # Fallback: match first character (e.g. unknown sub-type "Sq2" → "S")
        root = spec_type[0] if spec_type else ""
        if root in TAXONOMY_COMPOSITION:
            return TAXONOMY_COMPOSITION[root][field]
        return TAXONOMY_COMPOSITION["Unknown"][field]

    # One factorisation of `spectral_type`, nine columns read off it.  The
    # codes are identical for every field, so factorising once and indexing
    # nine times is nine passes of C-level take instead of nine of `.apply`.
    _spec_codes, _spec_uniques = pd.factorize(df["spectral_type"],
                                              use_na_sentinel=False)
    for field in comp_fields:
        _vals = np.empty(len(_spec_uniques), dtype=object)
        for _i, _u in enumerate(_spec_uniques):
            _vals[_i] = _lookup(_u, field)
        # `.infer_objects()` for the reason `_by_distinct` documents at length:
        # several of these fields are floats-with-`None`, and `.apply()` would
        # have handed back float64/NaN rather than object/None.
        df[f"comp_{field}"] = pd.Series(_vals[_spec_codes],
                                        index=df.index).infer_objects()

    # ── 3b. PGM enrichment factor (v1.0.4) ────────────────────────────────────
    # Per-spectral-type multiplier applied to platinum-group-metal yields
    # in Module 2's "nickel-iron" mineral.  Differentiated bodies (M-type
    # cores) have ~2× chondritic PGM in their metal phase; basaltic-crust
    # fragments (V-type) ~0.2×.  See PGM_ENRICHMENT_BY_TYPE for the table.
    df["comp_pgm_enrichment"] = _by_distinct(df["spectral_type"],
                                             pgm_enrichment_for_type)
    n_enriched  = int((df["comp_pgm_enrichment"] > 1.0).sum())
    n_depleted  = int((df["comp_pgm_enrichment"] < 1.0).sum())
    if n_enriched or n_depleted:
        say(f"       PGM enrichment: {n_enriched:,} enriched (>1x)  |  "
              f"{n_depleted:,} depleted (<1x)  |  rest baseline (1x)")

    # ── 4. Fill density gap ───────────────────────────────────────────────────
    if "density_gcm3" in df.columns:
        df["density_gcm3"]    = pd.to_numeric(df["density_gcm3"], errors="coerce")
        df["density_measured"] = df["density_gcm3"].notna()
    else:
        df["density_gcm3"]    = np.nan
        df["density_measured"] = False

    df["density_gcm3"] = df["density_gcm3"].fillna(
        pd.to_numeric(df["comp_density_est_gcm3"], errors="coerce")
    )

    n_meas = int(df["density_measured"].sum())
    n_est  = len(df) - n_meas
    say(f"       Density: {n_meas:,} measured  |  {n_est:,} estimated from taxonomy")

    # ── 5. Compute estimated mass (kg) ────────────────────────────────────────
    # Keep any MEASURED mass already supplied by a source (SsODNet).
    # `mass_measured` tracks provenance: True if the value came from a fetcher,
    # False if we derived it here from diameter × density (sphere assumption).
    if "estimated_mass_kg" in df.columns:
        measured = pd.to_numeric(df["estimated_mass_kg"], errors="coerce")
    else:
        measured = pd.Series(np.nan, index=df.index, dtype="float64")
    df["mass_measured"] = measured.notna()

    if "diameter_km" in df.columns:
        diam_m   = pd.to_numeric(df["diameter_km"], errors="coerce") * 1_000.0
        rho_kgm3 = pd.to_numeric(df["density_gcm3"], errors="coerce") * 1_000.0
        derived  = (4 / 3) * np.pi * (diam_m / 2) ** 3 * rho_kgm3
    else:
        derived  = pd.Series(np.nan, index=df.index, dtype="float64")

    # Measured wins; derived fills the gaps.
    df["estimated_mass_kg"] = measured.fillna(derived)

    n_mass_meas = int(df["mass_measured"].sum())
    n_mass_der  = int(df["estimated_mass_kg"].notna().sum()) - n_mass_meas
    say(f"        Mass:    {n_mass_meas:,} measured  |  {n_mass_der:,} derived (diameter x density)")

    return df
