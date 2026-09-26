# -*- coding: utf-8 -*-
"""What a small body can physically be, and the arithmetic that checks it.

A CATALOG THAT PUBLISHES AN IMPOSSIBLE NUMBER IS WRONG, HOWEVER WELL SOURCED
THE NUMBER IS.  The 2026-09-23 release (data contract 1.3.0) carried, among
others:

    1686 De Sitter    6.76e18 kg on a 29.7 km body     495 g/cm3   MP3C
    152 Atala         5.43e18 kg on a 59.0 km body      51 g/cm3   MP3C
    704 Interamnia    7.49e19 kg, a B-type              5.0 g/cm3  JPL GM = 5.0
    10 Hygiea         1.05e20 kg                        2.97 g/cm3 JPL GM = 7.0

Every one of them was a real value in a real source, and the merge took it
because its source came first.  The first three are impossible: nothing is
denser than iron, and a carbonaceous body is not denser than the densest
carbonaceous rock.  Hygiea's is possible and superseded, which is a matter of
precedence (merge.py), not of limits.  (JPL's GM for Hygiea and Interamnia are
quoted to ONE significant figure, 7.0 and 5.0 km^3/s^2, and are superseded by
the literature SsODNet compiles.)

This module holds the limits and nothing else, so the merge, the enrichment
and the release gate all check against one definition.

THE LIMITS ARE WHAT IS POSSIBLE, NOT WHAT IS LIKELY.  Each is set from a
physical argument with a margin, so a value outside one is wrong rather than
merely surprising.  A value inside one can still be wrong; the agreement
columns are the tool for that.
"""

from typing import Tuple

import numpy as np
import pandas as pd

from .taxonomy import _BLANK_CLASSES, _bus_demeo_case, composition_entry

# ─────────────────────────────────────────────────────────────────────────────
# BULK DENSITY  (g/cm3)
# ─────────────────────────────────────────────────────────────────────────────
# A body's bulk density is its grain density times (1 - porosity), and porosity
# cannot be negative, so NO BODY IS DENSER THAN THE ROCK IT IS MADE OF.  The
# ceiling for a spectral group is the grain density of the densest meteorite
# that could show that group's spectrum, at zero porosity.
#
#   carbonaceous               CI 2.42 (Orgueil), CM 2.92 (2.74-3.26), CO/CV
#       (C-complex, D, and       ~3.0-3.6 (Consolmagno, Britt & Macke 2008,
#        K and L, the CV/CO      Chemie der Erde 68, 1; Macke et al. 2011,
#        analogues)              MAPS 46, 1842)
#                              -> 3.6
#       The CB chondrites reach 5.66 (Bencubbin), but they are 60-70% metal
#       and are not what a C-complex spectrum is matched to.
#
#       ⚠️  K IS THE CLASS THIS CEILING FITS MOST TIGHTLY.  The only K-type
#       whose density Carry (2012, Planet. Space Sci. 73, 98, Table 3) has to
#       20% is 15 Eunomia at 3.54 +/- 0.20, 0.3 sigma under 3.6.  A K-type mass
#       refused here is worth reading before it is believed wrong.
#
#   everything else            5.0, and this one is REALISM, not physics.
#                              Physically a stony-iron lies between its
#                              silicate (~3.3) and its metal (iron 7.87), in
#                              proportion to the metal it carries, which is
#                              why the release gate still uses 8.0
#                              (DENSITY_LIMITS_ANY_GCM3).  But the densest
#                              asteroid MEASURED is 22 Kalliope, 4.40 +/- 0.46
#                              (Ferrais et al. 2022, A&A 662, A71); the other
#                              M-types measured by adaptive optics run
#                              3.4-4.2 (Kleopatra, Psyche).  The catalog
#                              agrees: of the 77 bodies of data-2026-09-26
#                              with a mass known to 5%, the densest are
#                              Kalliope 4.18 and Psyche 4.14, then 110 Lydia
#                              3.54.  In the 2026-09-23 release every value
#                              over 5 came from a mass good to 12-56% or a
#                              radiometric diameter, so 5.0 (Kalliope plus
#                              one sigma is 4.86) is the ceiling a mass must
#                              meet to be believed.  One that fails is
#                              replaced by the class estimate, which is
#                              realistic.
#
#   ⚠️  1.4.0 as first written capped stony groups at 5.0 as IMPOSSIBLE on
#   "pallasites ~4.8"; a pallasite can carry far more metal than that, so it
#   was wrong as physics.  The same 5.0 is right as the measured record, and
#   is labelled as such.  (Until 1.5.0 this note said nothing had been
#   measured above ~4.2, which Kalliope contradicts.)
#
# The floor is the same for everyone: the most porous small bodies measured are
# comet nuclei, 67P at 0.533 +/- 0.006 (Paetzold et al. 2016, Nature 530, 63)
# and 9P/Tempel 1 at 0.47 +0.78/-0.24 (Thomas et al. 2013, Icarus, from the
# Deep Impact ejecta), ~75% empty space around grains as light as water ice.
# Carry (2012) averages the comets known to 20% at 0.54 +/- 0.09.  0.25
# leaves margin under all of them.
#
# The table is keyed on TAXONOMY_COMPOSITION's `group`, so a class inherits its
# group's limits and a class added there needs no entry here unless it opens a
# new group; `test_every_taxonomy_group_has_density_limits` checks that.
DENSITY_FLOOR_GCM3 = 0.25
_CARBONACEOUS_CEILING = 3.6
_MEASURED_RECORD_CEILING = 5.0
_IRON_CEILING = 8.0
DENSITY_LIMITS_GCM3 = {
    "C-complex": (DENSITY_FLOOR_GCM3, _CARBONACEOUS_CEILING),
    "D-type":    (DENSITY_FLOOR_GCM3, _CARBONACEOUS_CEILING),
    "K-type":    (DENSITY_FLOOR_GCM3, _CARBONACEOUS_CEILING),
    "L-type":    (DENSITY_FLOOR_GCM3, _CARBONACEOUS_CEILING),
    "T-type":    (DENSITY_FLOOR_GCM3, _MEASURED_RECORD_CEILING),
    "S-complex": (DENSITY_FLOOR_GCM3, _MEASURED_RECORD_CEILING),
    "Q-type":    (DENSITY_FLOOR_GCM3, _MEASURED_RECORD_CEILING),
    "A-type":    (DENSITY_FLOOR_GCM3, _MEASURED_RECORD_CEILING),
    "O-type":    (DENSITY_FLOOR_GCM3, _MEASURED_RECORD_CEILING),
    "R-type":    (DENSITY_FLOOR_GCM3, _MEASURED_RECORD_CEILING),
    "V-type":    (DENSITY_FLOOR_GCM3, _MEASURED_RECORD_CEILING),
    "X-complex": (DENSITY_FLOOR_GCM3, _MEASURED_RECORD_CEILING),
    "Unknown":   (DENSITY_FLOOR_GCM3, _MEASURED_RECORD_CEILING),
}
# What NO body can exceed, whatever its class: the release gate's bound.
DENSITY_LIMITS_ANY_GCM3 = (DENSITY_FLOOR_GCM3, _IRON_CEILING)

