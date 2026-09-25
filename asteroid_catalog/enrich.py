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

from .physics import (
    ALBEDO_CEILING, ALBEDO_FLOOR, OUTER_SOLAR_SYSTEM_AU, OUTER_SOLAR_SYSTEM_CLASS,
    albedo_from_h_and_diameter, bulk_density_gcm3, density_limits,
    diameter_from_mass_km, sphere_volume_m3,
)
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
      2a'. Beyond 5.5 AU, an untyped body is D, from its orbit (1.4.0).
      2b. Where it's STILL absent, infer a coarse type from geometric albedo.
      2c. Where there is no measured albedo either, fall back to the albedo
          ASSUMED when the diameter was derived from H (v1.1.0).
          A `spectral_type_source` column records provenance:
            • "source"         → arrived from a fetcher (JPL spec_B, SsODNet
                                 taxonomy.class, MP3C taxonomy, …)
            • "tholen"         → filled from spectral_type_tholen (step 2a)
            • "orbit"          → D, for an untyped body beyond Jupiter (2a')
            • "albedo"         → inferred from measured albedo (step 2b)
            • "albedo_assumed" → inferred from the assumed albedo behind an
                                 H-derived diameter (step 2c), the weakest
                                 class, and the bulk of a default v1.1.0 run
            • "unknown"        → still missing after every fallback
      3. Look up TAXONOMY_COMPOSITION fields for each type → `comp_*` cols.
      4/5. Density and mass, so that mass = density × volume in every row:
         a measured mass sets the density; failing that a source density
         within its class's possible range; failing that the class estimate.
         An H-derived diameter a measured mass refutes is re-derived from the
         mass.  `density_measured` and `mass_measured` track provenance.
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

    # ── 2a'. Beyond Jupiter, the orbit says more than the albedo (1.4.0) ────
    # The albedo inference below reads a bright surface as basalt (V) or stone
    # (S), which is right in the main belt and wrong past Jupiter, where a
    # bright surface is fresh ICE.  In the 2026-09-23 release it typed Pluto,
    # Haumea, Makemake and Sedna as V (2.9 g/cm3, 90% silicate, PGM-depleted
    # basaltic crust) and Quaoar and Gonggong as S, and gave all 8,127 H-sized
    # TNOs and Centaurs a main-belt C.  Every body beyond Jupiter's aphelion
    # with no classification from a source now takes D, the table's ice- and
    # organic-rich outer-Solar-System class, labelled "orbit".  A class a
    # source measured is never overridden.
    if "semi_major_axis_au" in df.columns:
        a_au = pd.to_numeric(df["semi_major_axis_au"], errors="coerce")
        outer = df["spectral_type"].isna() & (a_au > OUTER_SOLAR_SYSTEM_AU)
        df.loc[outer, "spectral_type"] = OUTER_SOLAR_SYSTEM_CLASS
        df.loc[outer, "spectral_type_source"] = "orbit"
        if int(outer.sum()):
            say(f"       Spectral type {OUTER_SOLAR_SYSTEM_CLASS} from the orbit "
                f"(a > {OUTER_SOLAR_SYSTEM_AU} AU) for {int(outer.sum()):,} entries")

    # ── 2b. Infer from albedo where type is still missing ────────────────────
    # Checked 1.4.0 against the 65,159 bodies of the 2026-09-23 release that
    # carry both a source class and a measured albedo.  Split at 0.10, C versus
    # stony is right for 84.0% (the best split, 0.13, reaches 85.2%, not worth
    # moving a boundary the literature uses).  The third bucket, p >= 0.35 ->
    # V, was right for 22%: 916 of 4,191 such bodies are V and 2,473 are
    # S-complex, and V carries basaltic crust's metal fraction and a 0.2x
    # PGM factor.  Bright bodies are S now.
    def _infer_from_albedo(a: float) -> str:
        """Coarse spectral-type inference from geometric albedo."""
        if a < 0.10: return "C"     # dark      → carbonaceous
        return "S"                  # otherwise → stony

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

    # ── 4/5. Density and mass, in ONE ROW THAT AGREES WITH ITSELF (1.4.0) ───
    # Until 1.3.0 these were three independent columns: a measured mass from
    # one catalog, a diameter from another and a density from a third (or from
    # the class table), so `estimated_mass_kg` was not `density_gcm3` times the
    # volume in 464 rows of the 2026-09-23 release.  Now, in every row,
    #
    #     estimated_mass_kg == density_gcm3 * pi/6 * diameter_km**3
    #
    # and whichever of the three was measured determines the others:
    #
    #     measured mass             density = mass / volume
    #     measured density, no mass mass = density * volume
    #     neither                   density = the class estimate, mass follows
    #
    # `density_measured` is True only when the density rests on measurements
    # alone: a measured mass over a measured diameter, or a source's density.
    mass_src = (pd.to_numeric(df["estimated_mass_kg"], errors="coerce")
                if "estimated_mass_kg" in df.columns
                else pd.Series(np.nan, index=df.index, dtype="float64"))
    rho_src = (pd.to_numeric(df["density_gcm3"], errors="coerce")
               if "density_gcm3" in df.columns
               else pd.Series(np.nan, index=df.index, dtype="float64"))
    rho_est = pd.to_numeric(df["comp_density_est_gcm3"], errors="coerce")
    diam = (pd.to_numeric(df["diameter_km"], errors="coerce")
            if "diameter_km" in df.columns
            else pd.Series(np.nan, index=df.index, dtype="float64"))
    estimate = (df["derived_diameter_is_estimate"].fillna(False).astype(bool)
                if "derived_diameter_is_estimate" in df.columns
                else pd.Series(False, index=df.index))

    # A MEASUREMENT is judged against the class a SOURCE gave, never against
    # one this function inferred from an albedo: an inference is not grounds
    # to overrule a measurement.  A source density outside its group's
    # possible range (physics.py) is dropped; SsODNet carries Ch-types at
    # 4.8-5.2 g/cm3, P-types at 5.3 and a D-type at 6.3.
    sourced = df["spectral_type_source"].isin(["source", "tholen"])
    lo_m, hi_m = density_limits(df["comp_group"].where(sourced, "Unknown"))
    bad_rho = rho_src.notna() & ~((rho_src >= lo_m) & (rho_src <= hi_m))
    rho_src = rho_src.mask(bad_rho)

    # AN ESTIMATE A MEASUREMENT REFUTES IS REPLACED.  A measured mass beside
    # a diameter DERIVED from H and an assumed albedo puts the body outside
    # the density its class allows: 2003 QY90 was a 257 km body of 5.2e17 kg,
    # 0.06 g/cm3, because a binary's H is two bodies' light and the Centaur/
    # TNO albedo bin is too dark for it.  The mass is the measurement, so the
    # diameter is re-derived from it at the class's density, labelled
    # "derived_mass".  If even that needs an albedo no surface has, the mass
    # cannot belong to this body and is dropped instead.
    lo_c, hi_c = density_limits(df["comp_group"])
    rho_md = pd.Series(bulk_density_gcm3(mass_src, diam), index=df.index)
    refuted = mass_src.notna() & estimate & ~((rho_md >= lo_c) & (rho_md <= hi_c))
    d_from_m = pd.Series(diameter_from_mass_km(mass_src, rho_est), index=df.index)
    h = (pd.to_numeric(df["absolute_magnitude_h"], errors="coerce")
         if "absolute_magnitude_h" in df.columns
         else pd.Series(np.nan, index=df.index, dtype="float64"))
    p_implied = pd.Series(albedo_from_h_and_diameter(h, d_from_m), index=df.index)
    fits = (refuted & (d_from_m > 0)
            & (p_implied.isna() | ((p_implied >= ALBEDO_FLOOR) & (p_implied < ALBEDO_CEILING))))
    if fits.any():
        diam = diam.where(~fits, d_from_m)
        df["diameter_km"] = diam
        df.loc[fits, "diameter_source"] = "derived_mass"
        if "albedo_assumed_for_diameter" in df.columns:
            df.loc[fits, "albedo_assumed_for_diameter"] = np.nan
    unfit = refuted & ~fits
    if unfit.any():
        mass_src = mass_src.mask(unfit)
        if "mass_screened_out" in df.columns and "mass_provider" in df.columns:
            prov = df["mass_provider"].astype("string")
            old = df["mass_screened_out"].astype("string")
            df["mass_screened_out"] = old.where(
                ~unfit, (old.fillna("") + ";" + prov).str.strip(";"))
            df.loc[unfit, "mass_provider"] = pd.NA

    mass_measured = mass_src.notna()
    vol_m3 = pd.Series(sphere_volume_m3(diam), index=df.index)
    density = pd.Series(np.where(mass_measured, bulk_density_gcm3(mass_src, diam),
                                 rho_src.fillna(rho_est)), index=df.index)
    df["density_gcm3"] = density
    df["density_measured"] = ((mass_measured & ~estimate)
                              | (~mass_measured & rho_src.notna()))
    df["mass_measured"] = mass_measured
    df["estimated_mass_kg"] = mass_src.where(mass_measured, density * 1_000.0 * vol_m3)

    n_meas = int(df["density_measured"].sum())
    say(f"       Density: {n_meas:,} measured  |  {len(df) - n_meas:,} estimated"
        + (f"  ({int(bad_rho.sum()):,} source densities outside their class's "
           f"possible range dropped)" if int(bad_rho.sum()) else ""))
    if int(refuted.sum()):
        say(f"       {int(refuted.sum()):,} H-derived diameters contradicted a measured "
            f"mass: {int(fits.sum()):,} re-derived from the mass, "
            f"{int(unfit.sum()):,} masses dropped")

    n_mass_meas = int(df["mass_measured"].sum())
    n_mass_der  = int(df["estimated_mass_kg"].notna().sum()) - n_mass_meas
    say(f"        Mass:    {n_mass_meas:,} measured  |  {n_mass_der:,} derived (diameter x density)")

    return df
