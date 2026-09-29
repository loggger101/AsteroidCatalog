# -*- coding: utf-8 -*-
"""The mineral PHASES inside each class's four coarse fractions  (data contracts 1.7.0, 1.8.0).

1.8.0 resolves two of them further, into `comp_phases_detailed`: see the
section of that name at the foot of this module.

`TAXONOMY_COMPOSITION` gives every class four mass fractions (metal, silicate,
carbon, ice) and a `minerals` list that NAMES what is there without saying how
much.  A consumer valuing a body can therefore sell "silicate" but not the
olivine and plagioclase it is made of, "metal" but not the phosphide in it,
and nothing at all of the troilite, magnetite or carbonate that sits in the
residual those four leave.  This module says how much of each.

TWO TABLES, AND THE SPLIT BETWEEN THEM IS THE CONTRACT:

  `PHASE_SHARES`       how each coarse fraction divides among its phases, as
                       SHARES that sum to 1 within the group.  The absolute
                       fraction is share x the row's coarse fraction, so the
                       phases of a group always add back to the coarse figure
                       by construction, and a coarse fraction revised later
                       moves its phases with it rather than disagreeing.

  `ACCESSORY_PHASES`   phases that belong to NONE of the four groups -- the
                       sulfides, oxides and carbonates -- as ABSOLUTE fractions
                       of the body, carved out of the residual the four coarse
                       fractions leave (which a consumer otherwise floors at a
                       bulk-silicate value).  They may not exceed it.

So this module adds detail and moves no existing number: every `comp_*`
column a build wrote before 1.7.0 is unchanged, and `comp_phases` is new.

`PHASE_GROUP` is the vocabulary: every phase any row may name, and the group
it belongs to.  A phase outside it is a test failure, because a consumer keys
its prices on these names.

WHERE A NUMBER HAS A SOURCE, THIS IS IT (all shares are of the group, all
accessory figures of the body, all rounded):

  ordinary chondrite     S, Sq, Q: the L/LL mean of the XRD modal abundances
    (S complex, Q)       in Dunn, Cressey, McSween & McCoy (2010, MAPS 45,
                         123): olivine ~50 wt%, low-Ca pyroxene ~21, high-Ca
                         pyroxene ~5, plagioclase ~10, troilite ~5.5, chromite
                         ~0.5.  Normalised over the silicates that is olivine
                         0.58 / orthopyroxene 0.24 / pyroxene 0.06 /
                         plagioclase 0.12, and troilite and chromite are body
                         fractions.  Sa, Sr, Sv, Sk and Sl lean that split
                         toward the neighbour class their label names; the
                         lean is a judgement, not a measurement.
  CI chondrite           C, B, Cb, F: Orgueil and Ivuna by XRD (King, Schofield,
                         Howard & Russell 2015, GCA 165, 148): phyllosilicate
                         (serpentine + saponite) ~81-84 wt%, magnetite ~6-10,
                         sulfide ~5-7, carbonate ~2-5, olivine a few percent.
  CM chondrite           Cg, Ch, G: Howard, Alexander, Schrader & Dyl (2015,
                         GCA 149, 206): phyllosilicate 70-90 wt%, olivine +
                         pyroxene most of the rest, magnetite and sulfide a few
                         percent, carbonate ~1-2.
  carbon, C complex      0.70 insoluble macromolecular organic matter to 0.30
                         soluble organics: IOM is 70-99% of the organic carbon
                         in CI/CM chondrites (Alexander et al. 2007, GCA 71,
                         4380); the low end, so the split does not over-credit
                         the cheaper row.
  enstatite chondrite    Xe: EH, enstatite ~60-70 wt% with plagioclase, metal
                         ~20-25, sulfides (troilite, niningerite) ~10; the
                         schreibersite share of the metal is ~0.03 (E
                         chondrites carry 1-2 wt% schreibersite in bulk).
  aubrite                E: enstatite near 0.95 of the silicate, trace
                         plagioclase and forsterite, troilite ~1 wt%.
  iron / mesosiderite    M, Xk: the metal is kamacite + taenite with ~1.5%
                         schreibersite, (Fe,Ni)3P, at ~15.5 wt% P, which is
                         the 0.2-0.3 wt% bulk P of the common iron groups.
  HED                    V: eucrite pyroxene (pigeonite/augite) and
                         plagioclase in near-equal parts, diogenite
                         orthopyroxene, trace olivine; chromite and ilmenite
                         ~1 wt% each (Mittlefehldt 2015, Chem. Erde 75, 155).
  CV / CO                K, L: olivine-dominated with CAIs; spinel is the CAI
                         mineral.  L-types need the highest CAI content of any
                         spectrum (Sunshine et al. 2008, Science 320, 514), so
                         L carries the most spinel the residual allows.
  ices, D Z P            the cometary volatile mix, H2O : CO2 : NH3 =
                         100 : 4.7 : 0.67 by number (Rubin et al. 2019, MNRAS
                         489, 594, 67P bulk from ROSINA), CO dropped as too
                         volatile to survive at asteroid distances.  By mass
                         that is water 0.892, carbon dioxide 0.102, ammonia
                         0.006.
  D, Z, P accessories    Tagish Lake, the proposed D-type analogue (Hiroi et al.
                         2001, Science 293, 2234): magnetite ~5, sulfide ~3,
                         carbonate ~3 wt%.

WHAT HAS NO SOURCE: every split for A, R, O and T; the silicate split of the
X-complex members beyond "enstatite dominates"; the Sa/Sr/Sv/Sk/Sl leans; and
which accessory the residual goes to in a class whose analogue is uncertain.
Those are the row's own `minerals` list turned into numbers, and are here so
that a consumer is never left to invent them per row.

X and Xc are NOT typed: like every other field of those rows they are the
mass-weighted mixture of P, M and E (taxonomy.X_SPLIT_COUNTS), derived here and
rescaled so each group still sums to the row's own coarse fraction.
"""

