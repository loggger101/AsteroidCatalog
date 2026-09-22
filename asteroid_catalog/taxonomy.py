# -*- coding: utf-8 -*-
"""Bus-DeMeo taxonomy mapped to mineralogy, and the PGM enrichment layer.

`TAXONOMY_COMPOSITION` is the reference table: one entry per Bus-DeMeo and
Tholen class, each carrying a bulk density estimate and four mass fractions.
Count it rather than quoting a length here -- the ~76 figure that circulates
in the upstream project is the number of DISTINCT `spectral_type` VALUES in a
built catalog, which is a different thing and roughly twice as large.

THE FRACTIONS DO NOT SUM TO 1
AND MUST NOT BE MADE TO -- every real class sums to strictly less than one, and
the residual is what a consumer floors at a bulk-silicate value.  `Unknown` is
the deliberate exception, with all four fractions None, so the residual is the
whole body.

`PGM_ENRICHMENT_BY_TYPE` IS A VALUATION LAYER, NOT AN OBSERVATION, and it is
kept separate for that reason.  It multiplies only the platinum-group fraction
of a metal phase, by parent-body differentiation history, and a consumer
costing something other than precious metals can ignore the column entirely.
The physical half of this module stands without it.
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
# TAXONOMY & COMPOSITION LOOKUP TABLES
# ─────────────────────────────────────────────────────────────────────────────
#
# Bus-DeMeo (2009) taxonomy mapped to mineralogical composition estimates.
# Fractions are APPROXIMATE (literature mean values) and used as defaults
# when no direct measurement exists. density_est_gcm3 is the bulk estimate.

TAXONOMY_COMPOSITION: Dict[str, dict] = {

    # ── C-complex (carbonaceous) ──────────────────────────────────────────────
    "B": {
        "group": "C-complex",
        "composition": "Hydrated silicates, carbon, organics, possible ices",
        "minerals": ["phyllosilicates", "magnetite", "carbon", "organics"],
        "density_est_gcm3":  1.30,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.30,
        "carbon_fraction":   0.30,
        "ice_fraction":      0.20,
        "notes": "Bluest C-complex; possible metamorphic overprint",
    },
    "C": {
        "group": "C-complex",
        "composition": "Carbonaceous: hydrated silicates, organics, carbon",
        "minerals": ["phyllosilicates", "carbon", "organics"],
        "density_est_gcm3":  1.50,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.35,
        "carbon_fraction":   0.25,
        "ice_fraction":      0.15,
        "notes": "Most common asteroid type; CI/CM chondrite analogs",
    },
    "Cb": {
        "group": "C-complex",
        "composition": "Transitional C/B: carbonaceous, moderate hydration",
        "minerals": ["phyllosilicates", "carbon"],
        "density_est_gcm3":  1.40,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.32,
        "carbon_fraction":   0.28,
        "ice_fraction":      0.18,
        "notes": "Intermediate between B and C",
    },
    "Cg": {
        "group": "C-complex",
        "composition": "Cg-type: CM chondrite analog, strong UV dropoff",
        "minerals": ["phyllosilicates", "carbon", "magnetite"],
        "density_est_gcm3":  1.50,
        "metal_fraction":    0.02,
        "silicate_fraction": 0.38,
        "carbon_fraction":   0.22,
        "ice_fraction":      0.12,
        "notes": "Strong UV absorption feature",
    },
    "Cgh": {
        "group": "C-complex",
        "composition": "CH/CK analog: hydrated silicates, olivine",
        "minerals": ["olivine", "phyllosilicates", "magnetite"],
        "density_est_gcm3":  1.60,
        "metal_fraction":    0.03,
        "silicate_fraction": 0.40,
        "carbon_fraction":   0.20,
        "ice_fraction":      0.10,
        "notes": "0.7-μm absorption band; high water content",
    },
    "Ch": {
        "group": "C-complex",
        "composition": "CM2 analog: hydrated silicates, low albedo",
        "minerals": ["phyllosilicates", "magnetite", "carbon"],
        "density_est_gcm3":  1.50,
        "metal_fraction":    0.02,
        "silicate_fraction": 0.38,
        "carbon_fraction":   0.25,
        "ice_fraction":      0.10,
        "notes": "Strongest 0.7-μm feature in C-complex",
    },

    # ── S-complex (silicate / stony) ──────────────────────────────────────────
    "S": {
        "group": "S-complex",
        "composition": "Stony: olivine, pyroxene, nickel-iron mixture",
        "minerals": ["olivine", "pyroxene", "nickel-iron"],
        "density_est_gcm3":  2.70,
        "metal_fraction":    0.15,
        "silicate_fraction": 0.75,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Second-most common type; LL/L chondrite analogs",
    },
    "Sa": {
        "group": "S-complex",
        "composition": "S/A transitional: olivine-dominated stony",
        "minerals": ["olivine", "pyroxene"],
        "density_est_gcm3":  2.80,
        "metal_fraction":    0.12,
        "silicate_fraction": 0.80,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "High olivine / pyroxene ratio",
    },
    "Sk": {
        "group": "S-complex",
        "composition": "S/K transitional stony",
        "minerals": ["olivine", "pyroxene", "oxides"],
        "density_est_gcm3":  2.60,
        "metal_fraction":    0.10,
        "silicate_fraction": 0.78,
        "carbon_fraction":   0.02,
        "ice_fraction":      0.00,
        "notes": "Intermediate S and K spectral features",
    },
    "Sl": {
        "group": "S-complex",
        "composition": "S/L transitional: spinel-bearing stony",
        "minerals": ["olivine", "pyroxene", "spinel"],
        "density_est_gcm3":  2.70,
        "metal_fraction":    0.12,
        "silicate_fraction": 0.78,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Intermediate S and L spectral features",
    },
    "Sq": {
        "group": "S-complex",
        "composition": "S/Q transitional: LL/L ordinary chondrite analog",
        "minerals": ["olivine", "pyroxene", "nickel-iron"],
        "density_est_gcm3":  2.80,
        "metal_fraction":    0.15,
        "silicate_fraction": 0.78,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Possible fresh/unweathered S surface",
    },
    "Sr": {
        "group": "S-complex",
        "composition": "S/R transitional stony",
        "minerals": ["pyroxene", "olivine"],
        "density_est_gcm3":  2.90,
        "metal_fraction":    0.12,
        "silicate_fraction": 0.82,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Intermediate S and R spectral features",
    },
    "Sv": {
        "group": "S-complex",
        "composition": "S/V transitional stony-basaltic",
        "minerals": ["pyroxene", "olivine", "plagioclase"],
        "density_est_gcm3":  3.00,
        "metal_fraction":    0.08,
        "silicate_fraction": 0.85,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Intermediate S and V spectral features",
    },

    # ── X-complex (metallic / enstatite / primitive) ──────────────────────────
    "X": {
        "group": "X-complex",
        "composition": "X-type: possibly metallic or primitive (albedo ambiguous)",
        "minerals": ["nickel-iron", "enstatite", "troilite"],
        "density_est_gcm3":  3.30,
        "metal_fraction":    0.30,
        "silicate_fraction": 0.50,
        "carbon_fraction":   0.05,
        "ice_fraction":      0.00,
        "notes": "Requires albedo to distinguish M, E, or P sub-type.  v1.0.8: "
                 "metal 0.40 → 0.30, tracking the M revision — an unresolved "
                 "X sits between metal-rich M and near-metal-free P.",
    },
    "Xc": {
        "group": "X-complex",
        "composition": "Xc-type: low-albedo metallic, possibly carbonaceous",
        "minerals": ["carbon", "nickel-iron"],
        "density_est_gcm3":  2.50,
        "metal_fraction":    0.25,
        "silicate_fraction": 0.35,
        "carbon_fraction":   0.20,
        "ice_fraction":      0.00,
        "notes": "Low albedo suggests carbonaceous metallic mix",
    },
    "Xe": {
        "group": "X-complex",
        "composition": "Xe-type (M-type analog): metal-rich, metal-silicate mix",
        "minerals": ["nickel-iron", "troilite", "enstatite"],
        "density_est_gcm3":  3.80,
        "metal_fraction":    0.45,
        "silicate_fraction": 0.45,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "High-albedo X; metal-rich but not a bare core.  v1.0.8: "
                 "was 0.75 metal / 5.00 g/cm³ — tracked down alongside M for "
                 "the same measured-density reason.",
    },
    "Xk": {
        "group": "X-complex",
        "composition": "Xk-type: E-chondrite analog, enstatite dominant",
        "minerals": ["enstatite", "nickel-iron", "troilite"],
        "density_est_gcm3":  3.60,
        "metal_fraction":    0.25,
        "silicate_fraction": 0.65,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "E-chondrite analog; high albedo.  v1.0.8: metal 0.50 → 0.25 "
                 "— EH/EL enstatite chondrites carry ~20-25 wt% metal, and "
                 "'enstatite dominant' cannot also be half metal.",
    },

    # ── Other spectral types ──────────────────────────────────────────────────
    "A": {
        "group": "A-type",
        "composition": "Dunite/olivine-rich: possible differentiated mantle fragment",
        "minerals": ["olivine"],
        "density_est_gcm3":  3.20,
        "metal_fraction":    0.05,
        "silicate_fraction": 0.90,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Very strong 1-μm olivine band; rare type",
    },
    "D": {
        "group": "D-type",
        "composition": "Primitive: organics, anhydrous silicates, possible ices",
        "minerals": ["organics", "silicates", "carbon"],
        "density_est_gcm3":  1.20,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.25,
        "carbon_fraction":   0.30,
        "ice_fraction":      0.25,
        "notes": "Featureless red spectrum; Trojan/outer-belt analog",
    },
    "K": {
        "group": "K-type",
        "composition": "CV/CO chondrite analog: olivine, pyroxene, oxides",
        "minerals": ["olivine", "pyroxene", "magnetite"],
        "density_est_gcm3":  2.50,
        "metal_fraction":    0.08,
        "silicate_fraction": 0.72,
        "carbon_fraction":   0.08,
        "ice_fraction":      0.00,
        "notes": "Intermediate C and S features; moderate albedo",
    },
    "L": {
        "group": "L-type",
        "composition": "Spinel-bearing: anhydrous silicates, high albedo",
        "minerals": ["spinel", "olivine", "pyroxene"],
        "density_est_gcm3":  2.80,
        "metal_fraction":    0.05,
        "silicate_fraction": 0.85,
        "carbon_fraction":   0.02,
        "ice_fraction":      0.00,
        "notes": "Unusual spinel absorption; possibly CV3 chondrite",
    },
    "O": {
        "group": "O-type",
        "composition": "Olivine-orthopyroxene mixture (very rare)",
        "minerals": ["olivine", "orthopyroxene"],
        "density_est_gcm3":  2.90,
        "metal_fraction":    0.08,
        "silicate_fraction": 0.85,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Only a handful of known O-types",
    },
    "Q": {
        "group": "Q-type",
        "composition": "Ordinary chondrite: olivine, pyroxene, metal",
        "minerals": ["olivine", "pyroxene", "nickel-iron"],
        "density_est_gcm3":  3.00,
        "metal_fraction":    0.20,
        "silicate_fraction": 0.72,
        "carbon_fraction":   0.02,
        "ice_fraction":      0.00,
        "notes": "Fresh/unweathered ordinary chondrite analog",
    },
    "R": {
        "group": "R-type",
        "composition": "Olivine-pyroxene mantle fragment (rare)",
        "minerals": ["olivine", "pyroxene"],
        "density_est_gcm3":  3.10,
        "metal_fraction":    0.05,
        "silicate_fraction": 0.90,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Very rare; possible differentiated mantle fragment",
    },
    "T": {
        "group": "T-type",
        "composition": "Primitive: organics, troilite, Fe-silicates",
        "minerals": ["troilite", "organics", "silicates"],
        "density_est_gcm3":  1.80,
        "metal_fraction":    0.05,
        "silicate_fraction": 0.40,
        "carbon_fraction":   0.25,
        "ice_fraction":      0.10,
        "notes": "Featureless red; possibly primitive body",
    },
    "V": {
        "group": "V-type",
        "composition": "Basaltic crust fragment (HED meteorite analog)",
        "minerals": ["pyroxene", "plagioclase", "olivine"],
        "density_est_gcm3":  2.90,
        "metal_fraction":    0.05,
        "silicate_fraction": 0.90,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Vestoids / Vesta family; strong pyroxene bands",
    },

    # ── Tholen-only types (no direct Bus-DeMeo equivalent) ────────────────────
    # The Tholen (1984) taxonomy uses a few letters that Bus-DeMeo (2009)
    # subsequently absorbed into the X- and C-complex.  We keep them as
    # first-class entries here so the enrichment step can use a JPL
    # `spec_T` value directly when `spec_B` is empty.
    "M": {
        "group": "X-complex",
        "composition": "Metallic (Tholen): metal-silicate mix, core-fragment affinity",
        "minerals": ["nickel-iron", "troilite", "enstatite"],
        "density_est_gcm3":  3.90,
        "metal_fraction":    0.50,
        "silicate_fraction": 0.45,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Tholen M-type ≈ Bus-DeMeo Xe; high IR albedo, low optical.  "
                 "v1.0.8: was 0.80 metal / 5.30 g/cm³, the pre-Psyche "
                 "'exposed iron core' assumption.  16 Psyche's measured bulk "
                 "density is ~3.8-3.9 g/cm³ (Elkins-Tanton et al. 2020, "
                 "Siltala & Granvik 2021) — far below the 7.8 g/cm³ of iron "
                 "meteorite — and metal content is now put at roughly "
                 "30-60%.  A solid-metal M-type is not supported by any "
                 "measured density.",
    },
    "E": {
        "group": "X-complex",
        "composition": "Enstatite (Tholen): aubrite/E-chondrite analog",
        "minerals": ["enstatite", "nickel-iron"],
        "density_est_gcm3":  3.20,
        "metal_fraction":    0.10,
        "silicate_fraction": 0.85,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Tholen E-type ≈ Bus-DeMeo Xk; very high albedo (>0.3).  "
                 "v1.0.8: metal 0.30 → 0.10 — aubrites are enstatite "
                 "achondrites and are very nearly metal-free.",
    },
    "P": {
        "group": "C-complex",
        "composition": "Primitive (Tholen): low albedo, organics + silicates",
        "minerals": ["organics", "silicates", "carbon"],
        "density_est_gcm3":  1.80,
        "metal_fraction":    0.02,
        "silicate_fraction": 0.35,
        "carbon_fraction":   0.25,
        "ice_fraction":      0.15,
        "notes": "Tholen P-type ≈ Bus-DeMeo Xc / D; outer-belt primitive",
    },
    "F": {
        "group": "C-complex",
        "composition": "Flat-spectrum carbonaceous (Tholen): dehydrated CM",
        "minerals": ["phyllosilicates", "carbon"],
        "density_est_gcm3":  1.40,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.35,
        "carbon_fraction":   0.28,
        "ice_fraction":      0.15,
        "notes": "Tholen F-type ≈ Bus-DeMeo B; flat featureless spectrum",
    },
    "G": {
        "group": "C-complex",
        "composition": "G-type (Tholen): C-complex with UV dropoff",
        "minerals": ["phyllosilicates", "carbon", "magnetite"],
        "density_est_gcm3":  1.50,
        "metal_fraction":    0.02,
        "silicate_fraction": 0.38,
        "carbon_fraction":   0.22,
        "ice_fraction":      0.12,
        "notes": "Tholen G-type ≈ Bus-DeMeo Cg; Ceres-like",
    },

    # ── Fallback ──────────────────────────────────────────────────────────────
    "Unknown": {
        "group": "Unknown",
        "composition": "Unknown — insufficient spectral data",
        "minerals": [],
        "density_est_gcm3":  None,
        "metal_fraction":    None,
        "silicate_fraction": None,
        "carbon_fraction":   None,
        "ice_fraction":      None,
        "notes": "No spectral classification available",
    },
}

say(f"OK  Taxonomy lookup ready - {len(TAXONOMY_COMPOSITION)} spectral types defined")


# ─────────────────────────────────────────────────────────────────────────────
# PGM ENRICHMENT BY SPECTRAL TYPE  (v1.0.4)
# ─────────────────────────────────────────────────────────────────────────────
# Multiplier applied to the platinum-group-metal (PGM) yields in Module 2's
# "nickel-iron" mineral when valuing an asteroid of this spectral type.
# Baseline 1.0× is calibrated to chondritic / mean-iron-meteorite PGM
# concentration (~37 ppm total PGM+Au in nickel-iron alloy).
#
# Why per-type variation matters:
#   • Differentiated parent bodies (M-type / Xe / E asteroids, fragments
#     of cores or near-core regions) concentrated PGMs into the metal
#     phase during melting, so their nickel-iron grains have ELEVATED PGM
#     vs chondritic average.
#   • Basaltic-crust fragments (V-type, Vesta family) lost their PGM to
#     the core during their parent body's differentiation; their metal
#     grains are PGM-DEPLETED.
#   • Mantle fragments (A, R, O) sit between, partially depleted.
#   • Primitive bodies (C-complex, ordinary chondrites) never differentiated,
#     so PGMs remained uniformly distributed in metal grains → baseline.
#
# These factors only multiply the RARE-METAL portion (Pt, Pd, Ru, Ir, Os,
# Rh, Au) of the nickel-iron yield in Module 4; base metals (Fe, Ni, Co)
# are unaffected.  Conservative midpoints; the literature variance is huge
# (iron meteorite Ir alone ranges 0.01-19 ppm).

PGM_ENRICHMENT_BY_TYPE: Dict[str, float] = {
    # ── Differentiated core fragments, PGMs concentrated by metal-segregation ──
    "M":  2.0,   # Tholen metallic (e.g. 16 Psyche)
    "Xe": 2.0,   # Bus-DeMeo M-analog
    "Xk": 1.5,   # E-chondrite / aubrite analog, partial differentiation
    "X":  1.5,   # X-complex ambiguous (assume partial)
    "Xc": 1.2,   # low-albedo X: partially carbonaceous
    "E":  1.5,   # Tholen enstatite, aubrite analog

    # ── Mantle / lower-mantle fragments: partial PGM depletion ──
    "A":  0.5,   # dunite, olivine-dominated mantle
    "R":  0.5,   # olivine-pyroxene mantle fragment
    "O":  0.5,   # olivine-orthopyroxene (rare, ureilite-class)

    # ── Basaltic crust, PGMs largely extracted into core during differentiation ──
    "V":  0.2,   # Vesta family / HED meteorite analog

    # ── Everything else: baseline 1.0× (chondritic / primitive: get via .get default) ──
    # C, Cb, Cg, Cgh, Ch, B, S, Sa, Sk, Sl, Sq, Sr, Sv, Q, K, L, D, T, P, F, G, Unknown
}


def _by_distinct(col: "pd.Series", fn):
    """`col.apply(fn)` evaluated once per DISTINCT value instead of per row.

    v1.1.1.  Everything this module derives from `spectral_type` is a lookup
    keyed on a taxonomy class, and there are **76 distinct classes across
    1,555,667 rows**, so twelve `.apply()` passes (nine composition fields,
    two capitalisation passes, and the PGM multiplier) were making ~19 million
    calls to produce ~800 answers.  Each of those calls ran `pd.isna` on a
    scalar, which is a pandas dispatch at ~1 µs.  Measured on the real
    1,555,667-row catalog, `enrich_composition` goes **9.09 s -> 2.35 s
    (3.87x)**; that is the whole function, of which the rest (the Tholen and
    albedo fallbacks, the masks, the counts) is unchanged.

    Same finding, and the same fix, as `_parse_minerals_column` in Stage 4, 
    which is the point: the pattern is "a column with few distinct values, one
    Python call per row", and this pipeline has it in both directions.

    `factorize` rather than `unique` + a dict because it is total: NaN is a
    code like any other, so a missing taxonomy cannot fall through a lookup
    that `nan != nan` would silently break.

    ⚠️  The result array is built with `np.empty(..., dtype=object)` and filled,
    NOT `np.array([...])`.  Some of these fields are LISTS (`comp_minerals`),
    and `np.array` of equal-length lists builds a 2-D array instead of an array
    of lists, which would reshape the column rather than fill it.

    ⚠️  `.infer_objects()` at the end is NOT cosmetic, and leaving it off is
    how this change failed its first verification. `Series.apply()` builds its
    result through `maybe_convert_objects`, so a column of floats-and-`None`
    comes back **float64 with NaN**, and a column of floats comes back
    float64 rather than object. Filling an object array and stopping there
    keeps `None` as `None` and the dtype as `object`: 53 rows of
    `comp_metal_fraction` differed on exactly that, and `comp_pgm_enrichment`
    changed dtype under a column whose values were all equal. `infer_objects`
    runs the same conversion `apply` does, so lists stay lists, strings stay
    strings, and the numeric columns land where they always did.

    ⚠️  Values are SHARED across rows that share a class, exactly as
    `.apply()` shared them: `_lookup` returns the object straight out of
    `TAXONOMY_COMPOSITION`, so every C-type row already pointed at one list.
    Stage 1 writes this to CSV and never mutates it.  (Stage 4 re-reads it and
    deliberately does NOT share; see `_parse_minerals_column`.)
    """
    codes, uniques = pd.factorize(col, use_na_sentinel=False)
    resolved = np.empty(len(uniques), dtype=object)
    for i, u in enumerate(uniques):
        resolved[i] = fn(u)
    return pd.Series(resolved[codes], index=col.index,
                     name=col.name).infer_objects()


def pgm_enrichment_for_type(spec_type) -> float:
    """Return the PGM enrichment multiplier for a Bus-DeMeo / Tholen type.

    Default 1.0 (chondritic) for unknown / unlisted types.  Falls back to
    first-character match (e.g. unknown sub-type 'Mq' → 'M' → 2.0) so
    minor sub-type variants inherit the parent class's enrichment.
    """
    if spec_type is None or (isinstance(spec_type, float) and pd.isna(spec_type)):
        return 1.0
    s = str(spec_type).strip()
    if not s:
        return 1.0
    if s in PGM_ENRICHMENT_BY_TYPE:
        return PGM_ENRICHMENT_BY_TYPE[s]
    # Fallback to first letter (e.g. 'Sq2' → 'S' → 1.0)
    return PGM_ENRICHMENT_BY_TYPE.get(s[0], 1.0)


say(f"OK  PGM enrichment table ready - "
      f"{len(PGM_ENRICHMENT_BY_TYPE)} non-baseline spectral types "
      f"(M / Xe = 2.0x, V = 0.2x, A / R / O = 0.5x, others 1.0x)")
