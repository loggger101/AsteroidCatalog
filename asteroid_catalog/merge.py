# -*- coding: utf-8 -*-
"""Combining the sources, and saying honestly what each contributed.

A SOURCE THAT FETCHED ROWS AND MATCHED NONE IS ALWAYS A BUG IN THAT FETCHER,
never an empty upstream table, and `merge_sources` shouts when it happens.
That is not decoration: a float-typed merge key cost NEOWISE four releases of
contributing exactly zero rows while the fetch summary reported 183,408.

ONE BODY, ONE ROW, EVERY SOURCE'S KNOWLEDGE IN IT.  Since 1.3.0:

  * every supplement row is re-keyed onto the backbone's designation before
    the join (identity.py), so a body two sources spell differently is joined,
    not duplicated or dropped;
  * duplicates are COMBINED, not culled: each column takes the first non-null
    value in completeness order, so the less complete row's data fills the
    gaps of the more complete one instead of being thrown away;
  * each measured quantity records who supplied it, how many sources report it
    and whether they agree (`MEASURED_FIELDS`).
"""

import warnings
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ._frame import numeric
from ._log import say, warn

from .designations import _designation_key, _extract_canonical_designation
from .identity import build_alias_map, resolve_designations
from .neowise import combine_neowise_fits
from .physics import (
    ALBEDO_CEILING, ALBEDO_FLOOR, IMPLIED_ALBEDO_RANGE, albedo_from_h_and_diameter,
    bulk_density_gcm3, density_limits, groups_of, rotation_is_impossible,
    smallest_diameter_km,
)

# ─────────────────────────────────────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────────────────────────────────────
def deduplicate_catalog(
    df: pd.DataFrame,
    key: str = "designation",
    label: str = "catalog",
) -> pd.DataFrame:
    """
    Collapse rows that share a normalised `key` into ONE row per body,
    COMBINING them: each column takes the first non-null value, with rows
    ranked most-complete first.  The most complete row's values win wherever
    it has one, and the other rows fill its gaps rather than being discarded.
    Reports counts so the caller can see what was combined.  Idempotent, safe
    to call multiple times in the pipeline.

    Before 1.3.0 this KEPT the most complete row and dropped the rest, so a
    body listed twice lost whatever only the second listing knew.

    Used in three places:
      1. inside merge_sources, per source, BEFORE the join, defends against
         source-internal duplicates (e.g. two designations of one body that
         identity.py re-keyed onto the same backbone designation)
      2. inside merge_sources, AFTER the join, catches duplicates introduced
         by designation variants between sources
      3. inside build_catalog, AFTER enrichment, final safety net before save
    """
    if df.empty or key not in df.columns:
        return df

    n_before = len(df)

    work = df.copy()
    work["_dedup_key"] = _designation_key(work[key])

    # Drop rows whose normalised key is null; they can't be safely grouped.
    null_key = work["_dedup_key"].isna()
    n_null   = int(null_key.sum())
    work     = work[~null_key]

    dup = work["_dedup_key"].duplicated(keep=False)
    n_groups = 0
    if dup.any():
        d = work[dup]
        # Most complete first, so `first()` prefers its values; `first()`
        # skips nulls, which is what makes this a combine rather than a cull.
        d = d.assign(_completeness=d.notna().sum(axis=1)).sort_values(
            "_completeness", ascending=False, kind="stable")
        combined = (d.drop(columns="_completeness")
                     .groupby("_dedup_key", sort=False, dropna=True).first()
                     .reset_index())
        n_groups = len(combined)
        work = pd.concat([work[~dup], combined[work.columns]], ignore_index=True)

    work = work.drop(columns=["_dedup_key"]).reset_index(drop=True)

    n_removed = n_before - len(work) - n_null

    if n_removed > 0 or n_null > 0:
        msg = []
        if n_removed > 0:
            msg.append(f"{n_removed + n_groups:,} rows for {n_groups:,} bodies "
                       f"combined into one row each")
        if n_null > 0:
            msg.append(f"{n_null:,} row(s) dropped for null designation")
        say(f"        {label}: " + "; ".join(msg))
    else:
        say(f"     OK   {label}: no duplicates detected")

    return work