import json
from typing import Dict, Optional

from .taxonomy import TAXONOMY_COMPOSITION, X_SPLIT_CLASSES, X_SPLIT_COUNTS, X_SPLIT_ROWS


# The four coarse groups, in the order their fields appear in TAXONOMY_COMPOSITION.
GROUP_FIELDS: Dict[str, str] = {
    "metal":    "metal_fraction",
    "silicate": "silicate_fraction",
    "carbon":   "carbon_fraction",
    "ice":      "ice_fraction",
}
ACCESSORY = "accessory"

# Every phase a row may name, and the group it belongs to.  The names are the
# consumer's price keys, so they are spelled as its mineral table spells them.
PHASE_GROUP: Dict[str, str] = {
    "nickel-iron":     "metal",      # kamacite + taenite
    # 1.8.0: the alloy resolved into the phases it is made of, and a carbide
    "kamacite":        "metal",      # alpha-(Fe,Ni), ~6.5 wt% Ni
    "taenite":         "metal",      # gamma-(Fe,Ni), ~30 wt% Ni, with plessite
    "tetrataenite":    "metal",      # ordered FeNi, ~50 wt% Ni
    "cohenite":        "metal",      # (Fe,Ni)3C
    "schreibersite":   "metal",      # (Fe,Ni)3P
    "olivine":         "silicate",
    "orthopyroxene":   "silicate",   # low-Ca pyroxene
    "pyroxene":        "silicate",   # high-Ca / clinopyroxene, pigeonite
    "enstatite":       "silicate",
    "plagioclase":     "silicate",
    "phyllosilicates": "silicate",   # serpentine, saponite
    "silicates":       "silicate",   # anhydrous, unspecified
    "carbon":          "carbon",     # insoluble macromolecular organic matter, graphite
    "organics":        "carbon",     # soluble organic matter
    "water":           "ice",
    "carbon dioxide":  "ice",
    "ammonia":         "ice",
    "troilite":        ACCESSORY,    # FeS, standing for all Fe sulfides
    # 1.8.0: the sulfides troilite stood for, by species
    "pyrrhotite":      ACCESSORY,    # Fe(1-x)S, as Fe7S8
    "pentlandite":     ACCESSORY,    # (Fe,Ni)9S8
    "niningerite":     ACCESSORY,    # (Mg,Fe,Mn)S
    "oldhamite":       ACCESSORY,    # CaS
    "daubreelite":     ACCESSORY,    # FeCr2S4
    "magnetite":       ACCESSORY,    # Fe3O4
    "chromite":        ACCESSORY,    # FeCr2O4
    "ilmenite":        ACCESSORY,    # FeTiO3
    "perovskite":      ACCESSORY,    # CaTiO3, a CAI oxide (1.8.0)
    "spinel":          ACCESSORY,    # MgAl2O4, the CAI oxide
    "hibonite":        ACCESSORY,    # CaAl12O19, a CAI oxide (1.8.0)
    "carbonates":      ACCESSORY,    # calcite, dolomite, breunnerite
    # 1.8.0: the calcium phosphates, where a chondrite's phosphorus sits
    "merrillite":      ACCESSORY,    # Ca9NaMg(PO4)7
    "chlorapatite":    ACCESSORY,    # Ca5(PO4)3Cl
}

