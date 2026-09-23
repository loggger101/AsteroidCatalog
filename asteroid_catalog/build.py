# -*- coding: utf-8 -*-
"""Fetch -> merge -> derive -> validate -> enrich -> export.

`build_catalog` is the whole pipeline.  `build_catalog_table` is the same
function under a second name, and the second name is not cosmetic -- see its
docstring.
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

from .config import CONFIG, CatalogConfig
from .derive import derive_missing_diameters
from .enrich import enrich_composition
from .identity import fetch_mpc_identifications
from .jpl import fetch_jpl_sbdb
from .merge import deduplicate_catalog, merge_sources
from .mp3c import fetch_mp3c
from .neowise import fetch_neowise
from .ssodnet import fetch_ssodnet
from .validate import validate_and_filter

# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────
def build_catalog(config: CatalogConfig = CONFIG) -> pd.DataFrame:
    """
    Master entry-point.  Runs the full catalog pipeline:
      1. Fetch from each source
      2. Merge sources
      3. Validate & filter (failsafes)
      4. Enrich with composition data
      5. Sort, tag, and export

    Returns the validated, enriched catalog as a DataFrame.
    Saves CSV + rejection log to config.output_dir.
    """
    t0 = datetime.now()

    say("=" * 65)
    say("    ASTEROID CATALOG PIPELINE  -  MODULE 1: CATALOGING")
    say(f"      {t0.strftime('%Y-%m-%d %H:%M:%S')}  |  v{config.pipeline_version}")
    say("=" * 65)

    # ── Step 1, Fetch ────────────────────────────────────────────────────────
    # Each entry: "Display name" -> DataFrame (empty if toggled off / failed).
    # To add a new catalog, write a `fetch_<name>(config)` returning a DataFrame
    # keyed on 'designation' and append one line here.  See the ADDITIONAL
    # FETCHERS template section above for the full contract.
    sources: Dict[str, pd.DataFrame] = {
        # JPL is the backbone (first entry → wins on conflicts).  Order of the
        # remaining sources determines which one fills NaN gaps first; SsODNet
        # is placed early because its values are already best-of-literature
        # cross-matches and tend to be more reliable than any single survey.
        "JPL SBDB": fetch_jpl_sbdb(config) if config.use_jpl      else pd.DataFrame(),
        "SsODNet":  fetch_ssodnet(config)  if config.use_ssodnet  else pd.DataFrame(),
        "NEOWISE":  fetch_neowise(config)  if config.use_neowise  else pd.DataFrame(),
        "MP3C":     fetch_mp3c(config)     if config.use_mp3c     else pd.DataFrame(),
        # "<Source>":  fetch_<name>(config) if config.use_<name> else pd.DataFrame(),
    }

    source_counts = {name: len(df) for name, df in sources.items()}
    say(f"\n     Source summary: {source_counts}")

    # ── Step 2, Merge ────────────────────────────────────────────────────────
    # The MPC's designation links, for supplement rows keyed on a designation
    # JPL's own columns do not carry; see `use_mpc_identifications`.
    n_nonempty = sum(1 for df in sources.values() if not df.empty)
    links = (fetch_mpc_identifications(config)
             if config.use_mpc_identifications and n_nonempty > 1 else None)
    merged = merge_sources(sources, links=links)
    if merged.empty:
        warn("\nFAIL  Pipeline aborted - merge produced no data")
        return pd.DataFrame()

    # ── Step 2b; Derive diameters from H ────────────────────────────────────
    # Must run BEFORE validation: validation is what drops rows with no
    # diameter, and this is what gives them one.
    merged = derive_missing_diameters(merged, config)

    # ── Step 3: Validate & filter ────────────────────────────────────────────
    catalog, rejections = validate_and_filter(merged, config)
    if catalog.empty:
        warn("\nFAIL  Pipeline aborted - no entries passed validation")
        return pd.DataFrame()

    # ── Step 4, Composition enrichment ──────────────────────────────────────
    catalog = enrich_composition(catalog)

    # ── Step 4b, Final dedup safety net ─────────────────────────────────────
    # Belt-and-braces: enrichment shouldn't introduce duplicates, but checking
    # here means a CSV written to disk is guaranteed to have unique designations.
    say("\n  Final duplicate sweep ...")
    catalog = deduplicate_catalog(catalog, key="designation", label="final")

    # ── Step 5, Metadata + sort ──────────────────────────────────────────────
    catalog["catalog_date"]      = t0.strftime("%Y-%m-%d")
    catalog["pipeline_version"]  = config.pipeline_version

    if "semi_major_axis_au" in catalog.columns:
        catalog = catalog.sort_values("semi_major_axis_au").reset_index(drop=True)

    # ── Step 6, Save ─────────────────────────────────────────────────────────
    catalog_path  = os.path.join(config.output_dir, config.catalog_filename)
    rejected_path = os.path.join(config.output_dir, config.rejected_filename)

    # lineterminator is pinned because pandas defaults it to os.linesep,
    # which makes a catalog written on Linux differ from the same catalog
    # written on Windows in every line, for no model reason.  CRLF is the
    # existing Windows output, so pinning it changes nothing here.
    catalog.to_csv(catalog_path, index=False, lineterminator="\r\n")
    say(f"\n       Catalog saved  -> {catalog_path}")

    if not rejections.empty:
        # lineterminator is pinned because pandas defaults it to os.linesep,
        # which makes a catalog written on Linux differ from the same catalog
        # written on Windows in every line, for no model reason.  CRLF is the
        # existing Windows output, so pinning it changes nothing here.
        rejections.to_csv(rejected_path, index=False, lineterminator="\r\n")
        say(f"       Rejections log -> {rejected_path}")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = (datetime.now() - t0).total_seconds()
    say("\n" + "=" * 65)
    say("  OK  CATALOGING COMPLETE")
    say(f"      Entries    : {len(catalog):,}")
    say(f"      Columns    : {len(catalog.columns)}")
    say(f"      Elapsed    : {elapsed:.1f}s")

    # Diameter provenance, alongside the taxonomy provenance the run already
    # prints.  This is the number to read before comparing against a committed
    # result: two runs with the same row count but a different measured /
    # derived split are not the same population.
    if "diameter_source" in catalog.columns:
        vc = catalog["diameter_source"].value_counts()
        n_meas = int(vc.get("measured", 0))
        n_der  = int(len(catalog) - n_meas)
        say(f"      Diameter   : {n_meas:,} measured  |  {n_der:,} derived from H")
        for src, n in vc.items():
            if src == "measured":
                continue
            say(f"                   * {str(src):30s} {int(n):,}")
        if n_der:
            say("      WARN   Derived rows carry an ASSUMED albedo; mass scales as "
                  "p_V**-1.5.\n"
                  "          Filter on `derived_diameter_is_estimate` to get the "
                  "measured-only\n"
                  "          population back out of this catalog.")
    say("=" * 65)

    return catalog