# ─────────────────────────────────────────────────────────────────────────────
# MEASURED QUANTITIES: provider, source count, agreement
# ─────────────────────────────────────────────────────────────────────────────
# Quantities more than one source measures.  For each, the merge keeps the
# value from the highest-precedence source that has one (JPL, then the
# supplements in `sources` order, as before 1.3.0), keeps THAT source's sigma
# beside it, and writes four provenance columns under the stem:
#
#   <stem>_provider      which source the value came from
#   <stem>_n_sources     how many sources report a value
#   <stem>_spread        disagreement between them: max/min - 1 for a ratio
#                        quantity, max - min (mag) for H.  0 when one source.
#   <stem>_sources_agree True when 2+ sources report it and the spread is
#                        within the tolerance below; NA with fewer than 2.
#
# ⚠️  AGREEMENT IS NOT INDEPENDENT CONFIRMATION.  The catalogs share upstream
# surveys: most JPL diameters are NEOWISE fits, and ssoBFT and MP3C both
# compile NEOWISE among others.  Two sources agreeing often means one
# measurement quoted twice.  What agreement does establish is that the
# catalogs did not garble it, and a DISagreement is always informative.
#
# The tolerances are a reading of typical catalogue precision, not fitted:
#
#   diameter 10%, albedo 25%   the accuracy of a WISE/NEOWISE thermal fit
#                              against radar and spacecraft sizes, +/-10% in
#                              diameter and +/-25% in albedo (Mainzer et al.
#                              2011, ApJ 736, 100): albedo carries roughly
#                              twice diameter's relative error, as p_V ~ 1/D^2
#   H 0.30 mag                 catalog H is systematically too bright for small
#                              bodies, by -0.4 to -0.5 mag on average at
#                              H ~ 14 and under 0.1 mag for large ones (Pravec
#                              et al. 2012, Icarus 221, 365); 0.3 separates a
#                              catalog quoting an older H from one garbling it
#   mass 25%                   published masses scatter by tens of percent
#                              (Carry 2012, Planet. Space Sci. 73, 98, where
#                              only a third of 287 densities reach 20%)
#   rotation 2%                a period is precise enough that 2% catches the
#                              half/double-period ambiguity
#
# `<stem>_spread` is published so a caller can apply their own.
#
# ⚠️  PRECEDENCE PICKS AMONG POSSIBLE VALUES ONLY  (data contract 1.4.0).  Until
# 1.3.0 the first source with a value won, whatever the value was, and the
# 2026-09-23 release published a 29.7 km body at 495 g/cm3 because MP3C was
# the only source with a mass for it.  Four fields are now screened, source
# by source, BEFORE precedence applies (limits and their reasons in physics.py):
#
#   diameter_km         with the catalog's H it must imply an albedo some
#                       surface could have (IMPLIED_ALBEDO_RANGE)
#   albedo              1 or more is a fit at its ceiling, under 0.01 darker
#                       than any whole body measured
#   estimated_mass_kg   a sigma as large as the value is no determination; a
#                       mass that puts the body outside its group's possible
#                       bulk density, with the source's own diameter and with
#                       the catalog's, is not this body's mass
#   rotation_period_h   a body 10 km or more across cannot spin faster than
#                       its equator can hold on
#
# A screened value still counts in `<stem>_n_sources` and `<stem>_spread`,
# which describe what the sources SAY; `<stem>_screened_out` names the sources
# whose value was refused.
#
# MASS PRECEDENCE IS SsODNet FIRST.  JPL is the authority on orbits and
# identity, not on masses: its SBDB `GM` covers 17 bodies, carries no
# uncertainty, and gives Hygiea and Interamnia to one significant figure (7.0
# and 5.0 km^3/s^2, i.e. 1.05e20 and 7.49e19 kg, against 8.7e19 and ~3.5e19 in
# the literature: Carry 2012's weighted averages are 8.63 +/- 0.52e19 and
# 3.28 +/- 0.45e19).  ssoBFT's mass is a weighted, outlier-rejected combination
# of every published estimate, the spacecraft masses JPL quotes included (the
# two agree to 0.2% on Ceres, Vesta, Eros and Bennu).
MEASURED_FIELDS: Dict[str, dict] = {
    "absolute_magnitude_h": {"stem": "h",               "sigma": "absolute_magnitude_h_sigma",
                             "kind": "diff",  "tolerance": 0.30},
    "diameter_km":          {"stem": "diameter",        "sigma": "diameter_sigma_km",
                             "kind": "ratio", "tolerance": 0.10,
                             "screen": "h_diameter"},
    "albedo":               {"stem": "albedo",          "sigma": "albedo_sigma",
                             "kind": "ratio", "tolerance": 0.25,
                             "screen": "albedo"},
    "estimated_mass_kg":    {"stem": "mass",            "sigma": "estimated_mass_sigma_kg",
                             "kind": "ratio", "tolerance": 0.25,
                             "screen": "density", "prefer": ["SsODNet"]},
    "rotation_period_h":    {"stem": "rotation_period", "sigma": None,
                             "kind": "ratio", "tolerance": 0.02,
                             "screen": "spin"},
}
_HELD_BACK = set(MEASURED_FIELDS) | {m["sigma"] for m in MEASURED_FIELDS.values() if m["sigma"]}