# ── Shares within a group, reused across the classes that share an analogue ──
_METAL_PLAIN     = {"nickel-iron": 1.0}
_METAL_IRON      = {"nickel-iron": 0.985, "schreibersite": 0.015}
_METAL_ENSTATITE = {"nickel-iron": 0.97,  "schreibersite": 0.03}

_SIL_OC  = {"olivine": 0.58, "orthopyroxene": 0.24, "pyroxene": 0.06, "plagioclase": 0.12}
_SIL_CI  = {"phyllosilicates": 0.95, "olivine": 0.05}
_SIL_CM  = {"phyllosilicates": 0.85, "olivine": 0.10, "pyroxene": 0.05}
_SIL_CV  = {"olivine": 0.75, "pyroxene": 0.20, "plagioclase": 0.05}

_CARBON_CC        = {"carbon": 0.70, "organics": 0.30}
_CARBON_PRIMITIVE = {"organics": 0.60, "carbon": 0.40}
_CARBON_PLAIN     = {"carbon": 1.0}

_ICE_BOUND = {"water": 1.0}                         # bound water, hydrated classes
_ICE_COMET = {"water": 0.892, "carbon dioxide": 0.102, "ammonia": 0.006}

_ACC_OC = {"troilite": 0.055, "chromite": 0.005}
_ACC_CI = {"magnetite": 0.07, "troilite": 0.05, "carbonates": 0.03}
_ACC_CM = {"troilite": 0.03, "magnetite": 0.02, "carbonates": 0.01}
_ACC_TL = {"magnetite": 0.05, "troilite": 0.03, "carbonates": 0.03}   # Tagish Lake


def _row(metal, silicate, carbon, ice=None):
    """One PHASE_SHARES row; a group left None has a zero coarse fraction."""
    out = {"metal": metal, "silicate": silicate, "carbon": carbon}
    if ice is not None:
        out["ice"] = ice
    return out


