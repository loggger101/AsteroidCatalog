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
because its source came first.  None of the four is possible: nothing is
denser than iron, and a carbonaceous body is not denser than the densest
carbonaceous rock.  (JPL's GM for Hygiea and Interamnia are quoted to ONE
significant figure, 7.0 and 5.0 km^3/s^2, and are superseded by the
literature SsODNet compiles.)

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

from .taxonomy import TAXONOMY_COMPOSITION

# ─────────────────────────────────────────────────────────────────────────────
# BULK DENSITY  (g/cm3)
# ─────────────────────────────────────────────────────────────────────────────
# A body's bulk density is its grain density times (1 - porosity), and porosity
# cannot be negative, so NO BODY IS DENSER THAN THE ROCK IT IS MADE OF.  The
# ceiling for a spectral group is therefore the grain density of the densest
# meteorite that group could be made of, at zero porosity (grain densities from
# Consolmagno, Britt & Macke 2008, Chemie der Erde 68, 1; Macke 2010):
#
#   carbonaceous & primitive   CI 2.46, CM 2.90, CR 3.1, CO/CV/CK 3.4-3.6
#       (C-complex, D, T)      -> 3.6
#   stony                      ordinary chondrites 3.5-3.7, mesosiderites
#       (S-complex, Q, K, L,     ~4.3, pallasites ~4.8: a stony-iron still
#        A, O, R, V)             shows a silicate spectrum
#                              -> 5.0
#   X-complex & untyped        could be solid iron-nickel, 7.9
#                              -> 8.0
#
# The floor is the same for everyone: the most porous small bodies measured are
# comet nuclei and TNO binaries at ~0.3-0.5 g/cm3 (67P 0.53, Tempel 1 ~0.4),
# ~75% empty space around grains as light as water ice.  0.25 leaves margin
# under all of them.
#
# The table is keyed on TAXONOMY_COMPOSITION's `group`, so a class inherits its
# group's limits and a class added there needs no entry here unless it opens a
# new group; `test_every_taxonomy_group_has_density_limits` checks that.
DENSITY_FLOOR_GCM3 = 0.25
DENSITY_LIMITS_GCM3 = {
    "C-complex": (DENSITY_FLOOR_GCM3, 3.6),
    "D-type":    (DENSITY_FLOOR_GCM3, 3.6),
    "T-type":    (DENSITY_FLOOR_GCM3, 3.6),
    "S-complex": (DENSITY_FLOOR_GCM3, 5.0),
    "Q-type":    (DENSITY_FLOOR_GCM3, 5.0),
    "K-type":    (DENSITY_FLOOR_GCM3, 5.0),
    "L-type":    (DENSITY_FLOOR_GCM3, 5.0),
    "A-type":    (DENSITY_FLOOR_GCM3, 5.0),
    "O-type":    (DENSITY_FLOOR_GCM3, 5.0),
    "R-type":    (DENSITY_FLOOR_GCM3, 5.0),
    "V-type":    (DENSITY_FLOOR_GCM3, 5.0),
    "X-complex": (DENSITY_FLOOR_GCM3, 8.0),
    "Unknown":   (DENSITY_FLOOR_GCM3, 8.0),
}
# The limits for a body whose class is not known: anything but iron-and-more.
DENSITY_LIMITS_ANY_GCM3 = DENSITY_LIMITS_GCM3["Unknown"]

# ─────────────────────────────────────────────────────────────────────────────
# GEOMETRIC ALBEDO
# ─────────────────────────────────────────────────────────────────────────────
# A value of 1 or more is a fit that ran into its ceiling, not a surface: JPL
# carries 24 albedos of exactly 1.000 (SsODNet gives 0.52-0.91 for the same
# bodies), and derive.py already refused to size a body from one.  The floor is
# only used to judge an albedo the catalog would otherwise have to INVENT (see
# enrich.py): nothing in the Solar System is darker than ~0.02, and 0.01 leaves
# margin under the darkest NEOWISE fits.
ALBEDO_CEILING = 1.0
ALBEDO_FLOOR = 0.01

# D_km = H_DIAMETER_CONSTANT / sqrt(p_V) * 10**(-H/5); see derive.py.
H_DIAMETER_CONSTANT = 1329.0

# ─────────────────────────────────────────────────────────────────────────────
# ROTATION
# ─────────────────────────────────────────────────────────────────────────────
# A body held together by gravity alone sheds its equator when it spins faster
# than a satellite skimming its surface would orbit:
#
#     P_min = sqrt(3 pi / (G rho))            3.3 h / sqrt(rho in g/cm3)
#
# Above ~10 km, self-gravity dwarfs any plausible cohesion (Holsapple 2007), so
# the limit is hard.  It is evaluated at the density CEILING for the body's
# group, which is the fastest spin that group could survive; an elongated body
# fails sooner still.  Smaller bodies can be held by cohesion, and real ones
# spin in minutes, so nothing under 10 km is judged.
#
# The size used is the smallest the body could be: its measured diameter, or,
# with none, the diameter it would have at albedo 1 (H alone bounds it).
SPIN_LIMIT_MIN_DIAMETER_KM = 10.0
G_SI = 6.67430e-11

# Anything beyond Jupiter's aphelion (5.46 AU) is a Centaur or a TNO: an icy,
# organic-rich body, whatever its albedo says.  See enrich.py.
OUTER_SOLAR_SYSTEM_AU = 5.5
OUTER_SOLAR_SYSTEM_CLASS = "D"


def taxonomy_group(spec_type) -> str:
    """The TAXONOMY_COMPOSITION group of a class as a source spells it.

    Normalised the way enrich_composition normalises (first letter upper, rest
    lower), then the exact class, then its root letter, as `_lookup` does:
    "S(iv)" -> "S" -> "S-complex", "Bk" -> "B" -> "C-complex".  Anything else
    is "Unknown".
    """
    if spec_type is None or (not isinstance(spec_type, str) and pd.isna(spec_type)):
        return "Unknown"
    s = str(spec_type).strip()
    if not s or s.lower() in ("nan", "none", "na", "-"):
        return "Unknown"
    s = s[0].upper() + s[1:].lower()
    entry = TAXONOMY_COMPOSITION.get(s) or TAXONOMY_COMPOSITION.get(s[0])
    return entry["group"] if entry else "Unknown"


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
            c = c.mask(c.isin(["", "nan", "None", "NaN", "none", "NA", "-"]))
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
        v = np.asarray(mass_kg, dtype="float64") / (np.asarray(density_gcm3, dtype="float64") * 1_000.0)
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