def _matrix(merged: pd.DataFrame, cols: List[str]) -> np.ndarray:
    """The named columns as one float matrix, NaN where a column is absent."""
    n = len(merged)
    return np.column_stack([
        pd.to_numeric(merged[c], errors="coerce").to_numpy(dtype="float64")
        if c in merged.columns else np.full(n, np.nan) for c in cols])


def _first(usable: np.ndarray, rank: List[int]) -> np.ndarray:
    """Per row, the column index of the first usable value in `rank` order."""
    u = usable[:, rank]
    first = u.argmax(axis=1)
    return np.where(u.any(axis=1), np.asarray(rank)[first], -1)


def _names(mask: np.ndarray, order: List[str], index=None) -> pd.Series:
    """';'-joined source names per row where `mask` is set, NA where none."""
    out = np.full(len(mask), "", dtype=object)
    for j, s in enumerate(order):
        out = np.where(mask[:, j], np.where(out == "", s, out + ";" + s), out)
    return pd.Series(out, index=index, dtype="string").replace("", pd.NA)


def _say_screened(merged: pd.DataFrame, stem: str, V: np.ndarray,
                  refused: np.ndarray, order: List[str]) -> None:
    """One progress line per screened field: what was refused, from whom."""
    if not refused.any():
        say(f"     OK   {stem}: no source value refused")
        return
    per = ", ".join(f"{s} {int(refused[:, j].sum()):,}" for j, s in enumerate(order)
                    if refused[:, j].any())
    ex = []
    for i in np.flatnonzero(refused.any(axis=1))[:5]:
        j = int(refused[i].argmax())
        ex.append(f"{merged['designation'].iat[i]} ({order[j]} {V[i, j]:.4g})")
    say(f"        {stem}: {int(refused.any(axis=1).sum()):,} bodies had a value refused "
        f"as physically impossible ({per}); e.g. {', '.join(ex)}")