PHASE_SHARES: Dict[str, Dict[str, Dict[str, float]]] = {
    # ── C complex ───────────────────────────────────────────────────────────
    "B":   _row(_METAL_PLAIN, _SIL_CI, _CARBON_CC, _ICE_BOUND),
    "C":   _row(_METAL_PLAIN, _SIL_CI, _CARBON_CC, _ICE_BOUND),
    "Cb":  _row(_METAL_PLAIN, _SIL_CI, _CARBON_CC, _ICE_BOUND),
    "F":   _row(_METAL_PLAIN, _SIL_CI, _CARBON_CC, _ICE_BOUND),
    "Cg":  _row(_METAL_PLAIN, _SIL_CM, _CARBON_CC, _ICE_BOUND),
    "Ch":  _row(_METAL_PLAIN, _SIL_CM, _CARBON_CC, _ICE_BOUND),
    "G":   _row(_METAL_PLAIN, _SIL_CM, _CARBON_CC, _ICE_BOUND),
    # CH/CK: the row names olivine first; CK chondrites are olivine-rich.
    "Cgh": _row(_METAL_PLAIN,
                {"phyllosilicates": 0.50, "olivine": 0.40, "pyroxene": 0.10},
                _CARBON_CC, _ICE_BOUND),
    # ── S complex and Q: ordinary chondrite ─────────────────────────────────
    "S":   _row(_METAL_PLAIN, _SIL_OC, _CARBON_PLAIN),
    "Sq":  _row(_METAL_PLAIN, _SIL_OC, _CARBON_PLAIN),
    "Q":   _row(_METAL_PLAIN, _SIL_OC, _CARBON_PLAIN),
    "Sk":  _row(_METAL_PLAIN, _SIL_OC, _CARBON_PLAIN),
    "Sl":  _row(_METAL_PLAIN, _SIL_OC, _CARBON_PLAIN),
    "Sa":  _row(_METAL_PLAIN,
                {"olivine": 0.75, "orthopyroxene": 0.12, "pyroxene": 0.03,
                 "plagioclase": 0.10}, _CARBON_PLAIN),
    "Sr":  _row(_METAL_PLAIN,
                {"olivine": 0.45, "orthopyroxene": 0.35, "pyroxene": 0.08,
                 "plagioclase": 0.12}, _CARBON_PLAIN),
    "Sv":  _row(_METAL_PLAIN,
                {"olivine": 0.30, "orthopyroxene": 0.30, "pyroxene": 0.20,
                 "plagioclase": 0.20}, _CARBON_PLAIN),
    # ── X complex members (X and Xc are derived below) ──────────────────────
    "M":   _row(_METAL_IRON, {"enstatite": 0.70, "plagioclase": 0.20,
                              "olivine": 0.10}, _CARBON_PLAIN),
    "Xk":  _row(_METAL_IRON, {"enstatite": 0.70, "plagioclase": 0.20,
                              "olivine": 0.10}, _CARBON_PLAIN),
    "Xe":  _row(_METAL_ENSTATITE, {"enstatite": 0.90, "plagioclase": 0.10},
                _CARBON_PLAIN),
    "E":   _row(_METAL_PLAIN, {"enstatite": 0.95, "plagioclase": 0.03,
                               "olivine": 0.02}, _CARBON_PLAIN),
    "P":   _row(_METAL_PLAIN, {"silicates": 1.0}, _CARBON_PRIMITIVE, _ICE_COMET),
    # ── primitive outer bodies ──────────────────────────────────────────────
    "D":   _row(_METAL_PLAIN, {"silicates": 1.0}, _CARBON_PRIMITIVE, _ICE_COMET),
    "Z":   _row(_METAL_PLAIN, {"silicates": 1.0}, _CARBON_PRIMITIVE, _ICE_COMET),
    "T":   _row(_METAL_PLAIN, {"silicates": 1.0}, _CARBON_PRIMITIVE, _ICE_COMET),
    # ── the rest ────────────────────────────────────────────────────────────
    "A":   _row(_METAL_PLAIN, {"olivine": 0.95, "orthopyroxene": 0.05}, _CARBON_PLAIN),
    "R":   _row(_METAL_PLAIN, {"olivine": 0.60, "orthopyroxene": 0.30,
                               "pyroxene": 0.05, "plagioclase": 0.05}, _CARBON_PLAIN),
    "O":   _row(_METAL_PLAIN, {"olivine": 0.50, "orthopyroxene": 0.50}, _CARBON_PLAIN),
    "K":   _row(_METAL_PLAIN, _SIL_CV, _CARBON_CC),
    "L":   _row(_METAL_PLAIN, {"olivine": 0.60, "pyroxene": 0.30,
                               "plagioclase": 0.10}, _CARBON_PLAIN),
    "V":   _row(_METAL_PLAIN, {"pyroxene": 0.45, "orthopyroxene": 0.15,
                               "plagioclase": 0.37, "olivine": 0.03}, _CARBON_PLAIN),
}

ACCESSORY_PHASES: Dict[str, Dict[str, float]] = {
    "B": _ACC_CI, "C": _ACC_CI, "Cb": _ACC_CI, "F": _ACC_CI,
    "Cg": _ACC_CM, "Ch": _ACC_CM, "G": _ACC_CM,
    "Cgh": {"magnetite": 0.05, "troilite": 0.02},          # CK: magnetite-rich
    "S": _ACC_OC, "Sq": _ACC_OC, "Q": _ACC_OC, "Sa": _ACC_OC, "Sr": _ACC_OC,
    "Sv": _ACC_OC,
    "Sk": {"troilite": 0.055, "chromite": 0.005, "magnetite": 0.02},
    "Sl": {"troilite": 0.055, "chromite": 0.005, "spinel": 0.03},
    "M":  {"troilite": 0.02},
    "Xk": {"troilite": 0.02},
    "Xe": {"troilite": 0.08},
    "E":  {"troilite": 0.01},
    "P": _ACC_TL, "D": _ACC_TL, "Z": _ACC_TL,
    "T":  {"troilite": 0.08, "magnetite": 0.03},            # the row names troilite
    "A":  {"chromite": 0.01, "troilite": 0.01},
    "R":  {"troilite": 0.01, "chromite": 0.005},
    "O":  {"troilite": 0.02},
    "K":  {"magnetite": 0.03, "spinel": 0.03, "troilite": 0.02},
    "L":  {"spinel": 0.05, "troilite": 0.02},
    "V":  {"chromite": 0.01, "ilmenite": 0.01, "troilite": 0.005},
}