# ─────────────────────────────────────────────────────────────────────────────
# GEOMETRIC ALBEDO
# ─────────────────────────────────────────────────────────────────────────────
# A value of 1 or more is a fit that ran into its ceiling, not a surface: JPL
# carries 24 albedos of exactly 1.000 (SsODNet gives 0.52-0.91 for the same
# bodies), and derive.py already refused to size a body from one.  The floor is
# only used to judge an albedo the catalog would otherwise have to INVENT (see
# enrich.py): the darkest whole bodies measured are comet nuclei, 19P/Borrelly
# at 0.029 +/- 0.006 (Buratti et al. 2004, Icarus 167, 16) and 28P/Neujmin 1
# at much the same, and 0.01 leaves margin under them and under the darkest
# NEOWISE fits.  Since 1.4.0 a MEASURED albedo under the floor is refused as
# well: the 2026-09-23 release carried 43, down to 0.0007 (2010 HK22), darker
# than any whole body ever measured.
ALBEDO_CEILING = 1.0
ALBEDO_FLOOR = 0.01

# D_km = H_DIAMETER_CONSTANT / sqrt(p_V) * 10**(-H/5).  The one copy of the
# constant: derive.py sizes bodies with it and the screens below invert it.
#
# It is 2 AU * 10**(V_sun/5) with the Sun's V = -26.762 +/- 0.017 (Campins et
# al. 1985), 1329 +/- 10 km: the value the IRAS Minor Planet Survey used
# (Fowler & Chillemi 1992), derived in Appendix A of Pravec & Harris (2007,
# Icarus 190, 250).  The V_sun uncertainty is a ~1% systematic in diameter,
# 3% in mass, well inside the albedo's.  tests/test_physics.py re-derives it.
H_DIAMETER_CONSTANT = 1329.0
AU_KM = 1.495978707e8          # IAU 2012 Resolution B2, exact
V_SUN = -26.762

