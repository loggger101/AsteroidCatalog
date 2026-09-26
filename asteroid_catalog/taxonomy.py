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
#                                 seven times any measurement.
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
#   density_est_gcm3              checked against Carry (2012) Table 3 in
#                                 DENSITY_EVIDENCE below, which says where
#                                 each class sits against measured bodies.
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
                 "chondrite metal; 0.15 was H-chondrite metal.",
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
        "density_est_gcm3":  3.30,
        "metal_fraction":    0.25,
        "silicate_fraction": 0.35,
        "carbon_fraction":   0.20,
        "ice_fraction":      0.00,
        "notes": "Low albedo suggests carbonaceous metallic mix.  v1.5.0: "
                 "density 2.50 -> 3.30, the X-complex value: no density known "
                 "to 20% supports lower, and the two Xc-types Carry (2012) has "
                 "at that precision average 4.86 +/- 0.81.",
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
                 "Density 3.80: Psyche 3.8-3.9, Carry (2012) Xk 3.79-4.22.  "
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
        "density_est_gcm3":  3.00,
        "metal_fraction":    0.06,
        "silicate_fraction": 0.72,
        "carbon_fraction":   0.02,
        "ice_fraction":      0.00,
        "notes": "Fresh/unweathered ordinary chondrite analog.  v1.5.0: metal "
                 "0.20 -> 0.06, as S: more than H-chondrite metal was no LL/L "
                 "chondrite.",
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
        "notes": "Tholen E-type ≈ Bus-DeMeo Xe (the 0.49-μm band; until 1.5.0 "
                 "this said Xk); very high albedo (>0.3).  "
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
# DENSITY EVIDENCE  (1.5.0)
# ─────────────────────────────────────────────────────────────────────────────
# What measured bodies say about each class's `density_est_gcm3`, so the
# estimate can be held to it (tests/test_traps.py).  `carry2012` is the class
# average over the densities known to 20% or better, (mean, sigma, N), from
# Carry (2012, Planet. Space Sci. 73, 98), Table 3: the tier worth testing
# against.  Classes with nothing at that precision are absent.  `bodies` are
# individual densities, for reading, from the same paper's Table 1 unless a
# later reference is named.
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
    "S":  {"carry2012": (2.72, 0.54, 11),
           "bodies": [("433 Eros", 3.00, 0.08), ("243 Ida", 2.35, 0.29),
                      ("25143 Itokawa", 1.91, 0.21)]},
    "Sq": {"carry2012": (3.43, 0.20, 2),
           "bodies": [("3 Juno", 3.68, 0.62), ("11 Parthenope", 3.27, 0.41)],
           "below_because": "the two Sq-types known to 20% are large (Juno "
                            "242 km, Parthenope 151 km); small "
                            "S-types are rubble piles, Itokawa 1.9 +/- 0.13 "
                            "(Fujiwara et al. 2006)"},
    "B":  {"carry2012": (2.38, 0.45, 2),
           "bodies": [("2 Pallas", 2.86, 0.32), ("704 Interamnia", 1.96, 0.28),
                      ("101955 Bennu", 1.190, 0.013)],   # Lauretta et al. 2019
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
    "X":  {"carry2012": (1.85, 0.81, 8),
           "bodies": [("87 Sylvia", 1.31, 0.15), ("107 Camilla", 2.28, 0.29),
                      ("22 Kalliope", 4.40, 0.46)]},   # Ferrais et al. 2022
    "Xc": {"carry2012": (4.86, 0.81, 2),
           # Hestia is Carry's confidence rank E, the lowest.
           "bodies": [("97 Klotho", 4.16, 0.62), ("46 Hestia", 5.81, 0.87)]},
    "Xe": {"carry2012": (2.60, 0.20, 1),
           "bodies": [("3169 Ostro", 2.59, 0.20), ("216 Kleopatra", 4.27, 0.86)]},
    "Xk": {"carry2012": (4.22, 0.65, 3),
           "bodies": [("16 Psyche", 3.38, 1.16), ("21 Lutetia", 3.44, 0.52)]},
    "K":  {"carry2012": (3.54, 0.21, 1),
           "bodies": [("15 Eunomia", 3.54, 0.20)],
           "below_because": "one body: 15 Eunomia, 256 km, which other "
                            "catalogs class S; no small K-type has been "
                            "measured, and the estimate is the CV/CO analogue "
                            "at an S-type's macroporosity"},
    "V":  {"carry2012": (1.93, 1.07, 3),
           "bodies": [("4 Vesta", 3.58, 0.15), ("809 Lundia", 1.64, 0.10),
                      ("854 Frostia", 0.88, 0.13)]},
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
# differentiation) divided by each class's metal fraction.  Until it does,
# cost nothing that depends on these factors being right.

PGM_ENRICHMENT_BY_TYPE: Dict[str, float] = {
    # ── Differentiated core fragments, PGMs concentrated by metal-segregation ──
    "M":  2.0,   # Tholen metallic (e.g. 16 Psyche)
    "Xk": 2.0,   # Bus-DeMeo M-analog (13 of 24 Tholen M are Xk; was Xe until 1.5.0)
    "Xe": 1.5,   # E-chondrite / aubrite analog (the 0.49-um E-type band; was Xk)
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


def composition_entry(spec_type) -> dict:
    """The TAXONOMY_COMPOSITION row for a class: exact, else its root letter.

    A sub-type nobody tabulated inherits its complex ("Sq2" takes "S"), and
    anything else, a missing value included, is "Unknown".  Expects the class
    already in Bus-DeMeo capitalisation.
    """
    if isinstance(spec_type, str) and spec_type:
        entry = (TAXONOMY_COMPOSITION.get(spec_type)
                 or TAXONOMY_COMPOSITION.get(spec_type[0]))
        if entry:
            return entry
    return TAXONOMY_COMPOSITION["Unknown"]


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