# ─────────────────────────────────────────────────────────────────────────────
# X and Xc: the mixture of P, M and E, as every other field of those rows is
# ─────────────────────────────────────────────────────────────────────────────
def _mixture(row: str):
    """(shares by group, accessory) for X or Xc, mass-weighted over P, M, E."""
    counts = dict(zip(X_SPLIT_CLASSES, X_SPLIT_COUNTS[row]))
    mass = {c: n * TAXONOMY_COMPOSITION[c]["density_est_gcm3"] for c, n in counts.items()}
    total = sum(mass.values())
    mixed: Dict[str, float] = {}
    for c, m in mass.items():
        for phase, frac in phase_fractions(c).items():   # P, M, E are typed
            mixed[phase] = mixed.get(phase, 0.0) + m * frac / total
    shares: Dict[str, Dict[str, float]] = {}
    for group in GROUP_FIELDS:
        members = {p: f for p, f in mixed.items() if PHASE_GROUP[p] == group}
        s = sum(members.values())
        if s > 0:
            shares[group] = {p: f / s for p, f in members.items()}
    accessory = {p: f for p, f in mixed.items() if PHASE_GROUP[p] == ACCESSORY}
    return shares, accessory




# ─────────────────────────────────────────────────────────────────────────────
# What a build writes
# ─────────────────────────────────────────────────────────────────────────────
def _in_table_order(fracs: Dict[str, float]) -> Dict[str, float]:
    """Group order (metal, silicate, carbon, ice, accessory), then PHASE_GROUP's.

    A fixed order so `comp_phases` is byte-identical for one class on every
    build, whatever order the arithmetic produced its keys in.
    """
    order = list(PHASE_GROUP)
    groups = list(GROUP_FIELDS) + [ACCESSORY]
    return {p: fracs[p] for p in sorted(
        fracs, key=lambda p: (groups.index(PHASE_GROUP[p]), order.index(p)))}


def phase_fractions(cls: str) -> Optional[Dict[str, float]]:
    """Mass fraction of the body in each phase, or None for a class with none.

    The groups add back to the row's coarse fractions (to rounding), and the
    accessories fit inside the residual; tests/test_mineralogy.py holds both.
    Zero fractions are left out, so a key present is a phase present.
    """
    if cls not in PHASE_SHARES:
        return None
    entry = TAXONOMY_COMPOSITION[cls]
    out: Dict[str, float] = {}
    for group, field in GROUP_FIELDS.items():
        coarse = entry.get(field)
        if not coarse:
            continue
        for phase, share in PHASE_SHARES[cls][group].items():
            if share > 0:
                out[phase] = out.get(phase, 0.0) + coarse * share
    for phase, frac in ACCESSORY_PHASES.get(cls, {}).items():
        if frac > 0:
            out[phase] = out.get(phase, 0.0) + frac
    return _in_table_order(out)


def phases_json(cls: str) -> Optional[str]:
    """`phase_fractions` as the compact JSON a build writes to `comp_phases`.

    Floats are written by `repr`, so they read back as the same doubles.
    None (a missing value in the CSV) for a class with no phases: Unknown.
    """
    fracs = phase_fractions(cls)
    if fracs is None:
        return None
    return json.dumps(fracs, separators=(",", ":"))


# Derived last, because the mixture reads the typed rows through phase_fractions.
for _row_name in X_SPLIT_ROWS:
    PHASE_SHARES[_row_name], ACCESSORY_PHASES[_row_name] = _mixture(_row_name)
