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

from typing import Dict, Tuple

import numpy as np
import pandas as pd

from ._frame import flag
from ._log import say

from .config import CatalogConfig
from .physics import H_DIAMETER_CONSTANT
from .taxonomy import _BLANK_CLASSES, _bus_demeo_case

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
# (Fowler & Chillemi 1992.  The 1329 km constant is 2 AU * 10**(V_sun/5) with
# the Sun's V = -26.762 +/- 0.017, i.e. 1329 +/- 10 km; Pravec & Harris 2007,
# Icarus 190, 250, Appendix A, derive it and note that it has been the
# standard since the IRAS Minor Planet Survey.  physics.H_DIAMETER_CONSTANT.)
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
# tables are medians over bodies that HAVE a measured albedo, and those
# measurements are overwhelmingly NEOWISE, a thermal-infrared survey.
# At a fixed H a darker body must be larger, and a larger warmer body is easier
# for a thermal survey to detect, so the measured sample over-represents dark
# bodies relative to the 1.4 M that were never measured.  A median that is too
# LOW yields a diameter that is too LARGE and a mass that is too large by the
# 1.5 power.  Do not "correct" this by raising the table to taste; that is the
# same move CLAUDE.md rejects for IN_SPACE_UTILITY.  Quantifying it needs a
# debiased size-frequency model, which this module does not have.

# Median measured geometric albedo per spectral type.  DERIVED, not asserted.
#
# RECOMPUTED FOR 1.4.0 ON THE LABELS IT IS APPLIED TO.  The 1.1.0 table was
# medians over the 1,897 bodies carrying a JPL (spec_B / spec_T) class, but it
# sizes the bodies whose class came from ANY source, and by the 2026-09-23
# release that was 105,873 bodies, most of them typed by SsODNet.  On those
# labels the old medians were off by up to 72%: D 0.0509 against 0.0820 over
# 2,127 bodies, T 0.0645 against 0.111, K 0.142 against 0.184, V 0.388 against
# 0.336, and subclasses the old table lacked fell to their root letter (Ds,
# median 0.1265, sized as D at 0.0509: 58% too large).
#
# Now: every class with n >= 5 among the 65,159 bodies of the data-2026-09-23
# release with a source-given class and a measured 0 < albedo < 1, the albedo
# being the catalog's own (`albedo`, JPL-first, i.e. NEOWISE-era; see README
# section 4).  Classes are spelled as enrich_composition capitalises them.
# Classes with n < 5 are ABSENT rather than guessed; they fall through the chain
# in `_albedo_for_derivation` below, first to their root letter.
#
# RE-RUNNABLE, NOT ASSERTED: `tools/albedo_tables.py <catalog>` recomputes this
# table and the three below from a built catalog and exits non-zero on drift.
# On data-2026-09-26 it reproduces 46 of 47 classes to 0.005 (E has grown to
# n=37, median 0.596) and every orbital bin to 0.001.
ALBEDO_BY_SPECTRAL_TYPE: Dict[str, float] = {
    "A":    0.2620,   # n=709
    "Ad":   0.1820,   # n=113
    "B":    0.0670,   # n=3,723
    "Bk":   0.0850,   # n=102
    "C":    0.0620,   # n=22,018
    "Cb":   0.0550,   # n=82
    "Cd":   0.0575,   # n=10
    "Cg":   0.0530,   # n=19
    "Cgh":  0.0630,   # n=48
    "Cgx":  0.0880,   # n=134
    "Ch":   0.0520,   # n=398
    "Cl":   0.1880,   # n=5
    "Co":   0.0560,   # n=8
    "Cx":   0.0590,   # n=197
    "D":    0.0820,   # n=2,127
    "Dl":   0.1775,   # n=58
    "Ds":   0.1265,   # n=278
    "E":    0.5828,   # n=32
    "K":    0.1840,   # n=1,046
    "Kl":   0.1190,   # n=434
    "L":    0.2030,   # n=1,781
    "Ld":   0.1730,   # n=25
    "Ls":   0.2220,   # n=258
    "M":    0.1330,   # n=139
    "O":    0.1345,   # n=10
    "P":    0.0520,   # n=255
    "Q":    0.2520,   # n=335
    "Qv":   0.1968,   # n=8
    "R":    0.3165,   # n=14
    "S":    0.2340,   # n=20,057
    "S:":   0.2320,   # n=12
    "Sa":   0.2515,   # n=46
    "Sk":   0.2335,   # n=22
    "Sl":   0.2310,   # n=55
    "Sq":   0.2440,   # n=157
    "Sr":   0.2614,   # n=26
    "Sv":   0.2875,   # n=20
    "T":    0.1110,   # n=47
    "V":    0.3355,   # n=2,038
    "X":    0.0800,   # n=7,932
    "Xc":   0.0880,   # n=73
    "Xd":   0.0740,   # n=83
    "Xe":   0.1990,   # n=43
    "Xk":   0.1055,   # n=64
    "Xl":   0.1340,   # n=17
    "Xt":   0.1115,   # n=68
    "Z":    0.0650,   # n=33
}