# A MEASURED DIAMETER MUST BE THE SIZE OF THE BODY WHOSE H IT SITS BESIDE.
# Together they imply an albedo, and it must be one a surface can have, to
# within the H error.  Catalog H values are systematically too bright for
# small bodies: by -0.4 to -0.5 mag on average at H ~ 14 (Pravec et al. 2012,
# Icarus 221, 365), and in the 2026-09-22 sources NEOWISE's H runs 0.28 mag
# brighter than JPL's (README section 4).  0.75 mag is a margin chosen over
# that mean offset for the scatter about it, not a measured worst case.  So
# the implied albedo may run from ALBEDO_FLOOR to ALBEDO_CEILING widened by
# 0.75 mag each way, 0.005 to 2.0.  Outside that the diameter belongs to
# another body (a mislinked detection: 2010 BK37 is 1.95 km beside an H of
# 23.97, p_V 0.0001) or is a failed fit (303876, SsODNet 14.6 km at p_V
# 0.0027 with every source agreeing on H); 18 in the 2026-09-23 release.
H_DIAMETER_TOLERANCE_MAG = 0.75
IMPLIED_ALBEDO_RANGE = (ALBEDO_FLOOR * 10 ** (-0.4 * H_DIAMETER_TOLERANCE_MAG),
                        ALBEDO_CEILING * 10 ** (0.4 * H_DIAMETER_TOLERANCE_MAG))

# ─────────────────────────────────────────────────────────────────────────────
# ROTATION
# ─────────────────────────────────────────────────────────────────────────────
# A body held together by gravity alone sheds its equator when it spins faster
# than a satellite skimming its surface would orbit:
#
#     P_min = sqrt(3 pi / (G rho))            3.3 h / sqrt(rho in g/cm3)
#
# (Pravec & Harris 2000, Icarus 148, 12, who give 3.3 h * sqrt((1 + A)/rho)
# for a lightcurve amplitude A; this takes the sphere, A = 0.)  Above ~10 km
# gravity stresses dominate strength (Holsapple 2007, Icarus 187, 500), so the
# limit is hard.  It is evaluated at the density CEILING for the body's
# group, which is the fastest spin that group could survive: 1.74 h at 3.6
# g/cm3, 1.48 h at 5.0, both faster than the ~2.2 h spin barrier observed
# among asteroids larger than a few hundred metres, so the screen refuses only
# what theory AND the observed population both rule out.  An elongated body
# fails sooner still.  Smaller bodies can be held by cohesion, and real ones
# spin in minutes, so nothing under 10 km is judged.
#
# The size used is the smallest the body could be: its measured diameter, or,
# with none, the diameter it would have at albedo 1 (H alone bounds it).
SPIN_LIMIT_MIN_DIAMETER_KM = 10.0
G_SI = 6.67430e-11

# From the Jupiter Trojans outward (a > 4.6 AU), an untyped body is taken as
# D: icy and organic-rich past Jupiter, whatever its albedo says, and D is the
# Trojans' commonest class.  4.6 AU is a CHOICE, not a published boundary: it
# sits in the sparse gap between the Hildas (the 3:2 resonance, ~3.7-4.2 AU,
# 8,268 bodies in data-2026-09-26) and the Trojans (~5.05-5.35 AU, 16,104),
# which holds 469.  Moving it 0.2 AU either way re-types 59-89 untyped bodies
# of the 23,311 typed D from their orbit.  Of the 1,559 Trojans with a source
# class in the 2026-09-23 release, 36.5% are D and 24.6% C-complex (almost
# all labelled C; P is 1.7%); albedo inference had typed all 14,879 untyped
# ones C.  Spectroscopy puts about three quarters of the Trojans studied at
# featureless D (Emery et al. 2011, AJ 141, 25, and the surveys they
# compile), so the source classes, if anything, under-count D.  The Hildas
# inside 4.6 AU are C-complex first (37%) and keep the inference; the
# literature calls them P/D bimodal (Gil-Hutton & Brunini 2008), and a
# Tholen P is a dark X or C in the later taxonomies the sources use.  See
# enrich.py.
OUTER_SOLAR_SYSTEM_AU = 4.6
OUTER_SOLAR_SYSTEM_CLASS = "D"

# Past Jupiter's aphelion (5.46 AU) the asteroid taxonomy stops describing
# composition: a TNO's "S" or "C" is a colour class fitted with asteroid
# templates, and an icy body is not stony rock.  39 TNOs with a source class
# and no measured mass were given the class's rock density (Ixion, S: 2.7
# g/cm3, 5.05e20 kg, where TNOs of its size measure 1.2-1.5; Carry 2012
# averages the TNOs known to 20% at 1.06 +/- 0.75).  Beyond this, composition is taken
# from OUTER_SOLAR_SYSTEM_CLASS whatever the label; `spectral_type` keeps the
# source's label.
ICY_COMPOSITION_AU = 5.5