del _row_name


# ═════════════════════════════════════════════════════════════════════════════
# DATA CONTRACT 1.8.0: THE DETAILED PHASES  (`comp_phases_detailed`)
# ═════════════════════════════════════════════════════════════════════════════
# `comp_phases` stops at "nickel-iron" and "troilite", each standing for a
# family.  The detailed column resolves them, and adds the phosphates and the
# CAI oxides the residual was holding without a name:
#
#   the alloy       nickel-iron is kamacite (alpha, ~6.5 wt% Ni) and taenite
#                   (gamma, ~30%, taken with the plessite it grades into), and
#                   in slowly cooled chondrites tetrataenite (ordered FeNi,
#                   ~50%); irons add cohenite, (Fe,Ni)3C.  WHICH class holds
#                   WHICH mix is the point: siderophile metals ride with
#                   nickel, so a Ni-rich chondrite metal carries more platinum
#                   per kilogram than an iron meteorite's, which one
#                   "nickel-iron" for every class could not say.
#   the sulfides    "troilite" is FeS in the ordinary chondrites and the irons,
#                   and stays so there.  In the hydrated and primitive classes
#                   the sulfide is pyrrhotite with pentlandite, the nickel
#                   sulfide; in the enstatite classes it is troilite with the
#                   reduced sulfides niningerite, oldhamite and daubreelite.
#   the phosphates  merrillite and chlorapatite, ~0.6 wt% of an ordinary
#                   chondrite, carved out of the residual.
#   CAI oxides      perovskite and hibonite beside the spinel K and L carry.
#
# TWO TABLES, THE SAME CONTRACT AS 1.7.0'S, ONE LEVEL DOWN:
#
#   `PHASE_DETAIL`         per class, a phase of `comp_phases` divided into
#                          finer phases as SHARES that sum to one.  A phase
#                          with no entry passes through unchanged.  So the
#                          detailed phases of a `comp_phases` entry add back to
#                          it, every group adds back to its coarse fraction,
#                          and nothing in `comp_phases` moves.
#   `DETAIL_ACCESSORIES`   phases new to the residual, as absolute fractions of
#                          the body, which must fit inside what the four coarse
#                          fractions and `ACCESSORY_PHASES` leave.
#
# WHERE A NUMBER HAS A SOURCE (fractions are rounded; shares of the parent):
#
#   ordinary chondrite    metal: Fe-Ni-Co metal falls from 17.8 (H) to 8.33
#     (S complex, Q)      (L) to 3.56 wt% (LL) while bulk Ni barely moves
#                         (Jarosewich 1990, Meteoritics 25, 323): the iron
#                         oxidises into the silicate and the nickel stays, so
#                         Ni in the metal climbs from roughly 9 to 14 to 25+
#                         wt%, and LL metal is mostly taenite.  S-types lean
#                         LL (Itokawa), so kamacite 0.55, taenite 0.38,
#                         tetrataenite 0.07, which is ~18.5 wt% Ni at the
#                         consumer's alloy compositions, the L/LL middle.
#                         Phosphates: merrillite ~0.4 and chlorapatite ~0.2
#                         wt% (Jones et al. 2014, GCA 132, 120, LL chondrites).
#   iron meteorite        M, Xk: kamacite 0.88, taenite 0.11, cohenite 0.01 of
#                         the Fe-Ni: a Widmanstatten octahedrite whose bulk Ni
#                         (~9%) the lever rule between 6.5 and 30 wt% returns.
#   CI / CM / Tagish Lake the sulfide is pyrrhotite with lesser pentlandite
#                         (King et al. 2015; Howard et al. 2015); CK (Cgh) and
#                         the oxidised CV (K) are pentlandite-rich.
#   enstatite chondrite   Xe (EH): troilite ~5, niningerite ~2, oldhamite ~0.7
#                         and daubreelite ~0.3 wt% of the body, within the 8%
#                         of sulfide the row already carries (Keil 1968, JGR
#                         73, 6945).  Aubrite (E): oldhamite and a little
#                         daubreelite beside troilite (Keil 2010, Chemie der
#                         Erde 70, 295).
#   CV / CO               K, L: perovskite and hibonite are CAI minerals; L,
#                         which needs the most CAI of any spectrum (Sunshine et
#                         al. 2008), carries the most.
#
#   enstatite / HED       E, Xe, V: the metal is KAMACITE alone.  Enstatite
#                         chondrite and aubrite metal is low-Ni kamacite (Keil
#                         1968; Keil 2010), and eucrite metal is nearly
#                         Ni-free (Mittlefehldt 2015), which kamacite's ~6.5%
#                         still overstates.
#
# WHAT HAS NO SOURCE: every sulfide split as a number (the sources name the
# species, not a ratio this table could quote); the K alloy split; the CAI
# oxide fractions; and the metal of every class not named above -- the C
# complex, P, D, Z, T, A, R, O and L.
#
# 🚨  NO SOURCE MEANS NO CHANGE, AND 1.8.0 GOT THAT WRONG.  It gave those
# classes pure kamacite, at ~6.5 wt% Ni, where the coarse column's
# "nickel-iron" had always meant an iron meteorite's ~9%: a consumer valuing
# nickel then read them 6-12% poorer for a choice nothing supports.  Since
# 1.8.1 they take `_ALLOY_OCTAHEDRITE`, kamacite and taenite in an
# octahedrite's proportions, which IS the alloy the coarse column assumed.
# A refinement may only move a number where a source moves it.
#
# The composition of each alloy belongs to whoever prices it; this table says
# only how much of each a class holds.