# E-types were the known casualty of the 1.1.0 table (four measured, so absent,
# so sized off their orbital bin at a quarter of an enstatite surface's
# albedo).  The 1.4.0 sample has 32, median 0.583.

# Median measured geometric albedo by semi-major axis.  THIS is the branch
# that sizes most of the catalog: 1,310,985 bodies of the 2026-09-23 release
# have nothing but H and an orbit.
#
# The gradient is the well-known compositional zoning of the belt, S-complex
# inner, C-complex outer.  Bin edges are the Kirkwood gaps (3:1 at 2.50 AU,
# 5:2 at 2.82, 2:1 at 3.27), the Hildas' outer edge, and Jupiter's aphelion.
#
# SPLIT BY POPULATION IN 1.4.0.  The 1.1.0 table binned on a alone, and the
# re-check against the data-2026-09-23 release's JPL albedos found three
# populations sharing a bin they do not share an albedo with:
#
#   * NEOs are darker than the belt at the same a, by 1.4-2.4x: 0.170 against
#     0.4135 at 1.3-2.0 AU (2.4x, the bright Hungarias), 0.137 against 0.190
#     in the inner belt (1.4x), 0.037 against 0.066 beyond 2.82 AU (1.8x).
#     The old 1.3-2.0 value, 0.2885, was a blend of NEOs and Hungarias that fits
#     neither: 38,367 NEOs were sized off the belt, up to 1.3x too small
#     (2.2x too light), and 30,232 Hungarias 1.2x too large.
#   * The "Centaur / TNO" bin, a >= 5.2, was 1,228 of 1,231 Jupiter Trojans
#     (a 5.2-5.5): 0.069 is a Trojan median, and half the Trojans sat on the
#     other side of the edge in the Hilda bin at 0.061.
#   * Beyond Jupiter, JPL has 68 albedos (mostly NEOWISE Centaurs, 0.0595);
#     SsODNet has the Herschel and Spitzer TNO albedos, 125 more.  So that
#     one bin takes every provider: 0.088 over 193.  Elsewhere it is JPL's
#     albedos, as before, so the table stays on the H the `albedo` column
#     carries (README section 4).
#
# A SECOND READING OF THE BELT BINS: the same medians over EVERY provider's
# albedo run 3-7% lower (inner belt 0.176 against 0.190, outer 0.064 against
# 0.066, data-2026-09-26).  That is the direction SsODNet's albedos run, 22%
# under JPL's because it re-derives them from today's fainter H (README
# section 4), diluted by JPL's majority of the sample.  So the two readings
# differ by a known offset, not about the bodies; the table keeps JPL's.
#
# (a_min, a_max, median p_V, label); `n` is the measured sample.
ALBEDO_BY_SEMI_MAJOR_AXIS_AU: Tuple[Tuple[float, float, float, str], ...] = (
    (0.000,  1.300, 0.1870, "Aten / Apollo"),          # n=296 (all NEOs)
    (1.300,  2.000, 0.4135, "Hungaria / Mars-crosser"),  # n=498
    (2.000,  2.500, 0.1900, "inner belt"),             # n=29,638
    (2.500,  2.820, 0.0860, "middle belt"),            # n=45,778
    (2.820,  3.270, 0.0660, "outer belt"),             # n=57,089
    (3.270,  3.700, 0.0570, "Cybele"),                 # n=1,118
    (3.700,  4.600, 0.0550, "Hilda"),                  # n=1,154
    (4.600,  5.500, 0.0700, "Jupiter Trojan"),         # n=1,891
    (5.500,  1e9,   0.0880, "Centaur / TNO"),          # n=193, every provider
)

# The same, for near-Earth objects (JPL `neo`, q < 1.3 AU), which take it in
# preference wherever they have a row.  Beyond 2.82 AU they are few (83) and
# pooled: they are the dark, often cometary, end of the population.
ALBEDO_BY_SEMI_MAJOR_AXIS_AU_NEO: Tuple[Tuple[float, float, float, str], ...] = (
    (0.000,  1.300, 0.1870, "NEO, Aten / Apollo"),     # n=296
    (1.300,  2.000, 0.1700, "NEO, 1.3-2.0 AU"),        # n=407
    (2.000,  2.500, 0.1370, "NEO, inner belt"),        # n=282
    (2.500,  2.820, 0.0620, "NEO, middle belt"),       # n=135
    (2.820,  1e9,   0.0370, "NEO, outer"),             # n=83
)

