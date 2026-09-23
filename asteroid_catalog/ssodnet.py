# -*- coding: utf-8 -*-
"""IMCCE SsODNet ssoBFT: best-of-literature physical properties.

Bulk-downloaded once as a ~500 MB parquet and cached, read with column
projection so the ~915-column table is never materialised.

TEST COLUMN MEMBERSHIP AGAINST `schema_arrow`, NEVER `schema`.  The latter is
the PHYSICAL parquet schema, which names a nested list column by its inner
path, so `spins.period.value` reads as absent and the projection silently
drops it.
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

from .config import CatalogConfig, _PY, _resolve_cache_dir
from .designations import _extract_canonical_designation, _looks_like_designation

# ─────────────────────────────────────────────────────────────────────────────
# SsODNet ssoBFT FETCHER  (IMCCE, Solar-system Best-estimate Table)
# ─────────────────────────────────────────────────────────────────────────────
# SsODNet aggregates ~3,000 published catalogs into a single best-estimate
# table for ~1.2 M asteroids.  We pull the bulk Apache-Parquet file
# (~500 MB) ONCE per `cache_max_age_days` and read only the columns we need
# via pyarrow column projection so the in-memory footprint is small.
#
# Schema notes (parquet column names use dotted paths: 244 cols as of the
# 2026-08 release; verify against the cached file, not this comment):
#   Identity:  id, number, name
#   Physical:  diameter.value, diameter.error.{min,max}        (km)
#              albedo.value                                    (geometric)
#              mass.value                                      (kg)
#              density.value                                   (kg/m³ → we convert to g/cm³)
#              absolute_magnitude.H.value                      (mag)
#   Taxonomy:  taxonomy.class, taxonomy.complex
#   Orbital:   orbital_elements.{semi_major_axis,eccentricity,
#                inclination,periapsis_distance,apoapsis_distance,
#                node_longitude,periapsis_argument,mean_anomaly,
#                orbital_period}.value
#   Rotation:  spins.period.value: a LIST column (one row holds every ranked
#              solution); we take the first non-null element.
#
# ⚠️  THE IDENTITY COLUMNS WERE RENAMED (v1.0.9).  ssoBFT used to ship
# `sso_id` / `sso_number` / `sso_name`; it now ships `id` / `number` / `name`.
# Because the projection silently drops columns it cannot find, the fetcher
# went on returning 50,000 rows with NO merge key, and `merge_sources` then
# discarded the entire source with a one-line warning, for a ~500 MB download
# and every literature diameter, density and taxonomy in the catalog.  Six
# other columns drifted at the same time (perihelion → periapsis_distance,
# aphelion → apoapsis_distance, perihelion_argument → periapsis_argument,
# absolute_magnitude.value → absolute_magnitude.H.value, and the three ranked
# spin columns → one list column).
#
# The lesson: a projection that tolerates missing columns MUST still assert
# the ones it cannot work without.  `_SSODNET_REQUIRED` below does that, and
# the fetcher now fails loudly rather than returning an unmergeable frame.
#
# Documentation: https://ssp.imcce.fr/webservices/ssodnet/api/ssobft/
# Bulk file:     https://ssp.imcce.fr/data/ssoBFT-latest_Asteroid.parquet

_SSODNET_PARQUET_URL = "https://ssp.imcce.fr/data/ssoBFT-latest_Asteroid.parquet"
_SSODNET_CACHE_FILE  = "ssoBFT-latest_Asteroid.parquet"

# Columns we WANT.  Asked of pyarrow as a projection; any not present in the
# file's actual schema are silently dropped (handled below).
_SSODNET_WANTED = [
    "id", "number", "name",
    "diameter.value", "diameter.error.min", "diameter.error.max",
    "albedo.value", "albedo.error.min", "albedo.error.max",
    "mass.value", "mass.error.min", "mass.error.max",
    # NOT absolute_magnitude.H.error: 1.41 M of its 1.56 M values are exactly
    # 0.001, 0.01, 0.1, 1 or 10 (measured 2026-09-22), i.e. the precision H
    # was quoted to, not an uncertainty.  JPL's H_sigma is a fit uncertainty.
    "density.value",
    "taxonomy.class", "taxonomy.complex",
    "orbital_elements.semi_major_axis.value",
    "orbital_elements.eccentricity.value",
    "orbital_elements.inclination.value",
    "orbital_elements.periapsis_distance.value",
    "orbital_elements.apoapsis_distance.value",
    "orbital_elements.node_longitude.value",
    "orbital_elements.periapsis_argument.value",
    "orbital_elements.mean_anomaly.value",
    "orbital_elements.orbital_period.value",
    "absolute_magnitude.H.value",
    # Spin / rotation: ssoBFT now stores every ranked solution for a body in
    # ONE list column rather than `spins.<1..5>.period.value` scalars.  The
    # fetcher takes the first non-null element (rank order is preserved).
    "spins.period.value",
]

# Without these three the frame cannot be merged; `merge_sources` keys on
# `designation`, which is built from `number` falling back to `name`.  Losing
# them silently is the failure documented above, so the fetcher treats their
# absence as fatal for this source rather than returning a useless frame.
_SSODNET_REQUIRED = ["number", "name"]

_SSODNET_RENAME = {
    # Identity:
    #   number  → numeric IAU number (e.g. 1 for Ceres).  Used as our merge
    #             key (designation).  Nullable, unnumbered bodies fall back
    #             to `name`.
    #   name    → human-readable name ("Ceres").
    #   id      → IMCCE's quaero-resolved canonical identifier; for numbered
    #             asteroids this is the name string, for unnumbered it's the
    #             provisional designation.  Kept as `ssodnet_id` so a user can
    #             round-trip back to the SsODNet REST API
    #             (ssp.imcce.fr/.../ssocard/<ssodnet_id>).
    # These were sso_number / sso_name / sso_id before the 2026-08 schema
    # change; see the ⚠️ note above before "fixing" them back.
    "number":                                          "designation",
    "name":                                            "name",
    "id":                                              "ssodnet_id",
    "diameter.value":                                  "diameter_km",
    "albedo.value":                                    "albedo",
    "mass.value":                                      "estimated_mass_kg",
    # density: SsODNet stores SI (kg/m³).  Convert to g/cm³ in the body of the
    # fetcher (rename here just standardises the column name).
    "density.value":                                   "density_gcm3",
    "taxonomy.class":                                  "spectral_type",
    "taxonomy.complex":                                "spectral_complex",
    "orbital_elements.semi_major_axis.value":          "semi_major_axis_au",
    "orbital_elements.eccentricity.value":             "eccentricity",
    "orbital_elements.inclination.value":              "inclination_deg",
    "orbital_elements.periapsis_distance.value":       "perihelion_au",
    "orbital_elements.apoapsis_distance.value":        "aphelion_au",
    "orbital_elements.node_longitude.value":           "longitude_asc_node_deg",
    "orbital_elements.periapsis_argument.value":       "arg_perihelion_deg",
    "orbital_elements.mean_anomaly.value":             "mean_anomaly_deg",
    # IN DAYS, like JPL's `per`, and labelled years until 1.3.0.  Converted in
    # the body of the fetcher.
    "orbital_elements.orbital_period.value":           "orbital_period_yr",
    "absolute_magnitude.H.value":                      "absolute_magnitude_h",
    # spins.period.value handled separately below; the list is reduced to a
    # single `rotation_period_h` column.
}

_SSODNET_NUMERIC = [
    "diameter_km", "diameter_sigma_km", "albedo", "albedo_sigma",
    "estimated_mass_kg", "estimated_mass_sigma_kg", "density_gcm3",
    "semi_major_axis_au", "eccentricity", "inclination_deg",
    "perihelion_au", "aphelion_au", "longitude_asc_node_deg",
    "arg_perihelion_deg", "mean_anomaly_deg", "orbital_period_yr",
    "absolute_magnitude_h", "rotation_period_h",
]


def _ssodnet_cache_path(config: CatalogConfig) -> str:
    """Where the ~500 MB ssoBFT parquet is cached.

    Through `_resolve_cache_dir`, which defaults to the system temp directory
    rather than beside the CSVs, so a working copy on Google Drive does not
    round-trip half a gigabyte through Drive sync on every run.
    """
    return os.path.join(_resolve_cache_dir(config), _SSODNET_CACHE_FILE)


def _ssodnet_cache_is_fresh(path: str, max_age_days: float) -> bool:
    """Return True if a cached parquet exists and is < max_age_days old."""
    if not os.path.exists(path):
        return False
    age_days = (datetime.now().timestamp() - os.path.getmtime(path)) / 86400.0
    return age_days <= max_age_days


def _download_ssodnet_parquet(dest: str, config: CatalogConfig) -> bool:
    """Stream-download the ssoBFT parquet to `dest` with a tqdm progress bar."""
    try:
        with requests.get(
            _SSODNET_PARQUET_URL,
            timeout=config.request_timeout,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length") or 0) or None
            tmp = dest + ".part"
            with open(tmp, "wb") as fh, tqdm(
                total=total,
                desc="     SsODNet ssoBFT",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                leave=True,
                mininterval=0.5,
            ) as pbar:
                for chunk in resp.iter_content(chunk_size=1 << 20):  # 1 MB chunks
                    if chunk:
                        fh.write(chunk)
                        pbar.update(len(chunk))
            # Windows can briefly hold the freshly-closed file open via the
            # indexer or AV, retry the atomic rename a few times before giving up.
            import time
            for _ in range(8):
                try:
                    os.replace(tmp, dest)
                    break
                except PermissionError:
                    time.sleep(0.5)
            else:
                os.replace(tmp, dest)  # final attempt → raises if still locked
        return True
    except requests.exceptions.Timeout:
        say("     FAIL  SsODNet download timed out")
    except requests.exceptions.ConnectionError as exc:
        say(f"     FAIL  SsODNet unreachable ({str(exc)[:80]})")
    except requests.exceptions.HTTPError as exc:
        say(f"     FAIL  SsODNet HTTP {exc.response.status_code}")
    except Exception as exc:
        say(f"     FAIL  SsODNet download error: {type(exc).__name__}: {exc}")
    # Clean partial file on failure so a retry doesn't trip the freshness check
    try:
        os.remove(dest + ".part")
    except OSError:
        pass
    return False


def fetch_ssodnet(config: CatalogConfig) -> pd.DataFrame:
    """
    Fetch the SsODNet ssoBFT best-estimate table.

    The bulk parquet (~500 MB) is cached at
        {cache_dir}/ssoBFT-latest_Asteroid.parquet
    (system tmp by default; see _resolve_cache_dir) and refreshed only when
    older than config.cache_max_age_days.

    Returns EMPTY DataFrame on any unrecoverable error so the rest of the
    pipeline survives unaffected.
    """
    say("\n   SsODNet ssoBFT  (ssp.imcce.fr) ...")

    # pyarrow is required for column-projection parquet reads.  If somehow it
    # didn't install, fall back to pandas' built-in parquet engine, which is
    # usually pyarrow anyway but may be fastparquet on bare systems.
    try:
        import pyarrow.parquet as pq          # noqa: F401  (engine probe)
        engine = "pyarrow"
    except ImportError:
        say("     WARN  pyarrow not available - falling back to pandas default engine")
        engine = "auto"

    cache_path = _ssodnet_cache_path(config)
    if _ssodnet_cache_is_fresh(cache_path, config.cache_max_age_days):
        age_h = (datetime.now().timestamp() - os.path.getmtime(cache_path)) / 3600
        say(f"       Using cached parquet ({age_h:.1f} h old): {cache_path}")
    else:
        say(f"     v   Downloading bulk parquet from {_SSODNET_PARQUET_URL}")
        if not _download_ssodnet_parquet(cache_path, config):
            return pd.DataFrame()

    # Read only the columns that actually exist in the schema (the schema does
    # drift between SsODNet releases).
    try:
        if engine == "pyarrow":
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(cache_path)
            # schema_arrow, NOT schema.  The parquet PHYSICAL schema flattens a
            # list column into its inner path, so `spins.period.value` is absent
            # from pf.schema.names while present in pf.schema_arrow.names, and
            # read(columns=…) expects the arrow-level name.  Testing membership
            # against the physical schema silently drops every nested column.
            schema_names = set(pf.schema_arrow.names)
            cols = [c for c in _SSODNET_WANTED if c in schema_names]
            missing = [c for c in _SSODNET_WANTED if c not in schema_names]
            if missing:
                # SsODNet renames flattened columns between releases, so a few
                # misses are normal and tolerable.  Say which, at every scale, 
                # the old code only spoke up when fewer than 5 columns matched,
                # which is exactly why a release that renamed the IDENTITY
                # columns (and 6 others) passed for healthy: 14 still matched.
                say(f"     NOTE   Schema drift: {len(cols)}/{len(_SSODNET_WANTED)} "
                      f"columns matched, missing {missing}")
            absent_required = [c for c in _SSODNET_REQUIRED if c not in schema_names]
            if absent_required:
                warn(f"     FAIL  ssoBFT schema is missing the merge key(s) "
                      f"{absent_required} - cannot build `designation`, so every "
                      f"row would be dropped at merge time.  Skipping SsODNet.")
                say(f"         Inspect the real schema and update "
                      f"_SSODNET_WANTED / _SSODNET_RENAME:")
                say(f"         {_PY} -c \"import pyarrow.parquet as pq; "
                      f"print(pq.ParquetFile(r'{cache_path}').schema_arrow.names)\"")
                return pd.DataFrame()
            df = pf.read(columns=cols).to_pandas()
        else:
            df = pd.read_parquet(cache_path)
            absent_required = [c for c in _SSODNET_REQUIRED if c not in df.columns]
            if absent_required:
                warn(f"     FAIL  ssoBFT schema is missing the merge key(s) "
                      f"{absent_required} - skipping SsODNet.")
                return pd.DataFrame()
            df = df[[c for c in _SSODNET_WANTED if c in df.columns]]
    except Exception as exc:
        say(f"     FAIL  Parquet read failed: {type(exc).__name__}: {exc}")
        return pd.DataFrame()

    if df.empty:
        say("     WARN  Parquet returned 0 rows")
        return pd.DataFrame()

    # Cap to config.jpl_limit so SsODNet doesn't dominate runtime on small runs.
    # NB: full table is ~1.2 M rows; trimming here keeps merge / dedup fast.
    # IMPORTANT: sort by `number` ASC first so a small-N run gets the LOWEST
    # IAU numbers (Ceres=1, Pallas=2, Juno=3, Vesta=4, …), the most famous
    # bodies, rather than whatever arbitrary order the parquet stores rows in.
    # Unnumbered bodies (number = NaN) are sorted to the end via na_position.
    #
    # This silently stopped working when the column was renamed from
    # `sso_number`: the guard skipped the sort, and the run took an arbitrary
    # 50,000 rows starting around asteroid 367488 instead of Ceres.  The sort
    # key is required now, so the guard cannot silently no-op again.
    if config.ssodnet_limit and len(df) > config.ssodnet_limit:
        df = df.sort_values("number", ascending=True, na_position="last")
        df = df.head(config.ssodnet_limit).copy()
        say(f"        Truncated to first {config.ssodnet_limit:,} rows by number ASC")

    # Reduce the ranked spin solutions to a single rotation_period_h column.
    # ssoBFT used to expose them as `spins.<1..3>.period.value` scalars and now
    # ships ONE list column holding every solution for the body, best rank
    # first.  Take the first non-null element; same "best rank wins, lower
    # ranks fill the gap" behaviour as before, expressed over a list.
    if "spins.period.value" in df.columns:
        def _first_period(v) -> float:
            """Best-ranked rotation period from one body's spin-solution list.

            ssoBFT ships the solutions best-rank-first, so the first non-null
            positive element is the answer, which reproduces the old
            "best rank wins, lower ranks fill the gap" behaviour over a list.
            The `TypeError` arm catches a scalar arriving through a future
            schema change rather than assuming the column stays a list.
            """
            # pyarrow hands back None for absent lists and np.ndarray otherwise.
            if v is None:
                return np.nan
            try:
                for x in v:
                    if x is not None and not pd.isna(x) and float(x) > 0:
                        return float(x)
            except TypeError:          # scalar sneaking through a schema change
                return float(v) if pd.notna(v) else np.nan
            return np.nan

        df["rotation_period_h"] = df["spins.period.value"].apply(_first_period)
        df = df.drop(columns=["spins.period.value"])

    # Derive a scalar sigma from each asymmetric (min, max) error pair before
    # we drop the dotted columns.  Average is a reasonable scalar uncertainty.
    # Every value that has a sigma carries it, because the merge keeps a value
    # and its sigma together: a diameter from one catalog must not end up
    # beside another catalog's error bar.
    for stem, sigma_col in (("diameter", "diameter_sigma_km"),
                            ("albedo", "albedo_sigma"),
                            ("mass", "estimated_mass_sigma_kg")):
        lo, hi = f"{stem}.error.min", f"{stem}.error.max"
        if {lo, hi}.issubset(df.columns):
            df[sigma_col] = (df[lo].astype("float64").abs()
                             + df[hi].astype("float64").abs()) / 2.0
            df = df.drop(columns=[lo, hi])

    df = df.rename(columns={k: v for k, v in _SSODNET_RENAME.items() if k in df.columns})

    # Designation: prefer `number` (numbered → "1"), fall back to `name`
    # (provisional designations / unnumbered).
    # IMPORTANT: `number` is int64 in the parquet but pandas casts to float64
    # whenever NaN is present (unnumbered bodies), which would stringify "1" as
    # "1.0".  Cast to the nullable Int64 dtype first so the str() round-trip
    # gives us the bare integer form JPL uses.
    if "designation" in df.columns:
        try:
            df["designation"] = df["designation"].astype("Int64").astype("string")
        except (TypeError, ValueError):
            df["designation"] = df["designation"].astype("string")
        # Fill unnumbered rows from sso_name
        if "name" in df.columns:
            df["designation"] = df["designation"].where(
                df["designation"].notna() & (df["designation"].astype("string") != "<NA>"),
                df["name"].astype("string"),
            )
    elif "name" in df.columns:
        df["designation"] = df["name"]

    if "designation" in df.columns:
        df["designation"] = _extract_canonical_designation(df["designation"])

    # SsODNet density is in kg/m³, convert to g/cm³ to match the pipeline schema.
    if "density_gcm3" in df.columns:
        df["density_gcm3"] = pd.to_numeric(df["density_gcm3"], errors="coerce") / 1000.0

    # Coerce all numerics
    for col in _SSODNET_NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ssoBFT's orbital period is in days, the same as JPL's.
    if "orbital_period_yr" in df.columns:
        df["orbital_period_yr"] = df["orbital_period_yr"] / 365.25

    # `name` must stay an IAU NAME.  ssoBFT fills it with the provisional
    # designation for every unnamed body, and because the merge fills gaps,
    # that went straight into JPL's empty `name` cells: 1,537,189 unnamed
    # bodies read as named in the 2026-08-11 build, against 26,520 real names.
    # The designation is not lost; it is the row's key, and `ssodnet_id`.
    if "name" in df.columns:
        df["name"] = df["name"].astype("string").mask(_looks_like_designation(df["name"]))

    # If aphelion / perihelion are missing but a & e are present, derive them, 
    # cheap and helps with validator coverage.
    if {"semi_major_axis_au", "eccentricity"}.issubset(df.columns):
        if "perihelion_au" not in df.columns or df["perihelion_au"].isna().all():
            df["perihelion_au"] = df["semi_major_axis_au"] * (1 - df["eccentricity"])
        if "aphelion_au" not in df.columns or df["aphelion_au"].isna().all():
            df["aphelion_au"] = df["semi_major_axis_au"] * (1 + df["eccentricity"])

    df["source_ssodnet"] = True
    say(f"     OK  {len(df):,} records ingested from SsODNet ssoBFT "
          f"({len(df.columns)} columns)")
    return df