_ALLOY_KAMACITE    = {"kamacite": 1.0}
_ALLOY_OCTAHEDRITE = {"kamacite": 0.89, "taenite": 0.11}     # ~9 wt% Ni: no change
_ALLOY_OC       = {"kamacite": 0.55, "taenite": 0.38, "tetrataenite": 0.07}
_ALLOY_IRON     = {"kamacite": 0.88, "taenite": 0.11, "cohenite": 0.01}
_ALLOY_CV       = {"taenite": 0.60, "kamacite": 0.40}

_SULFIDE_CI = {"pyrrhotite": 0.70, "pentlandite": 0.30}
_SULFIDE_CM = {"pyrrhotite": 0.65, "pentlandite": 0.35}      # also Tagish Lake
_SULFIDE_NI = {"pentlandite": 0.50, "pyrrhotite": 0.50}      # CK, oxidised CV
_SULFIDE_EH = {"troilite": 0.625, "niningerite": 0.25, "oldhamite": 0.0875,
               "daubreelite": 0.0375}
_SULFIDE_AUBRITE = {"troilite": 0.60, "oldhamite": 0.30, "daubreelite": 0.10}

_PHOSPHATE_OC = {"merrillite": 0.004, "chlorapatite": 0.002}


def _detail(alloy, sulfide=None):
    """One PHASE_DETAIL row: how nickel-iron divides, and troilite if it does."""
    out = {"nickel-iron": alloy}
    if sulfide is not None:
        out["troilite"] = sulfide
    return out


PHASE_DETAIL: Dict[str, Dict[str, Dict[str, float]]] = {
    # ── C complex ───────────────────────────────────────────────────────────
    "B":   _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CI),
    "C":   _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CI),
    "Cb":  _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CI),
    "F":   _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CI),
    "Cg":  _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CM),
    "Ch":  _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CM),
    "G":   _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CM),
    "Cgh": _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_NI),
    # ── S complex and Q: ordinary chondrite, whose sulfide IS troilite ──────
    "S":   _detail(_ALLOY_OC), "Sq": _detail(_ALLOY_OC), "Q":  _detail(_ALLOY_OC),
    "Sa":  _detail(_ALLOY_OC), "Sr": _detail(_ALLOY_OC), "Sv": _detail(_ALLOY_OC),
    "Sk":  _detail(_ALLOY_OC), "Sl": _detail(_ALLOY_OC),
    # ── X complex members (X and Xc are derived below) ──────────────────────
    "M":   _detail(_ALLOY_IRON),
    "Xk":  _detail(_ALLOY_IRON),
    "Xe":  _detail(_ALLOY_KAMACITE, _SULFIDE_EH),
    "E":   _detail(_ALLOY_KAMACITE, _SULFIDE_AUBRITE),
    "P":   _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CM),
    # ── primitive outer bodies ──────────────────────────────────────────────
    "D":   _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CM),
    "Z":   _detail(_ALLOY_OCTAHEDRITE, _SULFIDE_CM),
    "T":   _detail(_ALLOY_OCTAHEDRITE),
    # ── the rest ────────────────────────────────────────────────────────────
    "A":   _detail(_ALLOY_OCTAHEDRITE),
    "R":   _detail(_ALLOY_OCTAHEDRITE),
    "O":   _detail(_ALLOY_OCTAHEDRITE),
    "K":   _detail(_ALLOY_CV, _SULFIDE_NI),
    "L":   _detail(_ALLOY_OCTAHEDRITE),
    "V":   _detail(_ALLOY_KAMACITE),
}

