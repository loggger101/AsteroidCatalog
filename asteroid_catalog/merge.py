# -*- coding: utf-8 -*-
"""Combining the sources, and saying honestly what each contributed.

A SOURCE THAT FETCHED ROWS AND MATCHED NONE IS ALWAYS A BUG IN THAT FETCHER,
never an empty upstream table, and `merge_sources` shouts when it happens.
That is not decoration: a float-typed merge key cost NEOWISE four releases of
contributing exactly zero rows while the fetch summary reported 183,408.
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

from .designations import _extract_canonical_designation

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
    Remove duplicate rows by normalised `key`, keeping the row with the most
    populated columns within each group (i.e. the most-complete record wins,
    not arbitrarily the first one).  Reports counts so the caller can see what
    was collapsed.  Idempotent, safe to call multiple times in the pipeline.

    Used in three places:
      1. inside merge_sources, per source, BEFORE the join, defends against
         source-internal duplicates (e.g. a future catalog returning the same
         asteroid under both numeric and named designations)
      2. inside merge_sources, AFTER the join, catches duplicates introduced
         by designation variants between sources
      3. inside build_catalog, AFTER enrichment, final safety net before save
    """
    if df.empty or key not in df.columns:
        return df

    n_before = len(df)

    work = df.copy()
    work["_dedup_key"]    = _normalise_designation_key(work[key])
    work["_completeness"] = work.notna().sum(axis=1)

    # Drop rows whose normalised key is null; they can't be safely grouped.
    null_key = work["_dedup_key"].isna()
    n_null   = int(null_key.sum())
    work     = work[~null_key]

    # Sort by completeness so drop_duplicates(keep='first') keeps the best row.
    work = work.sort_values("_completeness", ascending=False, kind="stable")
    work = work.drop_duplicates(subset=["_dedup_key"], keep="first")
    work = work.drop(columns=["_dedup_key", "_completeness"]).reset_index(drop=True)

    n_removed = n_before - len(work) - n_null

    if n_removed > 0 or n_null > 0:
        msg = []
        if n_removed > 0:
            msg.append(f"{n_removed:,} duplicate(s) collapsed (kept most-complete row)")
        if n_null > 0:
            msg.append(f"{n_null:,} row(s) dropped for null designation")
        say(f"        {label}: " + "; ".join(msg))
    else:
        say(f"     OK   {label}: no duplicates detected")

    return work


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
# value wins and the others fill gaps (never overwrite).
def merge_sources(sources: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Merge an arbitrary set of source DataFrames into a single catalog.

    Args:
        sources: ordered mapping of `source_name -> DataFrame`.  The first
                 non-empty entry is treated as the backbone; the rest are
                 outer-joined supplements that fill gaps.  Each DataFrame is
                 expected to have a 'designation' column.

    Returns:
        Merged + deduplicated DataFrame, or an empty DataFrame if every
        source was empty.
    """
    say("\n  Merging sources ...")

    available = {k: v for k, v in sources.items() if v is not None and not v.empty}

    if not available:
        warn("     FAIL  No data from any source - aborting merge")
        return pd.DataFrame()

    # Normalise designation for joining, then dedupe each source on its own
    # (defends against duplicates introduced upstream in any fetcher).
    # Use the shared canonical extractor, it's idempotent so re-running on
    # an already-canonical fetcher output is a no-op, and crucially it returns
    # proper pd.NA for missing values (a naïve .astype(str).str.upper() would
    # turn pd.NA into the literal string "<NA>" and create a ghost dedup key).
    for name, df in available.items():
        n_raw = len(df)
        if "designation" in df.columns:
            df["designation"] = _extract_canonical_designation(df["designation"])
        available[name] = deduplicate_catalog(df, key="designation", label=name)
        # A source that arrives with rows and leaves with none has a broken
        # merge key, not an empty table, and that distinction is invisible in
        # the output: the columns still appear, filled entirely with NaN, and
        # the fetcher has already printed its success line.  NEOWISE did this
        # on every large run up to v1.1.0.  Fail loud.
        if n_raw and available[name].empty:
            warn(f"     ALERT  {name} fetched {n_raw:,} rows and NONE survived "
                  f"keying - its `designation` column is unusable, so the whole "
                  f"source is about to contribute nothing.  This is a BUG in "
                  f"fetch_{name.split()[0].lower()}, not an empty upstream table.")

    # First non-empty source becomes the backbone, caller controls precedence
    # via the dict insertion order.
    backbone_name, backbone_df = next(iter(available.items()))
    merged = backbone_df.copy()
    available.pop(backbone_name)
    say(f"       Backbone: {backbone_name}  ({len(merged):,} rows)")

    # Outer-join each remaining source so designations unique to that source
    # are retained.  Backbone values win; supplement values fill NaN gaps.
    for src_name, supp in available.items():
        if "designation" not in supp.columns:
            warn(f"     WARN  {src_name} has no 'designation' column - skipped in merge")
            continue

        # Pass every column through, INCLUDING `source_*` flags.  Every
        # fetcher tags itself with a uniquely-named flag (source_jpl,
        # source_ssodnet, source_neowise, source_mp3c)
        # so there's no collision risk; preserving them gives each row a
        # full provenance footprint after the merge.
        fill_cols = [c for c in supp.columns if c != "designation"]

        # Rename supp columns to avoid clobbering backbone
        supp_renamed = supp[["designation"] + fill_cols].copy()
        supp_renamed.columns = (
            ["designation"] + [f"_{c}__{src_name.lower()}" for c in fill_cols]
        )

        before_merge = len(merged)
        # How many of this source's keys the backbone already knows.  Reported
        # because it is the one number that separates "the source is fine and
        # simply overlaps" from "the source's keys join nothing"; a supplement
        # whose overlap is 0 has almost certainly built its designation wrongly,
        # and an outer join hides that by quietly adding every row as new.
        overlap = int(supp["designation"].isin(merged["designation"]).sum())
        merged = merged.merge(supp_renamed, on="designation", how="outer")
        new_rows = len(merged) - before_merge

        for col in fill_cols:
            src_col = f"_{col}__{src_name.lower()}"
            if src_col not in merged.columns:
                continue
            if col in merged.columns:
                merged[col] = merged[col].fillna(merged[src_col])
            else:
                merged.rename(columns={src_col: col}, inplace=True)
                continue
            merged.drop(columns=[src_col], inplace=True)

        say(f"     OK   Merged {src_name}: {len(supp):,} supplement records "
              f"({overlap:,} matched the backbone, +{new_rows:,} new entries)")
        if len(supp) and not overlap:
            warn(f"     ALERT  {src_name} matched ZERO backbone designations. "
                  f"Every one of its {len(supp):,} rows entered as a new body "
                  f"with no orbital elements, and validation will drop them "
                  f"all.  Check how fetch_* builds `designation` - a float-typed "
                  f"identifier stringifies to \"3.0\" and joins nothing.")

    # Final post-merge dedup, keeps the most-complete row in each group.
    merged = deduplicate_catalog(merged, key="designation", label="post-merge")

    say(f"     OK  Combined catalog: {len(merged):,} rows x {len(merged.columns)} columns")
    return merged