# BEYOND JUPITER, BY H, NOT ONE VALUE.  Past 5.5 AU the brighter bodies are
# the BIG ones, and big trans-Neptunian objects are icier and brighter: over
# the 193 measured, the median runs 0.147 at H 3-6 (n=64) down to 0.0585 past
# H 8 (n=86), the size-albedo trend of the Herschel "TNOs are Cool" survey.
# One value (0.088) sized 532037 Chiminigagua (H 3.09) at 1,219 km against
# ~740 measured, and made it the eighth-heaviest body in the catalog.  The
# `Centaur / TNO` row of ALBEDO_BY_SEMI_MAJOR_AXIS_AU is the fallback for a body
# with no H.
# (h_max, median p_V, label), first match wins.
ALBEDO_BEYOND_JUPITER_BY_H: Tuple[Tuple[float, float, str], ...] = (
    (3.0,   0.4481, "dwarf planet, H <= 3"),           # n=7
    (6.0,   0.1468, "large TNO, H 3-6"),               # n=64
    (7.0,   0.0871, "TNO, H 6-7"),                     # n=23
    (8.0,   0.0755, "TNO, H 7-8"),                     # n=13
    (1e9,   0.0585, "small TNO / Centaur, H > 8"),     # n=86
)

# Overall median across the whole measured sample.  Last resort only: used for
# a body with no albedo, no usable taxonomy and no semi-major axis, which in
# practice cannot happen because validate_and_filter requires an orbit anyway.
ALBEDO_FALLBACK = 0.0780

# D_km = _H_DIAMETER_CONSTANT / sqrt(p_V) * 10**(-H/5).  ONE definition, in
# physics.py, which the screens invert; this name stays because
# tools/extraction_probe.py reads it.  Until 1.5.0 it was a second literal.
_H_DIAMETER_CONSTANT = H_DIAMETER_CONSTANT


def _albedo_from_taxonomy(t: object) -> float:
    """Median geometric albedo for a spectral type, or NaN if unknown.

    Falls back to the ROOT letter ("Sq2" to "S"), as the composition lookup
    does (`taxonomy.composition_entry`), so a sub-type nobody tabulated still
    sizes off its complex rather than dropping out of the catalog.
    """
    if not isinstance(t, str) or not t.strip():
        return np.nan
    # Capitalised as enrich_composition capitalises (1.4.0).  Sources write
    # "SQ" and "SA" as well as "Sq" and "Sa"; the exact lookup missed them and
    # fell to the S median, sizing 663 bodies of the 2026-09-23 release 6% too
    # large (20% too heavy).
    s = _bus_demeo_case(t.strip())
    if s in ALBEDO_BY_SPECTRAL_TYPE:
        return ALBEDO_BY_SPECTRAL_TYPE[s]
    return ALBEDO_BY_SPECTRAL_TYPE.get(s[0], np.nan)


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
    #
    # "No classification" is read exactly as enrich_composition reads it
    # (1.4.1).  With a narrower list here, a Bus column holding "-" or "<NA>"
    # blocked the Tholen fallback: the body was sized off its orbit bin while
    # enrich_composition typed it by its Tholen class, so its size and its
    # composition rested on two different albedos.
    tax = pd.Series(pd.NA, index=df.index, dtype="object")
    for col in ("spectral_type", "spectral_type_tholen"):
        if col in df.columns:
            candidate = df[col].astype("string").str.strip()
            candidate = candidate.replace(dict.fromkeys(_BLANK_CLASSES, pd.NA))
            tax = tax.where(tax.notna(), candidate)

    need = albedo.isna() & tax.notna()
    if need.any():
        derived_tax = tax[need].map(_albedo_from_taxonomy)
        albedo.loc[need] = derived_tax
        label[need & albedo.notna()] = "taxonomy_albedo"

    # ── 3. Orbital bin ────────────────────────────────────────────────────────
    if "semi_major_axis_au" in df.columns:
        a = pd.to_numeric(df["semi_major_axis_au"], errors="coerce")
        neo = flag(df, "is_neo")
        if "absolute_magnitude_h" in df.columns:
            h = pd.to_numeric(df["absolute_magnitude_h"], errors="coerce")
            outer = albedo.isna() & (a >= ALBEDO_BY_SEMI_MAJOR_AXIS_AU[-1][0]) & h.notna()
            for h_max, p_v, _lbl in ALBEDO_BEYOND_JUPITER_BY_H:
                band = outer & albedo.isna() & (h <= h_max)
                albedo.loc[band] = p_v
                label[band] = "orbit_albedo"
        for table, who in ((ALBEDO_BY_SEMI_MAJOR_AXIS_AU_NEO, neo),
                           (ALBEDO_BY_SEMI_MAJOR_AXIS_AU, ~neo | neo)):
            for a_min, a_max, p_v, _lbl in table:
                band = albedo.isna() & who & a.notna() & (a >= a_min) & (a < a_max)
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