DETAIL_ACCESSORIES: Dict[str, Dict[str, float]] = {
    "S": _PHOSPHATE_OC, "Sq": _PHOSPHATE_OC, "Q": _PHOSPHATE_OC,
    "Sa": _PHOSPHATE_OC, "Sr": _PHOSPHATE_OC, "Sv": _PHOSPHATE_OC,
    "Sk": _PHOSPHATE_OC, "Sl": _PHOSPHATE_OC,
    "K":  {"perovskite": 0.002, "hibonite": 0.003},
    "L":  {"perovskite": 0.003, "hibonite": 0.005},
}


def _detail_mixture(row: str):
    """(PHASE_DETAIL, DETAIL_ACCESSORIES) for X or Xc, over P, M and E.

    A parent phase's split is the mixture of the members' splits of it,
    weighted by how much of that parent each member brings, so X's nickel-iron
    divides as M's, P's and E's metal would in those proportions.  Its new
    accessories are the members', by mass, as `_mixture` weights them.
    """
    counts = dict(zip(X_SPLIT_CLASSES, X_SPLIT_COUNTS[row]))
    mass = {c: n * TAXONOMY_COMPOSITION[c]["density_est_gcm3"] for c, n in counts.items()}
    total = sum(mass.values())
    num: Dict[str, Dict[str, float]] = {}
    den: Dict[str, float] = {}
    extra: Dict[str, float] = {}
    for c, m in mass.items():
        split = PHASE_DETAIL.get(c, {})
        for phase, frac in phase_fractions(c).items():   # P, M, E are typed
            w = m * frac
            den[phase] = den.get(phase, 0.0) + w
            into = num.setdefault(phase, {})
            for finer, share in split.get(phase, {phase: 1.0}).items():
                into[finer] = into.get(finer, 0.0) + w * share
        for phase, frac in DETAIL_ACCESSORIES.get(c, {}).items():
            extra[phase] = extra.get(phase, 0.0) + m * frac / total
    detail = {p: {q: v / den[p] for q, v in num[p].items()}
              for p in num if den[p] > 0 and set(num[p]) != {p}}
    return detail, extra


def detailed_fractions(cls: str) -> Optional[Dict[str, float]]:
    """`phase_fractions` with each family resolved, plus the new accessories.

    None for a class with no phases.  A phase of `comp_phases` with no
    `PHASE_DETAIL` entry passes through, so every entry of the coarser column
    is the sum of its detailed phases; tests/test_mineralogy.py holds it.
    """
    fracs = phase_fractions(cls)
    if fracs is None:
        return None
    split = PHASE_DETAIL.get(cls, {})
    out: Dict[str, float] = {}
    for phase, frac in fracs.items():
        for finer, share in split.get(phase, {phase: 1.0}).items():
            if share > 0:
                out[finer] = out.get(finer, 0.0) + frac * share
    for phase, frac in DETAIL_ACCESSORIES.get(cls, {}).items():
        if frac > 0:
            out[phase] = out.get(phase, 0.0) + frac
    return _in_table_order(out)


def phases_detailed_json(cls: str) -> Optional[str]:
    """`detailed_fractions` as the JSON a build writes to `comp_phases_detailed`."""
    fracs = detailed_fractions(cls)
    if fracs is None:
        return None
    return json.dumps(fracs, separators=(",", ":"))


# After the 1.7.0 derivation above, because the mixture reads phase_fractions.
for _row_name in X_SPLIT_ROWS:
    PHASE_DETAIL[_row_name], DETAIL_ACCESSORIES[_row_name] = _detail_mixture(_row_name)
del _row_name