def _resolve_measured(merged: pd.DataFrame, order: List[str]) -> pd.DataFrame:
    """Pick each measured value by precedence, and say how the sources compare.

    `merged` holds, per source S in `order`, the columns `_<field>__<S>` (and
    `_<sigma>__<S>`) left unfilled by the join.  They are consumed here.

    Fields are resolved in MEASURED_FIELDS order, and that order is load-
    bearing: the mass screen needs the resolved diameter (and each source's
    own), and the spin screen needs the diameter the mass step settled on.
    """
    n = len(merged)
    rows = np.arange(n)
    names = np.array(order + [None], dtype=object)
    groups = None                       # taxonomy group per row, when needed
    diam = None                         # per-source diameters, for mass pairing

    for field, spec in MEASURED_FIELDS.items():
        vcols = [f"_{field}__{s}" for s in order]
        scols = [f"_{spec['sigma']}__{s}" for s in order] if spec["sigma"] else []
        if not any(c in merged.columns for c in vcols):
            # A sigma with no value to belong to says nothing; do not let the
            # temporary column leak into the catalog.
            merged.drop(columns=[c for c in scols if c in merged.columns], inplace=True)
            continue
        V = _matrix(merged, vcols)
        S = _matrix(merged, scols) if scols else None
        if spec["kind"] == "ratio":
            V[~(V > 0)] = np.nan           # a non-positive size is no measurement
        if S is not None:
            # A sigma of 0 claims infinite precision; it means "not given"
            # (559 JPL H sigmas and 2 diameter sigmas in 2026-09-23).
            S[~(S > 0)] = np.nan
        has = ~np.isnan(V)
        count = has.sum(axis=1)
        stem = spec["stem"]
        prefer = [order.index(s) for s in spec.get("prefer", []) if s in order]
        rank = prefer + [j for j in range(len(order)) if j not in prefer]

        # ── Physical screens (physics.py) ────────────────────────────────────
        refused = np.zeros_like(has)
        own_ok = None
        screen = spec.get("screen")
        if screen and groups is None:
            groups = groups_of(merged)
        if screen == "albedo":
            refused = has & ((V >= ALBEDO_CEILING) | (V < ALBEDO_FLOOR))
        elif screen == "h_diameter":
            h_cat = numeric(merged, "absolute_magnitude_h").to_numpy("float64")
            p = albedo_from_h_and_diameter(h_cat[:, None], V)
            lo_p, hi_p = IMPLIED_ALBEDO_RANGE
            refused = has & ~np.isnan(p) & ((p < lo_p) | (p > hi_p))
        elif screen == "spin":
            _, ceiling = density_limits(groups)
            smallest = smallest_diameter_km(numeric(merged, "diameter_km"),
                                            numeric(merged, "absolute_magnitude_h"))
            refused = has & rotation_is_impossible(V, smallest[:, None], ceiling[:, None])
        elif screen == "density":
            floor, ceiling = density_limits(groups)
            no_sigma = has & (S >= V) if S is not None else np.zeros_like(has)
            d_cat = numeric(merged, "diameter_km").to_numpy("float64")
            d_own = diam[0] if diam is not None else np.full_like(V, np.nan)
            rho_own = bulk_density_gcm3(V, d_own)
            rho_cat = bulk_density_gcm3(V, d_cat[:, None])
            lo, hi = floor[:, None], ceiling[:, None]
            own_ok = (rho_own >= lo) & (rho_own <= hi)
            cat_ok = (rho_cat >= lo) & (rho_cat <= hi)
            testable = ~np.isnan(rho_own) | ~np.isnan(rho_cat)
            impossible = has & ~no_sigma & testable & ~(own_ok | cat_ok)
            refused = no_sigma | impossible

            # EVERY mass refused on density alone: the mass and the diameter
            # cannot both be right, and the one fewer sources report goes.  A
            # tie drops the mass, the less certain measurement for all but the
            # largest bodies (Carry 2012).  What this separates, measured on the
            # 2026-09-23 release: De Sitter and Atala, one MP3C mass against a
            # diameter four sources agree on (the mass goes); and six TNO
            # binaries where SsODNet and MP3C give the SYSTEM mass and MP3C
            # alone gives the PRIMARY's diameter, at implied albedos up to 1.8
            # (the diameter goes, and is derived again downstream).
            stuck = impossible.any(axis=1) & ~(has & ~refused).any(axis=1)
            # Support is the diameters still standing: one the H screen
            # refused does not vote.
            d_support = diam[1].sum(axis=1) if diam is not None else np.zeros(n)
            m_support = (has & ~no_sigma).sum(axis=1)
            drop_d = stuck & (m_support > d_support) & (diam is not None)
            if diam is not None and drop_d.any():
                # Added to what the H screen already refused, not over it.
                prev = merged["diameter_screened_out"].astype("string").fillna("")
                new = _names(diam[1] & drop_d[:, None], diam[2]).fillna("").to_numpy()
                both = (prev + ";" + new).str.strip(";")
                merged["diameter_screened_out"] = both.replace("", pd.NA).to_numpy()
            if drop_d.any():
                merged.loc[drop_d, [c for c in ("diameter_km", "diameter_sigma_km")
                                    if c in merged.columns]] = np.nan
                merged.loc[drop_d, "diameter_provider"] = pd.NA
                refused[drop_d] = no_sigma[drop_d]
                own_ok[drop_d] = False     # nothing left to pair with
                # Counted here, not off `diameter_screened_out`, which also
                # holds what the H screen refused.
                say(f"        diameter: {int(drop_d.sum()):,} dropped beside a "
                    f"better-supported mass (a binary's system mass beside its "
                    f"primary's size); e.g. "
                    f"{merged.loc[drop_d, 'designation'].head(5).tolist()}")
        usable = has & ~refused
        pick = _first(usable, rank)
        at = np.maximum(pick, 0)

        merged[field] = np.where(pick >= 0, V[rows, at], np.nan)
        if S is not None:
            merged[spec["sigma"]] = np.where(pick >= 0, S[rows, at], np.nan)
        merged[f"{stem}_provider"] = pd.Series(names[pick], index=merged.index,
                                               dtype="string")
        merged[f"{stem}_n_sources"] = count.astype("int64")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN rows
            hi_v, lo_v = np.nanmax(V, axis=1), np.nanmin(V, axis=1)
        spread = (hi_v / lo_v - 1.0) if spec["kind"] == "ratio" else (hi_v - lo_v)
        spread = np.where(count > 0, spread, np.nan)
        merged[f"{stem}_spread"] = spread
        agree = pd.array(np.where(count >= 2, spread <= spec["tolerance"], False),
                         dtype="boolean")
        agree[count < 2] = pd.NA
        merged[f"{stem}_sources_agree"] = agree
        if screen:
            merged[f"{stem}_screened_out"] = _names(refused, order).to_numpy()
            _say_screened(merged, stem, V, refused, order)

        if field == "diameter_km":
            dS = S if S is not None else np.full_like(V, np.nan)
            kept = np.where(refused, np.nan, V)     # never pair a refused diameter
            diam = (kept, has & ~refused, order, dS)
        if screen == "density" and diam is not None:
            # PUBLISH A MASS BESIDE THE DIAMETER IT WAS MEASURED WITH.  A
            # source's density is its mass over ITS diameter, and ssoBFT's
            # diameters for massive bodies are the occultation and adaptive-
            # optics ones (Eunomia 271 km, Davida 303, Europa 317), where the
            # backbone's are older radiometric fits 5-15% smaller.  Pairing
            # one catalog's mass with another's diameter is what put Eunomia
            # at 4.9 g/cm3; its own pair says 3.1.
            d_new = diam[0][rows, at]
            swap = ((pick >= 0) & own_ok[rows, at]
                    & (d_new != merged["diameter_km"].to_numpy("float64")))
            if swap.any():
                merged.loc[swap, "diameter_km"] = d_new[swap]
                if "diameter_sigma_km" in merged.columns:
                    merged.loc[swap, "diameter_sigma_km"] = diam[3][rows, at][swap]
                merged.loc[swap, "diameter_provider"] = names[pick][swap]
            say(f"        mass: {int(swap.sum()):,} published beside their own "
                f"source's diameter instead of the backbone's")

        merged.drop(columns=[c for c in vcols + scols if c in merged.columns],
                    inplace=True)
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# DATA MERGER
# ─────────────────────────────────────────────────────────────────────────────
#
# Designed to scale to N sources; merge_sources, dedup and validation pick a
# new one up automatically.  What adding one takes: build.py, ADDING A SOURCE.
#
# The first non-empty source in the dict becomes the BACKBONE; remaining sources
# are merged in with an OUTER join so designations unique to any source are
# retained.  Where a designation appears in multiple sources the backbone's
# value wins and the others fill gaps (never overwrite); for MEASURED_FIELDS the
# same precedence applies and every source's value is compared as well.
def merge_sources(
    sources: Dict[str, pd.DataFrame],
    links: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Merge an arbitrary set of source DataFrames into a single catalog.

    Args:
        sources:  ordered mapping of `source_name -> DataFrame`.  The first
                  non-empty entry is treated as the backbone; the rest are
                  outer-joined supplements that fill gaps.  Each DataFrame is
                  expected to have a 'designation' column.
        links:    optional extra alias -> designation table for supplement
                  designations the backbone's own columns cannot place, from
                  `fetch_mpc_identifications`; see identity.py.

    Returns:
        Merged + deduplicated DataFrame, one row per body, with `n_sources`,
        `sources` and the MEASURED_FIELDS provenance columns; or an empty
        DataFrame if every source was empty.
    """
    say("\n  Merging sources ...")

    available = {k: v for k, v in sources.items() if v is not None and not v.empty}

    if not available:
        warn("     FAIL  No data from any source - aborting merge")
        return pd.DataFrame()

    # Normalise designation for joining.  Use the shared canonical extractor,
    # it's idempotent so re-running on an already-canonical fetcher output is a
    # no-op, and crucially it returns proper pd.NA for missing values (a naïve
    # .astype(str).str.upper() would turn pd.NA into the literal string "<NA>"
    # and create a ghost dedup key).
    for name, df in available.items():
        df = df.copy()
        if "designation" in df.columns:
            df["designation"] = _extract_canonical_designation(df["designation"])
        available[name] = df

    # First non-empty source becomes the backbone, caller controls precedence
    # via the dict insertion order.
    backbone_name = next(iter(available))
    order = list(available)
    merged = _dedup_source(available.pop(backbone_name), backbone_name)
    if "designation" not in merged.columns:
        warn(f"     FAIL  backbone {backbone_name} has no 'designation' column")
        return pd.DataFrame()
    backbone_cols = list(merged.columns)
    merged[f"_present__{backbone_name}"] = True
    say(f"       Backbone: {backbone_name}  ({len(merged):,} rows)")

    alias_map = build_alias_map(merged)

    # Outer-join each remaining source so designations unique to that source
    # are retained.  Backbone values win; supplement values fill NaN gaps.
    for src_name, supp in available.items():
        if "designation" not in supp.columns:
            warn(f"     WARN  {src_name} has no 'designation' column - skipped in merge")
            order.remove(src_name)
            continue

        # Re-key onto the backbone BEFORE deduplicating, so two designations of
        # one body in this source collapse into one row here.
        raw_keys = supp["designation"]
        supp = supp.copy()
        supp["designation"] = resolve_designations(raw_keys, alias_map, links)
        changed = supp["designation"].fillna("") != raw_keys.fillna("")
        rekeyed = pd.Series(supp.loc[changed, "designation"].unique())
        supp = _dedup_source(supp, src_name)
        supp[f"_present__{src_name}"] = True

        # Pass every column through, INCLUDING `source_*` flags.  Every
        # fetcher tags itself with a uniquely-named flag (source_jpl,
        # source_ssodnet, source_neowise, source_mp3c)
        # so there's no collision risk; preserving them gives each row a
        # full provenance footprint after the merge.
        fill_cols = [c for c in supp.columns if c != "designation"]

        # Rename supp columns to avoid clobbering backbone
        supp_renamed = supp[["designation"] + fill_cols].copy()
        supp_renamed.columns = (
            ["designation"] + [f"_{c}__{src_name}" for c in fill_cols]
        )

        before_merge = len(merged)
        # How many of this source's keys the backbone already knows.  Reported
        # because it is the one number that separates "the source is fine and
        # simply overlaps" from "the source's keys join nothing"; a supplement
        # whose overlap is 0 has almost certainly built its designation wrongly,
        # and an outer join hides that by quietly adding every row as new.
        overlap = int(supp["designation"].isin(merged["designation"]).sum())
        n_rekeyed = int(rekeyed.isin(merged["designation"]).sum())
        merged = merged.merge(supp_renamed, on="designation", how="outer")
        new_rows = len(merged) - before_merge

        for col in fill_cols:
            src_col = f"_{col}__{src_name}"
            if src_col not in merged.columns or col in _HELD_BACK:
                continue            # measured fields are resolved after the loop
            if col in merged.columns:
                merged[col] = merged[col].fillna(merged[src_col])
            else:
                merged.rename(columns={src_col: col}, inplace=True)
                continue
            merged.drop(columns=[src_col], inplace=True)

        say(f"     OK   Merged {src_name}: {len(supp):,} supplement records "
            f"({overlap:,} matched the backbone, {n_rekeyed:,} of them re-keyed "
            f"from another designation; +{new_rows:,} new entries)")
        if len(supp) and not overlap:
            warn(f"     ALERT  {src_name} matched ZERO backbone designations. "
                 f"Every one of its {len(supp):,} rows entered as a new body "
                 f"with no orbital elements, and validation will drop them "
                 f"all.  Check how fetch_* builds `designation` - a float-typed "
                 f"identifier stringifies to \"3.0\" and joins nothing.")

    # The backbone's own measured columns join the per-source set under the
    # same naming, so one routine resolves them all.
    for col in list(merged.columns):
        if col in _HELD_BACK:
            merged.rename(columns={col: f"_{col}__{backbone_name}"}, inplace=True)
    merged = _resolve_measured(merged, order)

    present = [f"_present__{s}" for s in order]
    flags = merged[present].eq(True)
    merged["n_sources"] = flags.sum(axis=1).astype("int64")
    merged["sources"] = _names(flags.to_numpy(), order, index=merged.index)
    merged.drop(columns=present, inplace=True)

    merged = merged[_column_order(backbone_cols, list(merged.columns))]

    # Final post-merge dedup, combines any rows that still share a body.
    merged = deduplicate_catalog(merged, key="designation", label="post-merge")

    vc = merged["n_sources"].value_counts().sort_index()
    say("       Bodies by number of sources: " +
        ", ".join(f"{int(k)}: {int(v):,}" for k, v in vc.items()))
    say(f"     OK  Combined catalog: {len(merged):,} rows x {len(merged.columns)} columns")
    return merged


def _column_order(backbone_cols: List[str], cols: List[str]) -> List[str]:
    """Backbone columns where the backbone had them, each measured value
    followed by its sigma and provenance columns, then everything else in
    arrival order.  Keeps `diameter_km` beside `designation` in the CSV rather
    than pushed behind fifty supplement columns."""
    group = {}
    for field, spec in MEASURED_FIELDS.items():
        stem = spec["stem"]
        group[field] = [c for c in
                        [field, spec["sigma"], f"{stem}_provider", f"{stem}_n_sources",
                         f"{stem}_spread", f"{stem}_sources_agree",
                         f"{stem}_screened_out"]
                        if c and c in cols]
    order: List[str] = []
    for c in backbone_cols + cols:
        if c in order or c not in cols:
            continue
        owner = next((f for f, g in group.items() if c in g), None)
        order.extend(x for x in (group[owner] if owner else [c]) if x not in order)
    return order


def _dedup_source(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Per-source dedup, with the loud check for a key that killed every row."""
    n_raw = len(df)
    # NEOWISE rows are FITS, and two designations re-keyed onto one body are
    # two sets of fits of it: average them like repeat fits (214 bodies on
    # 2026-09-22, median diameter spread 14.7%) rather than letting the more
    # complete row win.  Keyed on the column, not the source's display name.
    if "neowise_n_fits" in df.columns and "designation" in df.columns:
        df = combine_neowise_fits(df)
    out = deduplicate_catalog(df, key="designation", label=name)
    # A source that arrives with rows and leaves with none has a broken
    # merge key, not an empty table, and that distinction is invisible in
    # the output: the columns still appear, filled entirely with NaN, and
    # the fetcher has already printed its success line.  NEOWISE did this
    # on every large run up to v1.1.0.  Fail loud.
    if n_raw and out.empty:
        warn(f"     ALERT  {name} fetched {n_raw:,} rows and NONE survived "
             f"keying - its `designation` column is unusable, so the whole "
             f"source is about to contribute nothing.  This is a BUG in the "
             f"{name} fetcher, not an empty upstream table.")
    return out