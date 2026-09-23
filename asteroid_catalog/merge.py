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

from ._log import say, warn

from .designations import _extract_canonical_designation
from .identity import build_alias_map, resolve_designations

# ─────────────────────────────────────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────────────────────────────────────
def _normalise_designation_key(s: pd.Series) -> pd.Series:
    """
    Normalisation used ONLY for duplicate detection.

    Defers to the shared canonical extractor for the actual designation work
    (collapsing "(1) Ceres", "1 Ceres", "00001" all to "1"; preserving
    "2024 BX1" intact so distinct provisional designations stay distinct),
    then uppercases the result so case variation can't fragment groups.

    This is the SAME logic the fetchers run when they produce `designation`,
    so a designation produced by the JPL pdes field and one produced from
    another catalog's variant form are guaranteed to compare equal as dedup keys.
    """
    return _extract_canonical_designation(s).str.upper().str.strip()


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
    work["_dedup_key"] = _normalise_designation_key(work[key])

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
# NEOWISE quotes ~10% on diameter for well-observed bodies; albedo carries
# roughly twice the relative error of diameter; published masses scatter by
# tens of percent; catalogue H values differ systematically by 0.1-0.3 mag; a
# rotation period is precise enough that 2% catches the half/double-period
# ambiguity.  `<stem>_spread` is published so a caller can apply their own.
MEASURED_FIELDS: Dict[str, dict] = {
    "diameter_km":          {"stem": "diameter",        "sigma": "diameter_sigma_km",
                             "kind": "ratio", "tolerance": 0.10},
    "albedo":               {"stem": "albedo",          "sigma": "albedo_sigma",
                             "kind": "ratio", "tolerance": 0.25},
    "absolute_magnitude_h": {"stem": "h",               "sigma": "absolute_magnitude_h_sigma",
                             "kind": "diff",  "tolerance": 0.30},
    "estimated_mass_kg":    {"stem": "mass",            "sigma": "estimated_mass_sigma_kg",
                             "kind": "ratio", "tolerance": 0.25},
    "rotation_period_h":    {"stem": "rotation_period", "sigma": None,
                             "kind": "ratio", "tolerance": 0.02},
}
_HELD_BACK = set(MEASURED_FIELDS) | {m["sigma"] for m in MEASURED_FIELDS.values() if m["sigma"]}


def _resolve_measured(merged: pd.DataFrame, order: List[str]) -> pd.DataFrame:
    """Pick each measured value by precedence, and say how the sources compare.

    `merged` holds, per source S in `order`, the columns `_<field>__<S>` (and
    `_<sigma>__<S>`) left unfilled by the join.  They are consumed here.
    """
    n = len(merged)
    for field, spec in MEASURED_FIELDS.items():
        vcols = [f"_{field}__{s}" for s in order]
        if not any(c in merged.columns for c in vcols):
            # A sigma with no value to belong to says nothing; do not let the
            # temporary column leak into the catalog.
            if spec["sigma"]:
                merged.drop(columns=[f"_{spec['sigma']}__{s}" for s in order
                                     if f"_{spec['sigma']}__{s}" in merged.columns],
                            inplace=True)
            continue
        V = np.column_stack([
            pd.to_numeric(merged[c], errors="coerce").to_numpy(dtype="float64")
            if c in merged.columns else np.full(n, np.nan) for c in vcols])
        if spec["kind"] == "ratio":
            V[~(V > 0)] = np.nan           # a non-positive size is no measurement
        has = ~np.isnan(V)
        count = has.sum(axis=1)
        pick = np.where(count > 0, has.argmax(axis=1), -1)
        rows = np.arange(n)

        merged[field] = np.where(pick >= 0, V[rows, np.maximum(pick, 0)], np.nan)
        if spec["sigma"]:
            S = np.column_stack([
                pd.to_numeric(merged[f"_{spec['sigma']}__{s}"], errors="coerce")
                  .to_numpy(dtype="float64")
                if f"_{spec['sigma']}__{s}" in merged.columns else np.full(n, np.nan)
                for s in order])
            merged[spec["sigma"]] = np.where(pick >= 0, S[rows, np.maximum(pick, 0)], np.nan)

        names = np.array(order + [None], dtype=object)
        stem = spec["stem"]
        merged[f"{stem}_provider"] = pd.Series(names[pick], index=merged.index,
                                               dtype="string")
        merged[f"{stem}_n_sources"] = count.astype("int64")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN rows
            hi, lo = np.nanmax(V, axis=1), np.nanmin(V, axis=1)
        spread = (hi / lo - 1.0) if spec["kind"] == "ratio" else (hi - lo)
        spread = np.where(count > 0, spread, np.nan)
        merged[f"{stem}_spread"] = spread
        agree = pd.array(np.where(count >= 2, spread <= spec["tolerance"], False),
                         dtype="boolean")
        agree[count < 2] = pd.NA
        merged[f"{stem}_sources_agree"] = agree

        drop = [c for c in vcols if c in merged.columns]
        if spec["sigma"]:
            drop += [f"_{spec['sigma']}__{s}" for s in order
                     if f"_{spec['sigma']}__{s}" in merged.columns]
        merged.drop(columns=drop, inplace=True)
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# DATA MERGER
# ─────────────────────────────────────────────────────────────────────────────
#
# Designed to scale to N sources.  Adding a new catalog later is:
#   1. write fetch_<name>(config) returning a DataFrame keyed on 'designation'
#   2. add a matching `use_<name>: bool = True` toggle to CatalogConfig
#   3. inside build_catalog(), populate `sources["<Name>"] = fetch_<name>(...)
#                                          if config.use_<name> else pd.DataFrame()`
# merge_sources / dedup / validation pick the new source up automatically.
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
    label = pd.Series("", index=merged.index, dtype="object")
    for s, col in zip(order, present):
        label = label.where(~flags[col], label + np.where(label == "", "", ";") + s)
    merged["sources"] = label.astype("string")
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
                         f"{stem}_spread", f"{stem}_sources_agree"]
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
        from .neowise import combine_neowise_fits
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
              f"source is about to contribute nothing.  This is a BUG in "
              f"fetch_{name.split()[0].lower()}, not an empty upstream table.")
    return out