# -*- coding: utf-8 -*-
"""Bus-DeMeo taxonomy mapped to mineralogy, and the PGM enrichment layer.

`TAXONOMY_COMPOSITION` is the reference table: one entry per Bus-DeMeo and
Tholen class, each carrying a bulk density estimate and four mass fractions.
Count it rather than quoting a length here -- the ~76 figure that circulates
in the upstream project is the number of DISTINCT `spectral_type` VALUES in a
built catalog, which is a different thing and roughly twice as large.

THE FRACTIONS DO NOT SUM TO 1 AND MUST NOT BE MADE TO -- every real class sums
to strictly less than one, and the residual is what a consumer floors at a
bulk-silicate value.  `Unknown` is the deliberate exception, with all four
fractions None, so the residual is the whole body.

`PGM_ENRICHMENT_BY_TYPE` IS A VALUATION LAYER, NOT AN OBSERVATION, and it is
kept separate for that reason.  It multiplies only the platinum-group fraction
of a metal phase, by parent-body differentiation history, and a consumer
costing something other than precious metals can ignore the column entirely.
The physical half of this module stands without it.
"""

from typing import Dict

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# TAXONOMY & COMPOSITION LOOKUP TABLES
# ─────────────────────────────────────────────────────────────────────────────
#
# Bus-DeMeo (2009) taxonomy mapped to mineralogical composition estimates.
# Fractions are APPROXIMATE and used as defaults when no direct measurement
# exists. density_est_gcm3 is the bulk estimate.
#
# WHERE A NUMBER HAS A SOURCE, THIS IS IT  (data contract 1.5.0):
#
#   carbon, hydrated C-complex    0.04.  CI chondrites carry 3.5-3.9 wt% C
#     (B C Cb Cg Cgh Ch F G)      (Pearson et al. 2006, MAPS 41, 1899); the
#                                 returned samples of Bennu 4.5-4.7 wt% and
#                                 Ryugu ~4.0 (Lauretta et al. 2024, MAPS).
#                                 Until 1.5.0 these read 0.20-0.30, five to
#                                 seven times any measurement.  Three more
#                                 routes agree (1.6.0): Lodders (2010) Table
#                                 2, CI 34,800 +/- 3,500 ppm = 3.48 wt%;
#                                 Glavin et al. (2025, Nat. Astron. 9, 199)
#                                 re-measured Bennu at 4.5-4.7 wt% on their
#                                 own extracts; Yokoyama et al. (2023,
#                                 Science 379, eabn7850) Ryugu 4.63 +/- 0.23
#                                 wt% (read in General_Research R73, not
#                                 re-read here).
#   metal, S-complex and Q        0.06, the mean of LL (3.56 wt%) and L (8.33)
#                                 chondrite Fe-Ni-Co metal (Jarosewich 1990,
#                                 Meteoritics 25, 323), the analogues these
#                                 rows name; Kargel (1994, JGR 99, 21129)
#                                 gives LL 1.2-5.3%, and the Itokawa sample
#                                 is LL.  Until 1.5.0 S read 0.15 and Q 0.20,
#                                 which is H-chondrite metal (17.8) or more.
#   metal, V                      0.01.  Eucrites are the most siderophile-
#                                 depleted achondrites and carry trace metal.
#   Xe / Xk                       swapped in 1.5.0; see those rows.
#   density, P                    1.20 (1.6.0; was 1.80): the P-types measured
#                                 average 1.16 +/- 0.26 (Hanus et al. 2017,
#                                 Carry 2012, Kretlow 2022); DENSITY_EVIDENCE.
#   density, Q                    2.70 (1.6.0; was 3.00): S's value, the same
#                                 ordinary-chondrite analogue; see the Q row.
#   X and Xc                      split by albedo into P, M and E (1.6.0), and
#                                 each row the mixture of the three for a body
#                                 with no albedo; see X_SPLIT_BOUNDS.
#   density_est_gcm3              checked against Carry (2012) Table 3 in
#                                 DENSITY_EVIDENCE below, which says where
#                                 each class sits against measured bodies, and
#                                 against its meteorite analogue's bulk
#                                 density (Carry 2012 Table 2), which no
#                                 asteroid can exceed.  tools/density_evidence.py
#                                 holds it to a built catalog's own masses.
#
# WHAT HAS NO SOURCE: the silicate fractions, carbon for D, Z, T, P, K and the
# X-complex, and every ice fraction.  No meteorite constrains ice at all:
# CI/CM chondrites and the Bennu and Ryugu samples hold their water in
# hydrated minerals, not as ice, so an inner-belt C-type's ice_fraction is a
# guess about its interior, not a reading of its analogue.