def taxonomy_group(spec_type) -> str:
    """The TAXONOMY_COMPOSITION group of a class as a source spells it.

    Normalised the way enrich_composition normalises (first letter upper, rest
    lower), then looked up as enrich_composition looks it up, exact class
    first and root letter second: "S(iv)" -> "S" -> "S-complex", "Bk" -> "B"
    -> "C-complex".  Anything else is "Unknown".
    """
    if spec_type is None or (not isinstance(spec_type, str) and pd.isna(spec_type)):
        return "Unknown"
    s = str(spec_type).strip()
    if s in _BLANK_CLASSES:
        return "Unknown"
    return composition_entry(_bus_demeo_case(s))["group"]


def density_limits(groups: pd.Series) -> Tuple[np.ndarray, np.ndarray]:
    """(floor, ceiling) arrays for a column of taxonomy groups."""
    g = pd.Series(groups).astype("object")
    lo = g.map({k: v[0] for k, v in DENSITY_LIMITS_GCM3.items()})
    hi = g.map({k: v[1] for k, v in DENSITY_LIMITS_GCM3.items()})
    return (lo.fillna(DENSITY_LIMITS_ANY_GCM3[0]).to_numpy(dtype="float64"),
            hi.fillna(DENSITY_LIMITS_ANY_GCM3[1]).to_numpy(dtype="float64"))


def groups_of(df: pd.DataFrame) -> pd.Series:
    """Each row's taxonomy group from whatever classification it carries.

    Bus-DeMeo (`spectral_type`) first, then Tholen, as enrich_composition
    prefers them.  Evaluated once per distinct class.
    """
    t = pd.Series(pd.NA, index=df.index, dtype="object")
    for col in ("spectral_type", "spectral_type_tholen"):
        if col in df.columns:
            c = df[col].astype("string").str.strip()
            c = c.mask(c.isin(_BLANK_CLASSES))
            t = t.where(t.notna(), c)
    codes, uniques = pd.factorize(t, use_na_sentinel=False)
    groups = np.array([taxonomy_group(u) for u in uniques], dtype=object)
    return pd.Series(groups[codes], index=df.index)


def sphere_volume_m3(diameter_km) -> np.ndarray:
    d_m = np.asarray(diameter_km, dtype="float64") * 1_000.0
    return np.pi / 6.0 * d_m ** 3


def bulk_density_gcm3(mass_kg, diameter_km) -> np.ndarray:
    """Mass over the volume of a sphere of that diameter, in g/cm3."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.asarray(mass_kg, dtype="float64") / sphere_volume_m3(diameter_km) / 1_000.0


def diameter_from_mass_km(mass_kg, density_gcm3) -> np.ndarray:
    """The sphere of that mass at that bulk density, in km."""
    with np.errstate(divide="ignore", invalid="ignore"):
        rho_kg_m3 = np.asarray(density_gcm3, dtype="float64") * 1_000.0
        v = np.asarray(mass_kg, dtype="float64") / rho_kg_m3
        return np.cbrt(6.0 * v / np.pi) / 1_000.0


def albedo_from_h_and_diameter(h, diameter_km) -> np.ndarray:
    """The geometric albedo H and D imply together."""
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        return (H_DIAMETER_CONSTANT / np.asarray(diameter_km, dtype="float64")
                * np.power(10.0, -np.asarray(h, dtype="float64") / 5.0)) ** 2


def smallest_diameter_km(diameter_km, h) -> np.ndarray:
    """The smallest a body can be: its diameter, else its size at albedo 1."""
    d = np.asarray(diameter_km, dtype="float64")
    with np.errstate(over="ignore", invalid="ignore"):
        from_h = H_DIAMETER_CONSTANT * np.power(10.0, -np.asarray(h, dtype="float64") / 5.0)
    return np.where(d > 0, d, from_h)


def min_rotation_period_h(density_ceiling_gcm3) -> np.ndarray:
    """The fastest a strengthless sphere of that density can spin, in hours."""
    rho = np.asarray(density_ceiling_gcm3, dtype="float64") * 1_000.0
    return np.sqrt(3.0 * np.pi / (G_SI * rho)) / 3_600.0


def rotation_is_impossible(period_h, smallest_d_km, density_ceiling_gcm3) -> np.ndarray:
    """True where a body at least 10 km across spins faster than it could."""
    p = np.asarray(period_h, dtype="float64")
    big = np.asarray(smallest_d_km, dtype="float64") >= SPIN_LIMIT_MIN_DIAMETER_KM
    return big & (p < min_rotation_period_h(density_ceiling_gcm3))