TAXONOMY_COMPOSITION: Dict[str, dict] = {

    # ── C-complex (carbonaceous) ──────────────────────────────────────────────
    "B": {
        "group": "C-complex",
        "composition": "Hydrated silicates, carbon, organics, possible ices",
        "minerals": ["phyllosilicates", "magnetite", "carbon", "organics"],
        "density_est_gcm3":  1.30,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.30,
        "carbon_fraction":   0.04,
        "ice_fraction":      0.20,
        "notes": "Bluest C-complex; possible metamorphic overprint.  v1.5.0: "
                 "carbon 0.30 -> 0.04, as C.  Density 1.30 is the small-body "
                 "value (Bennu, B, 1.19); large B-types run higher (Pallas "
                 "2.86, Interamnia 1.96).",
    },
    "C": {
        "group": "C-complex",
        "composition": "Carbonaceous: hydrated silicates, organics, carbon",
        "minerals": ["phyllosilicates", "carbon", "organics"],
        "density_est_gcm3":  1.50,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.35,
        "carbon_fraction":   0.04,
        "ice_fraction":      0.15,
        "notes": "Most common asteroid type; CI/CM chondrite analogs.  v1.5.0: "
                 "carbon 0.25 -> 0.04: CI chondrites carry 3.5-3.9 wt% C, the "
                 "Bennu sample 4.5-4.7 and Ryugu ~4.0.",
    },
    "Cb": {
        "group": "C-complex",
        "composition": "Transitional C/B: carbonaceous, moderate hydration",
        "minerals": ["phyllosilicates", "carbon"],
        "density_est_gcm3":  1.40,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.32,
        "carbon_fraction":   0.04,
        "ice_fraction":      0.18,
        "notes": "Intermediate between B and C.  v1.5.0: carbon 0.28 -> 0.04, as C.",
    },
    "Cg": {
        "group": "C-complex",
        "composition": "Cg-type: CM chondrite analog, strong UV dropoff",
        "minerals": ["phyllosilicates", "carbon", "magnetite"],
        "density_est_gcm3":  1.50,
        "metal_fraction":    0.02,
        "silicate_fraction": 0.38,
        "carbon_fraction":   0.04,
        "ice_fraction":      0.12,
        "notes": "Strong UV absorption feature.  v1.5.0: carbon 0.22 -> 0.04, as C.",
    },
    "Cgh": {
        "group": "C-complex",
        "composition": "CH/CK analog: hydrated silicates, olivine",
        "minerals": ["olivine", "phyllosilicates", "magnetite"],
        "density_est_gcm3":  1.60,
        "metal_fraction":    0.03,
        "silicate_fraction": 0.40,
        "carbon_fraction":   0.04,
        "ice_fraction":      0.10,
        "notes": "0.7-μm absorption band; high water content.  v1.5.0: carbon "
                 "0.20 -> 0.04, as C.",
    },
    "Ch": {
        "group": "C-complex",
        "composition": "CM2 analog: hydrated silicates, low albedo",
        "minerals": ["phyllosilicates", "magnetite", "carbon"],
        "density_est_gcm3":  1.50,
        "metal_fraction":    0.02,
        "silicate_fraction": 0.38,
        "carbon_fraction":   0.04,
        "ice_fraction":      0.10,
        "notes": "Strongest 0.7-μm feature in C-complex.  v1.5.0: carbon 0.25 "
                 "-> 0.04, as C.",
    },

    # ── S-complex (silicate / stony) ──────────────────────────────────────────
    "S": {
        "group": "S-complex",
        "composition": "Stony: olivine, pyroxene, nickel-iron mixture",
        "minerals": ["olivine", "pyroxene", "nickel-iron"],
        "density_est_gcm3":  2.70,
        "metal_fraction":    0.06,
        "silicate_fraction": 0.75,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Second-most common type; LL/L chondrite analogs.  v1.5.0: "
                 "metal 0.15 -> 0.06, the mean of LL (3.56 wt%) and L (8.33 wt%) "
                 "chondrite metal; 0.15 was H-chondrite metal.  Density 2.70 is "
                 "the large-body value (Carry 2012: 2.72 +/- 0.54, 11 bodies); "
                 "sub-km S-type NEAs run lower, a Yarkovsky median of 1.37 over "
                 "23 (Dziadura et al. 2023), as rubble piles do.",
    },
    "Sa": {
        "group": "S-complex",
        "composition": "S/A transitional: olivine-dominated stony",
        "minerals": ["olivine", "pyroxene"],
        "density_est_gcm3":  2.80,
        "metal_fraction":    0.06,
        "silicate_fraction": 0.80,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "High olivine / pyroxene ratio.  v1.5.0: metal 0.12 -> 0.06, as S.",
    },
    "Sk": {
        "group": "S-complex",
        "composition": "S/K transitional stony",
        "minerals": ["olivine", "pyroxene", "oxides"],
        "density_est_gcm3":  2.60,
        "metal_fraction":    0.06,
        "silicate_fraction": 0.78,
        "carbon_fraction":   0.02,
        "ice_fraction":      0.00,
        "notes": "Intermediate S and K spectral features.  v1.5.0: metal 0.10 -> "
                 "0.06, as S.",
    },
    "Sl": {
        "group": "S-complex",
        "composition": "S/L transitional: spinel-bearing stony",
        "minerals": ["olivine", "pyroxene", "spinel"],
        "density_est_gcm3":  2.70,
        "metal_fraction":    0.06,
        "silicate_fraction": 0.78,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Intermediate S and L spectral features.  v1.5.0: metal 0.12 -> "
                 "0.06, as S.",
    },
    "Sq": {
        "group": "S-complex",
        "composition": "S/Q transitional: LL/L ordinary chondrite analog",
        "minerals": ["olivine", "pyroxene", "nickel-iron"],
        "density_est_gcm3":  2.80,
        "metal_fraction":    0.06,
        "silicate_fraction": 0.78,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Possible fresh/unweathered S surface.  v1.5.0: metal 0.15 -> "
                 "0.06, as S.  Density 2.80 is below the two large Sq-types "
                 "measured to 20% (3.43); small ones are rubble (Itokawa 1.9).",
    },
    "Sr": {
        "group": "S-complex",
        "composition": "S/R transitional stony",
        "minerals": ["pyroxene", "olivine"],
        "density_est_gcm3":  2.90,
        "metal_fraction":    0.06,
        "silicate_fraction": 0.82,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Intermediate S and R spectral features.  v1.5.0: metal 0.12 -> "
                 "0.06, as S.",
    },
    "Sv": {
        "group": "S-complex",
        "composition": "S/V transitional stony-basaltic",
        "minerals": ["pyroxene", "olivine", "plagioclase"],
        "density_est_gcm3":  3.00,
        "metal_fraction":    0.06,
        "silicate_fraction": 0.85,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Intermediate S and V spectral features.  v1.5.0: metal 0.08 -> "
                 "0.06, as S.",
    },

    # ── X-complex (metallic / enstatite / primitive) ──────────────────────────
    # X and Xc apply only to a body with NO measured albedo; one with an albedo
    # takes P, M or E (X_SPLIT_BOUNDS below).  So each is the mixture of those
    # three, as the bodies with that label and an albedo divide: the density
    # number-weighted, the fractions mass-weighted (X_SPLIT_COUNTS; a test
    # recomputes them).
    "X": {
        "group": "X-complex",
        "composition": "X-type of unknown albedo: primitive (P), metal-rich (M) "
                       "or enstatite (E), weighted as the X-types with an albedo divide",
        "minerals": ["nickel-iron", "enstatite", "troilite"],
        "density_est_gcm3":  2.29,
        "metal_fraction":    0.33,
        "silicate_fraction": 0.44,
        "carbon_fraction":   0.08,
        "ice_fraction":      0.05,
        "notes": "Requires albedo to distinguish M, E, or P sub-type.  v1.6.0: "
                 "a body with a measured albedo now takes P, M or E by "
                 "Tholen's cuts (0.10, 0.30); this row is the mixture of the "
                 "three for one without, 58% P, 37% M and 4% E by count "
                 "(density 3.30 -> 2.29).  Carry (2012) averages X at 1.85 "
                 "+/- 0.81, and Berthier et al. (2023) find X densities "
                 "bimodal by albedo.",
    },
    "Xc": {
        "group": "X-complex",
        "composition": "Xc-type of unknown albedo: mostly primitive (P), some "
                       "metal-rich (M) or enstatite (E), as the Xc-types with an albedo divide",
        "minerals": ["carbon", "nickel-iron"],
        "density_est_gcm3":  2.37,
        "metal_fraction":    0.32,
        "silicate_fraction": 0.47,
        "carbon_fraction":   0.08,
        "ice_fraction":      0.04,
        "notes": "v1.5.0 raised the density 2.50 -> 3.30 on Carry (2012)'s two "
                 "Xc-types, 4.86 +/- 0.81.  v1.6.0: a body with a measured "
                 "albedo takes P, M or E; this row is their mixture for one "
                 "without, 54% P, 36% M and 9% E by count (density 2.37).  The "
                 "five Xc-types data-2026-09-26b has masses for to 20% run "
                 "1.02-2.08, and SsODNet's mass for Hestia now gives 1.11, not "
                 "Carry's 5.81.",
    },
    "Xe": {
        "group": "X-complex",
        "composition": "Xe-type (E-type analog): enstatite-rich, 0.49-μm sulfide band",
        "minerals": ["enstatite", "nickel-iron", "troilite"],
        "density_est_gcm3":  2.90,
        "metal_fraction":    0.25,
        "silicate_fraction": 0.65,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "v1.5.0: swapped with Xk.  Xe's 0.49-μm band is the sulfide "
                 "band of Angelina-like E-types, and Carry (2012) pairs Xe with "
                 "EH enstatite chondrites, so Xe is the enstatite class; "
                 "until 1.5.0 it carried the M-type row.  Density 2.90: "
                 "enstatite chondrites average 3.55 in bulk (Macke et al. 2010) "
                 "less an S-type's macroporosity, and Carry (2012) has Xe at "
                 "2.60-2.91.  Metal 0.25: EH/EL chondrites carry ~20-25 wt%.",
    },
    "Xk": {
        "group": "X-complex",
        "composition": "Xk-type (M-type analog): metal-rich, metal-silicate mix",
        "minerals": ["nickel-iron", "troilite", "enstatite"],
        "density_est_gcm3":  3.80,
        "metal_fraction":    0.45,
        "silicate_fraction": 0.45,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "v1.5.0: swapped with Xe.  13 of 24 Tholen M-types are Xk "
                 "(Fornasier et al. 2010), 16 Psyche among them, so Xk is the "
                 "metal-rich class; until 1.5.0 it carried the enstatite row.  "
                 "Density 3.80: Psyche 3.8-4.2, Carry (2012) Xk 3.79-4.22.  "
                 "Metal-rich but not a bare core: v1.0.8 (then as Xe) took it "
                 "down from 0.75 metal / 5.00 g/cm³ alongside M.",
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
    "Z": {
        "group": "D-type",
        "composition": "Very red primitive: organics, anhydrous silicates, possible ices",
        "minerals": ["organics", "silicates", "carbon"],
        "density_est_gcm3":  1.20,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.25,
        "carbon_fraction":   0.30,
        "ice_fraction":      0.25,
        "notes": "Mahlke et al. (2022) Z: redder than D, D-like; composition "
                 "taken as D.  v1.4.0: until then Z fell to Unknown, and 32 "
                 "bodies (Trojans such as 1172 Aneas, 118 km) carried no mass.",
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
        "density_est_gcm3":  2.70,
        "metal_fraction":    0.06,
        "silicate_fraction": 0.72,
        "carbon_fraction":   0.02,
        "ice_fraction":      0.00,
        "notes": "Fresh/unweathered ordinary chondrite analog.  v1.5.0: metal "
                 "0.20 -> 0.06, as S: more than H-chondrite metal was no LL/L "
                 "chondrite.  v1.6.0: density 3.00 -> 2.70, as S: Q is an "
                 "unweathered S surface, not a denser body, and 3.00 was denser "
                 "than every Q-type density published; the 9 Q-type NEAs with "
                 "Yarkovsky densities have a median of 1.47, at most 2.79 "
                 "(Dziadura et al. 2023).",
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
        "metal_fraction":    0.01,
        "silicate_fraction": 0.90,
        "carbon_fraction":   0.01,
        "ice_fraction":      0.00,
        "notes": "Vestoids / Vesta family; strong pyroxene bands.  v1.5.0: metal "
                 "0.05 -> 0.01; eucrites carry trace metal only.",
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
        "notes": "Tholen M-type ≈ Bus-DeMeo Xk (13 of 24, Fornasier et al. "
                 "2010; until 1.5.0 this said Xe); moderate albedo.  "
                 "v1.0.8: was 0.80 metal / 5.30 g/cm³, the pre-Psyche "
                 "'exposed iron core' assumption.  16 Psyche's measured bulk "
                 "density is 3.8-4.2 g/cm³ (Elkins-Tanton et al. 2020; "
                 "Siltala & Granvik 2021, 3.88 +/- 0.25; Farnocchia et al. "
                 "2024, 4.17 +/- 0.15) — far below the 7.8 g/cm³ of iron "
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
        "notes": "Tholen E-type ≈ Bus-DeMeo Xe (the 0.49-μm band; until 1.5.0 "
                 "this said Xk); very high albedo (>0.3).  "
                 "v1.0.8: metal 0.30 → 0.10 — aubrites are enstatite "
                 "achondrites and are very nearly metal-free.",
    },
    "P": {
        "group": "C-complex",
        "composition": "Primitive (Tholen): low albedo, organics + silicates",
        "minerals": ["organics", "silicates", "carbon"],
        "density_est_gcm3":  1.20,
        "metal_fraction":    0.02,
        "silicate_fraction": 0.35,
        "carbon_fraction":   0.25,
        "ice_fraction":      0.15,
        "notes": "Tholen P-type ≈ Bus-DeMeo Xc / D; outer-belt primitive.  "
                 "v1.6.0: density 1.80 -> 1.20.  The P-types measured are "
                 "light: 87 Sylvia 1.39 +/- 0.08 (Hanus et al. 2017), 617 "
                 "Patroclus 0.88 +/- 0.17 (Carry 2012), 223 Rosa 1.2 +/- 0.5 "
                 "(Kretlow 2022, who calls ~1.3 typical of P).",
    },
    "F": {
        "group": "C-complex",
        "composition": "Flat-spectrum carbonaceous (Tholen): dehydrated CM",
        "minerals": ["phyllosilicates", "carbon"],
        "density_est_gcm3":  1.40,
        "metal_fraction":    0.01,
        "silicate_fraction": 0.35,
        "carbon_fraction":   0.04,
        "ice_fraction":      0.15,
        "notes": "Tholen F-type ≈ Bus-DeMeo B; flat featureless spectrum.  "
                 "v1.5.0: carbon 0.28 -> 0.04, as C.",
    },
    "G": {
        "group": "C-complex",
        "composition": "G-type (Tholen): C-complex with UV dropoff",
        "minerals": ["phyllosilicates", "carbon", "magnetite"],
        "density_est_gcm3":  1.50,
        "metal_fraction":    0.02,
        "silicate_fraction": 0.38,
        "carbon_fraction":   0.04,
        "ice_fraction":      0.12,
        "notes": "Tholen G-type ≈ Bus-DeMeo Cg; Ceres-like.  v1.5.0: carbon 0.22 "
                 "-> 0.04, as C.",
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

# ─────────────────────────────────────────────────────────────────────────────
# DENSITY EVIDENCE  (1.5.0; second routes 1.6.0)
# ─────────────────────────────────────────────────────────────────────────────
# What measured bodies say about each class's `density_est_gcm3`, so the
# estimate can be held to it (tests/test_traps.py).  `carry2012` is the class
# average over the densities known to 20% or better, (mean, sigma, N), from
# Carry (2012, Planet. Space Sci. 73, 98), Table 3: the tier worth testing
# against.  Where Carry has no class average (P, a Tholen class), `measured`
# is the same statistic, mean and sample standard deviation, over the
# `bodies` listed, and a test recomputes it from them.  `bodies` are
# individual densities, from Carry's Table 1 unless a later reference is
# named.  `small` is what sub-km NEAs of the class measure, (median, min, max,
# N): Yarkovsky densities from Gaia DR3 astrometry (Dziadura et al. 2023, A&A
# 680, A77, Table A.1, as read in General_Research R73), a method independent
# of every mass above and good to 30-60% per body, so it is for reading.
#
# Two more routes hold the same numbers from outside this table:
#   * METEORITE_ANALOGUE_GCM3 below: no class may be denser than the meteorite
#     it is matched to, a bound from laboratory densities, not asteroids.
#   * tools/density_evidence.py <catalog>: the same rule against the bodies a
#     built catalog has masses for, grouped by the row each body's
#     composition is read from, so a dark X-type counts toward P (SsODNet's
#     masses are newer than Carry's).  On data-2026-09-26b every row it can
#     test (N >= 3) passes; before the X split (1.6.0) Xc failed.
#
# THE ESTIMATE MAY SIT BELOW A CLASS AVERAGE, NOT ABOVE IT.  Carry finds C- and
# S-complex density rising with size, and the bodies measured to 20% are
# overwhelmingly large, while the estimate sizes the ~1.4 M small bodies that
# have no mass.  So the rule is:
#
#   estimate <= mean + 2 sigma     always: denser than the measured bodies of
#                                  its class is not an estimate anyone made
#   estimate >= mean - 2 sigma     unless `below_because` says why the
#                                  measured bodies do not speak for the small
#                                  ones the estimate sizes
#
# Carry's D-type average (9.56, three bodies at any precision) is not
# physical and is not used.
DENSITY_EVIDENCE: Dict[str, dict] = {
    # Eros twice: Carry divides NEAR's mass by a sphere of the 16.2 km mean
    # diameter; NEAR's shape volume (16.84 km volume-equivalent) gives 2.67
    # (Veverka et al. 2000, as Hanus et al. 2017 Table 6 has it).  One mass,
    # and (16.84/16.2)**3 = 1.12 between them.  data-2026-09-26b has 2.34,
    # on SsODNet's 17.6 km.
    "S":  {"carry2012": (2.72, 0.54, 11),
           "bodies": [("433 Eros", 3.00, 0.08), ("433 Eros", 2.67, 0.10),
                      ("243 Ida", 2.35, 0.29), ("25143 Itokawa", 1.91, 0.21)],
           "small": (1.37, 0.73, 3.70, 23)},
    # No class average at any precision (Carry 2012 Table 3 has no Q density).
    # Q is an unweathered S surface, so it takes S's value.  The densest of
    # the NEAs below, 1862 Apollo at 2.79 +0.41/-0.51, is within its error of
    # it; SsODNet's own density for Apollo is 2.05 +/- 0.35 (Ford et al.
    # 2014).  data-2026-09-26b has 3.70, that mass over a 1981 radar
    # diameter of 1.2 km.
    "Q":  {"small": (1.47, 0.61, 2.79, 9)},
    "Sq": {"carry2012": (3.43, 0.20, 2),
           "bodies": [("3 Juno", 3.68, 0.62), ("11 Parthenope", 3.27, 0.41)],
           "below_because": "the two Sq-types known to 20% are large (Juno "
                            "242 km, Parthenope 151 km); small "
                            "S-types are rubble piles, Itokawa 1.9 +/- 0.13 "
                            "(Fujiwara et al. 2006)"},
    "B":  {"carry2012": (2.38, 0.45, 2),
           "bodies": [("2 Pallas", 2.86, 0.32), ("704 Interamnia", 1.96, 0.28),
                      ("101955 Bennu", 1.190, 0.013),    # Lauretta et al. 2019
                      # the same body from its Yarkovsky drift, published
                      # before the spacecraft arrived (Chesley et al. 2014,
                      # Icarus 235, 5); the two agree to 1 sigma
                      ("101955 Bennu", 1.26, 0.07)],
           "below_because": "Carry's B-types known to 20% are large (Pallas "
                            "514 km, Interamnia 317 km); the small B measured "
                            "by spacecraft, Bennu, "
                            "is 1.190 +/- 0.013 (Lauretta et al. 2019)"},
    "C":  {"carry2012": (1.33, 0.58, 5),
           "bodies": [("1 Ceres", 2.13, 0.15), ("45 Eugenia", 1.34, 0.29),
                      ("90 Antiope", 0.86, 0.06)]},
    "Cb": {"carry2012": (1.25, 0.21, 3),
           "bodies": [("253 Mathilde", 1.32, 0.20), ("762 Pulcova", 1.00, 0.14)]},
    "Ch": {"carry2012": (1.41, 0.29, 9),
           "bodies": [("41 Daphne", 2.03, 0.32), ("121 Hermione", 1.27, 0.22),
                      ("130 Elektra", 1.84, 0.22)]},
    # The X complex is two populations.  Berthier et al. (2023, A&A 671, A151,
    # Fig. 5) find its densities bimodal: the dark P sub-class (mean p_V
    # 0.044) below 2 g/cm3, the M sub-class (0.129) above.  Carry's X average
    # mixes them, and so, since 1.6.0, does this row, which applies only to an
    # X-type with no albedo (X_SPLIT_BOUNDS).  The bodies below show the split:
    # Sylvia and Camilla dark and light, Kalliope moderate and dense.
    "X":  {"carry2012": (1.85, 0.81, 8),
           "bodies": [("87 Sylvia", 1.31, 0.15), ("107 Camilla", 2.28, 0.29),
                      ("22 Kalliope", 4.40, 0.46)]},   # Ferrais et al. 2022
    # Carry's two Xc-types are Klotho (which newer sources class M) and Hestia
    # at his confidence rank E, the lowest.  SsODNet's current mass for
    # Hestia, 1.17e18 kg from nine ephemeris and deflection solutions
    # (2001-2026), gives 1.11 +/- 0.31, not 5.81; SsODNet now classes it P.
    "Xc": {"carry2012": (4.86, 0.81, 2),
           "bodies": [("97 Klotho", 4.16, 0.62), ("46 Hestia", 5.81, 0.87),
                      ("46 Hestia", 1.11, 0.31)],     # SsODNet, 2026-09-27
           "below_because": "Carry's average is two bodies, one of them "
                            "Hestia at his lowest confidence rank, which "
                            "SsODNet's newer mass puts at 1.11 +/- 0.31; the "
                            "five Xc-types data-2026-09-26b has masses for to "
                            "20% run 1.02-2.08; and the row is the albedo "
                            "mixture of P, M and E, mostly P"},
    "Xe": {"carry2012": (2.60, 0.20, 1),
           "bodies": [("3169 Ostro", 2.59, 0.20), ("216 Kleopatra", 4.27, 0.86)]},
    "Xk": {"carry2012": (4.22, 0.65, 3),
           "bodies": [("16 Psyche", 3.38, 1.16), ("21 Lutetia", 3.44, 0.52),
                      # Psyche since, by three routes that agree: 3.88 +/-
                      # 0.25 from ten close encounters (Siltala & Granvik
                      # 2021, ApJL 909, L14); 4.17 +/- 0.15 from Gaia-era
                      # astrometry, GM 1.601 km3/s2 over 5.75e6 km3
                      # (Farnocchia et al. 2024, AJ 168, 21); and SsODNet's
                      # best estimate in data-2026-09-26b, 4.14.
                      ("16 Psyche", 3.88, 0.25), ("16 Psyche", 4.17, 0.15)]},
    "K":  {"carry2012": (3.54, 0.21, 1),
           "bodies": [("15 Eunomia", 3.54, 0.20)],
           "below_because": "one body: 15 Eunomia, 256 km, which other "
                            "catalogs class S.  The estimate is the CV/CO "
                            "analogue (bulk 2.79/3.03, Carry 2012 Table 2) "
                            "at an S-type's 16-20% macroporosity, 2.2-2.5; the "
                            "one small K-type with a density, 2100 Ra-Shalom "
                            "(2.3 km), is 1.28 +0.33/-0.51 (Dziadura et al. "
                            "2023)"},
    # Tholen P, no Bus-DeMeo class, so no Carry average: `measured` is the
    # mean and standard deviation of these three, the P-types with a published
    # density (Patroclus's is the system's mass over its volume-equivalent
    # 143 km).  Their precision-weighted mean is 1.30, and Kretlow (2022)
    # calls ~1.3 typical of P.  SsODNet's current values for the five Mahlke
    # P-types with a density known to 30% agree: Sylvia 1.37, Eurybates 0.86,
    # Aspasia 1.02, Cybele 1.51, Hestia 1.11 (ssoCards read 2026-09-27).
    "P":  {"measured": (1.16, 0.26, 3),
           "bodies": [("87 Sylvia", 1.39, 0.08),        # Hanus et al. 2017
                      ("617 Patroclus", 0.88, 0.17),     # Carry 2012
                      ("223 Rosa", 1.2, 0.5)]},          # Kretlow 2022
    "V":  {"carry2012": (1.93, 1.07, 3),
           "bodies": [("4 Vesta", 3.58, 0.15), ("809 Lundia", 1.64, 0.10),
                      ("854 Frostia", 0.88, 0.13)]},
}

# ─────────────────────────────────────────────────────────────────────────────
# METEORITE ANALOGUES  (1.6.0)
# ─────────────────────────────────────────────────────────────────────────────
# The bulk density of the meteorite each class is matched to, from Carry
# (2012) Table 2, which compiles laboratory measurements (Britt & Consolmagno
# 2003; Consolmagno et al. 2008; Macke et al. 2010, 2011; ordinary chondrites
# from falls only).  A meteorite's BULK density already counts its
# microporosity, and an asteroid built of it adds macroporosity, so
#
#     rho_asteroid = rho_meteorite * (1 - macroporosity),   macroporosity >= 0
#
# and NO ESTIMATE MAY EXCEED ITS ANALOGUE (tests/test_traps.py).  That is a
# second route to the same numbers, from laboratory samples rather than
# asteroid masses.  The analogue is the one the row names, or Carry's Table 3
# pairing where it names none; where a row names two, or only "ordinary
# chondrite", the denser, so the bound is the loose one.  The last column is
# the macroporosity the estimate implies, which is how the table reads.  Two
# bodies measured by spacecraft say the same: S at 20% is Eros's, 2.67
# against L's 3.36 (21%), and C, Cb, Cg, Ch and Cgh at 33-44% bracket
# Bennu's 40 +/- 10% against its likely analogues (Chesley et al. 2014).
#
#   class: (analogue, bulk g/cm3, 1 sigma)        implied macroporosity
#
# Two classes have none: Carry pairs T with an ataxite iron, which the T row
# does not model, and Unknown has no estimate.  (X read 3.30 until 1.6.0,
# above the CV Carry pairs it with; its albedo mixture is under it.)
METEORITE_ANALOGUE_GCM3: Dict[str, tuple] = {
    "X":   ("CV",  2.79, 0.06),   # 18%   Carry's pairing
    "S":   ("L",   3.36, 0.16),   # 20%   the row: LL/L
    "Sa":  ("H",   3.42, 0.18),   # 18%   ordinary chondrite: the densest, H
    "Sk":  ("H",   3.42, 0.18),   # 24%
    "Sl":  ("H",   3.42, 0.18),   # 21%
    "Sq":  ("L",   3.36, 0.16),   # 17%   the row: LL/L
    "Sr":  ("H",   3.42, 0.18),   # 15%
    "Sv":  ("H",   3.42, 0.18),   # 12%
    "Q":   ("H",   3.42, 0.18),   # 21%   (12% at the 3.00 it read until 1.6.0)
    "O":   ("H",   3.42, 0.18),   # 15%
    "R":   ("H",   3.42, 0.18),   #  9%
    "B":   ("CV",  2.79, 0.06),   # 53%   Carry's pairing
    "F":   ("CV",  2.79, 0.06),   # 50%   as B
    "C":   ("CM",  2.25, 0.08),   # 33%   the row: CI/CM
    "Cb":  ("CM",  2.25, 0.08),   # 38%
    "Cg":  ("CM",  2.25, 0.08),   # 33%
    "G":   ("CM",  2.25, 0.08),   # 33%   as Cg
    "Ch":  ("CM",  2.25, 0.08),   # 33%   the row: CM2
    "Cgh": ("CK",  2.85, 0.08),   # 44%   the row: CH/CK (no CH in Table 2)
    "D":   ("CM",  2.25, 0.08),   # 47%   Carry's pairing
    "Z":   ("CM",  2.25, 0.08),   # 47%   as D
    "P":   ("CM",  2.25, 0.08),   # 47%   as D, the row's other name
    "K":   ("CO",  3.03, 0.19),   # 17%   the row: CV/CO
    "L":   ("CO",  3.03, 0.19),   #  8%   Carry's pairing; the row: CV3
    "V":   ("HED", 3.25, 0.26),   # 11%
    "Xe":  ("EH",  3.47, 0.21),   # 16%
    "E":   ("EH",  3.47, 0.21),   #  8%   the row: aubrite/E-chondrite
    "Xk":  ("Mes", 4.35, 0.02),   # 13%   Carry's pairing (mesosiderite)
    "M":   ("Mes", 4.35, 0.02),   # 10%   as Xk
    "Xc":  ("Mes", 4.35, 0.02),   # 46%   Carry's pairing
    "A":   ("Pal", 4.76, 0.10),   # 33%   Carry's pairing (pallasite)
}

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
# are unaffected.  Conservative midpoints; the literature variance is huge.
#
# ⚠️  NONE OF THESE NUMBERS HAS A SOURCE, AND ONE PREMISE ABOVE IS WRONG.
# Neither the ~37 ppm baseline nor any factor traces to a publication.  What
# the literature does say (Kargel 1994, JGR 99, 21129): precious metals in
# iron meteorites vary "up to several hundred ppm", and the Fe-Ni metal of LL
# chondrites carries 50-220 ppm.  Other compilations agree on the spread:
# IIIAB irons run 0.17-75 ppm total PGM from the 10th to the 90th percentile,
# and six irons measured by AMS 16-270 ppm.  So:
#
#   * "chondritic" and "mean iron meteorite" are NOT the same baseline, as
#     the paragraph above says they are.  PGMs are siderophile: in an
#     undifferentiated body nearly all of them sit in its metal, and the less
#     metal there is the richer it is.  LL metal is 1.4-6x the 37 ppm
#     baseline, not 1x.
#   * so the ordinary-chondrite classes (S, Sq, Q) at 1.0 UNDERSTATE their
#     metal's PGM, and more so since 1.5.0 cut their metal fraction to 0.06:
#     a consumer multiplying metal x ppm x factor now credits an S-type with
#     less than half the PGM it did.  That is the conservative direction, and
#     it is left there deliberately rather than replaced by another guess.
#
# A calibrated table would start from bulk chondritic PGM (conserved through
# differentiation) divided by each class's metal fraction.  Done for S, that
# arithmetic agrees with Kargel: CI chondrites carry 3.29 ppm PGM in bulk
# (Ru 0.686, Rh 0.139, Pd 0.558, Os 0.493, Ir 0.469, Pt 0.947; Lodders 2010
# Table 2), which in S's 0.06 metal is 55 ppm if the metal holds all of it,
# 1.5x the baseline and inside LL metal's 50-220 ppm.  (CI is the
# undifferentiated composition, not an S-type's analogue; an ordinary
# chondrite would need its own bulk PGM.)  Until a table is built that way,
# cost nothing that depends on these factors being right.

PGM_ENRICHMENT_BY_TYPE: Dict[str, float] = {
    # ── Differentiated core fragments, PGMs concentrated by metal-segregation ──
    "M":  2.0,   # Tholen metallic (e.g. 16 Psyche)
    "Xk": 2.0,   # Bus-DeMeo M-analog (13 of 24 Tholen M are Xk; was Xe until 1.5.0)
    "Xe": 1.5,   # E-chondrite / aubrite analog (the 0.49-um E-type band; was Xk)
    # X and Xc without an albedo (1.6.0; were 1.5 and 1.2): the metal-weighted
    # mixture of P, M and E, 1.97 and 1.96.  Nearly all their metal is the
    # M-like members', so the factor is M's.
    "X":  2.0,
    "Xc": 2.0,
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
    `.apply()` shared them: `composition_entry` returns the row straight out of
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


# How a classification column spells "no classification", compared after
# `str.strip()`.  "<NA>" is what pandas < 3 renders a missing value as under
# `astype(str)`; left in, it became a class called "<na>" and skipped every
# inference downstream.
_BLANK_CLASSES = ("", "-", "nan", "NaN", "None", "none", "NA", "<NA>")


def _bus_demeo_case(t: str) -> str:
    """A class in Bus-DeMeo capitalisation: "sq" and "SQ" both become "Sq".

    First letter upper, rest lower, which is how the tables here are keyed.
    `t` must be a non-empty, already-stripped string.
    """
    return t[0].upper() + t[1:].lower()


def composition_key(spec_type) -> str:
    """The TAXONOMY_COMPOSITION key for a class: exact, else its root letter.

    A sub-type nobody tabulated inherits its complex ("Sq2" takes "S"), and
    anything else, a missing value included, is "Unknown".  Expects the class
    already in Bus-DeMeo capitalisation.
    """
    if isinstance(spec_type, str) and spec_type:
        for key in (spec_type, spec_type[0]):
            if key in TAXONOMY_COMPOSITION:
                return key
    return "Unknown"


def composition_entry(spec_type) -> dict:
    """The TAXONOMY_COMPOSITION row for a class; see `composition_key`."""
    return TAXONOMY_COMPOSITION[composition_key(spec_type)]


# ─────────────────────────────────────────────────────────────────────────────
# THE X COMPLEX, BY ALBEDO  (1.6.0)
# ─────────────────────────────────────────────────────────────────────────────
# Tholen's E, M and P share one featureless spectrum and differ in albedo, so
# a class that stops at X says nothing about composition until an albedo
# does.  By convention an X-type with a measured albedo is a Tholen E above
# p_V 0.3, an M from 0.1 to 0.3 and a P below 0.1 (Fornasier, Clark & Dotto
# 2011, Icarus 214, 131, p. 5).  Xc, whose members run from Hestia (P) to
# Undina (M) in SsODNet's current classes, is as ambiguous.  Three routes agree that the albedo separates bodies of
# different density:
#
#   * Berthier et al. (2023, Fig. 5): X-complex densities are bimodal, the P
#     sub-class (mean p_V 0.044) below 2 g/cm3, M (0.129) above.
#   * data-2026-09-26b: the X-complex bodies with a mass known to 20% have a
#     median of 1.44 below 0.10 (N=15) and 3.45 from 0.10 to 0.30 (N=17);
#     tools/density_evidence.py re-runs it.
#   * the cuts reproduce JPL's own Tholen labels: of the 83 bodies it types
#     E, M or P that carry an albedo in data-2026-09-26b, 80 fall in the bin
#     their label names (12 of 12 E, 36 of 38 M, 32 of 33 P).
#
# So a body whose class resolves to X or Xc and which has a MEASURED albedo
# takes its composition from P, M or E; `spectral_type` keeps the source's
# label and `comp_class` names the row used.  The measured masses and
# densities are still judged against the label's group (enrich.py): an
# inferred class is not grounds to refuse a measurement.  A body with no
# albedo keeps the X or Xc row, the mixture of the three (X_SPLIT_COUNTS).
# Xe and Xk are not split: their spectral bands already say which.
X_SPLIT_BOUNDS = (0.10, 0.30)        # P below the first, E at or above the second
X_SPLIT_CLASSES = ("P", "M", "E")
X_SPLIT_ROWS = ("X", "Xc")
# How the bodies of data-2026-09-26b whose class resolves to each row, inside
# 5.5 AU, divide by measured albedo: (P, M, E).  The X and Xc rows are their
# mixture: density weighted by count, each fraction and the PGM factor by
# mass (tests/test_traps.py recomputes them; tools/density_evidence.py
# recounts them on any build).  The measured sample over-represents dark
# bodies (derive.py), so the bodies with no albedo may lean more M than this.
X_SPLIT_COUNTS = {"X": (4741, 3022, 350), "Xc": (40, 27, 7)}


def split_x_by_albedo(keys: pd.Series, albedo: pd.Series) -> pd.Series:
    """Composition keys with X and Xc resolved to P, M or E by albedo.

    `keys` are TAXONOMY_COMPOSITION keys (`composition_key`); `albedo` is the
    MEASURED geometric albedo, and only 0 < p_V < 1 counts.  Every other key,
    and an X or Xc with no albedo, is returned unchanged.
    """
    p = pd.to_numeric(albedo, errors="coerce")
    lo, hi = X_SPLIT_BOUNDS
    by_albedo = pd.Series(np.where(p < lo, "P", np.where(p < hi, "M", "E")),
                          index=keys.index)
    split = keys.isin(X_SPLIT_ROWS) & (p > 0) & (p < 1)
    return keys.where(~split, by_albedo)


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
