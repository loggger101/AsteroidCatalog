# -*- coding: utf-8 -*-
"""Package a built catalog as a published data release.

    asteroid-catalog package ./data --out ./dist --tag data-2026-09-23

A build is not reproducible (JPL adds bodies daily), so the catalog is
published as a GitHub Release, one immutable snapshot per tag, and consumers
pin a tag instead of re-running the build.  This module turns a build directory
into the assets for one release:

    asteroid_catalog.csv.gz     the catalog, byte-for-byte the CSV the build
                                wrote, gzipped
    asteroid_catalog.parquet    the same rows, typed, for readers who want them
    rejected_entries.csv        the rejection log, as written
    taxonomy.json               TAXONOMY_COMPOSITION and PGM_ENRICHMENT_BY_TYPE
                                as this build used them, so a consumer can
                                re-derive the comp_* columns without
                                installing the package
    manifest.json               what the release is: tag, build date, data
                                contract, row counts per source, and a sha256
                                for every file, including the CSV inside the gz
    RELEASE_NOTES.md            the release page body, generated from the
                                manifest

THE GATES ARE THE POINT OF THIS MODULE.  A build tolerates a failed source and
still succeeds, and that is how MP3C contributed zero rows for several releases
while every run looked fine.  A local build that loses a source is somebody's
bad afternoon; a PUBLISHED one is the input every consumer pins.  So nothing is
written until every gate below passes, and every failed gate is reported, not
just the first.

THE GZIP IS DETERMINISTIC.  The header's mtime and filename are zeroed, so the
same CSV always compresses to the same bytes and the same sha256.
"""

import gzip
import hashlib
import json
import os
import shutil
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from . import __version__
from ._frame import numeric
from .config import CONFIG
from .physics import (
    ALBEDO_CEILING, ALBEDO_FLOOR, DENSITY_LIMITS_ANY_GCM3, DENSITY_LIMITS_GCM3,
    IMPLIED_ALBEDO_RANGE, albedo_from_h_and_diameter, bulk_density_gcm3,
    rotation_is_impossible, smallest_diameter_km,
)
from .query import read_catalog  # noqa: F401  (re-exported: tools and tests read it here)
from .taxonomy import DENSITY_EVIDENCE, PGM_ENRICHMENT_BY_TYPE, TAXONOMY_COMPOSITION

MANIFEST_VERSION = 1

CATALOG_CSV = "asteroid_catalog.csv"
CATALOG_GZ = "asteroid_catalog.csv.gz"
CATALOG_PARQUET = "asteroid_catalog.parquet"
REJECTED_CSV = "rejected_entries.csv"
TAXONOMY_JSON = "taxonomy.json"
MANIFEST = "manifest.json"
NOTES = "RELEASE_NOTES.md"

# The names the merge writes into each row's `sources` column.
SOURCE_NAMES = ["JPL SBDB", "SsODNet", "NEOWISE", "MP3C"]

# Absolute floors, at roughly 90-95% of the full 2026-09-22 build (1,566,616
# bodies; SsODNet ~1.56 M, NEOWISE 143,015, MP3C 1,335,502; 149,740 measured
# diameters).  They are loose on purpose: they exist to catch a source that
# contributed nothing or a fraction of itself, not to police normal growth.
FLOORS: Dict[str, int] = {
    "rows": 1_500_000,
    "measured_diameters": 135_000,
    "JPL SBDB": 1_500_000,
    "SsODNet": 1_400_000,
    "NEOWISE": 130_000,
    "MP3C": 1_200_000,
}

# Relative to the previous release.  The catalog only grows between builds, so
# a real shrink is a defect somewhere, not a new normal.  `allow_shrink`
# overrides these (and only these) for the day a shrink is expected.
MAX_ROW_DROP = 0.005        # total rows
MAX_SOURCE_DROP = 0.02      # rows each source knows


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_entry(path: str) -> dict:
    return {"bytes": os.path.getsize(path), "sha256": _sha256(path)}


def gzip_deterministic(src: str, dst: str) -> None:
    """Gzip `src` to `dst` so that the same input always gives the same bytes."""
    with open(src, "rb") as fin, open(dst, "wb") as raw:
        # filename="" and mtime=0 keep the path and the clock out of the header.
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                           compresslevel=9, mtime=0) as fout:
            shutil.copyfileobj(fin, fout, 1 << 20)


def _typed_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """Give every object column one Arrow type.

    read_csv leaves a column of True/False/blank as object holding bools and
    NaN, and a text column as object holding str and NaN.  Arrow wants one type
    per column, so each becomes nullable boolean or nullable string.
    """
    out = df.copy()
    for col in out.columns:
        if out[col].dtype != object:
            continue
        vals = out[col].dropna()
        if len(vals) and vals.map(lambda v: isinstance(v, bool)).all():
            out[col] = out[col].astype("boolean")
        else:
            out[col] = out[col].astype("string")
    return out


def measured_diameters(df: pd.DataFrame) -> int:
    """How many rows carry a measured, not derived, diameter."""
    if "diameter_source" not in df.columns:
        return 0
    return int((df["diameter_source"] == "measured").sum())


def source_counts(df: pd.DataFrame) -> Dict[str, int]:
    """How many bodies each source knows, from the per-row `sources` column."""
    if "sources" not in df.columns:
        return {name: 0 for name in SOURCE_NAMES}
    exploded = df["sources"].dropna().astype(str).str.split(";").explode()
    vc = exploded.value_counts()
    return {name: int(vc.get(name, 0)) for name in SOURCE_NAMES}


def physical_problems(df: pd.DataFrame) -> List[str]:
    """Every physically impossible value in a catalog, counted, with examples.

    The pipeline screens these out (physics.py); this is the gate that proves
    it did, on the rows about to be published.  The limits are the loosest
    ones, any class's, so a failure here is an impossible value and never a
    judgement call.  A catalog without the columns is not judged on them.
    """
    def num(col):
        return numeric(df, col)

    def report(mask, what):
        mask = pd.Series(mask, index=df.index).fillna(False).astype(bool)
        if mask.any():
            ex = (df.loc[mask, "designation"].astype(str).head(5).tolist()
                  if "designation" in df.columns else [])
            problems.append("%s: %d rows, e.g. %s" % (what, int(mask.sum()), ex))

    problems: List[str] = []
    mass, diam, rho = num("estimated_mass_kg"), num("diameter_km"), num("density_gcm3")
    lo, hi = DENSITY_LIMITS_ANY_GCM3
    implied = pd.Series(bulk_density_gcm3(mass, diam), index=df.index)
    if "estimated_mass_kg" in df.columns and "diameter_km" in df.columns:
        report((implied < lo) | (implied > hi),
               "mass and diameter imply a bulk density outside %g-%g g/cm3" % (lo, hi))
    if "density_gcm3" in df.columns:
        report((rho < lo) | (rho > hi), "density_gcm3 outside %g-%g g/cm3" % (lo, hi))
        if "estimated_mass_kg" in df.columns:
            report((implied / rho - 1).abs() > 1e-6,
                   "estimated_mass_kg is not density_gcm3 x volume")
    if "albedo" in df.columns:
        report(num("albedo") >= ALBEDO_CEILING, "albedo of %g or more" % ALBEDO_CEILING)
        report(num("albedo") < ALBEDO_FLOOR, "albedo below %g" % ALBEDO_FLOOR)
    if "absolute_magnitude_h" in df.columns and "diameter_km" in df.columns:
        measured = (df["diameter_source"].eq("measured") if "diameter_source" in df.columns
                    else pd.Series(True, index=df.index))
        p = pd.Series(albedo_from_h_and_diameter(num("absolute_magnitude_h"), diam),
                      index=df.index)
        lo_p, hi_p = IMPLIED_ALBEDO_RANGE
        report(measured & ((p < lo_p) | (p > hi_p)),
               "a measured diameter that H puts at an albedo outside %g-%g"
               % (round(lo_p, 4), round(hi_p, 2)))
    if "rotation_period_h" in df.columns:
        # Judged on what is KNOWN of the size, as the merge judges it: a
        # measured diameter, else the size at albedo 1.  A derived diameter
        # is an assumption and cannot make a measured period impossible.
        known = (df["diameter_source"].eq("measured").to_numpy()
                 if "diameter_source" in df.columns else np.ones(len(df), bool))
        smallest = smallest_diameter_km(diam.where(known), num("absolute_magnitude_h"))
        report(rotation_is_impossible(num("rotation_period_h"), smallest, hi),
               "a body 10 km or more across spinning faster than its breakup "
               "period at %g g/cm3" % hi)
    return problems


def check_release(df: pd.DataFrame, previous: Optional[dict] = None,
                  floors: Optional[Dict[str, int]] = None,
                  allow_shrink: bool = False) -> List[str]:
    """Every reason `df` must not be published.  Empty means it may be."""
    floors = FLOORS if floors is None else floors
    problems: List[str] = []

    n = len(df)
    if n < floors["rows"]:
        problems.append("rows: %d, below the floor of %d" % (n, floors["rows"]))

    if "designation" not in df.columns:
        problems.append("no `designation` column")
    else:
        des = df["designation"]
        if des.isna().any():
            problems.append("designation: %d null" % int(des.isna().sum()))
        if des.duplicated().any():
            problems.append("designation: %d duplicated"
                            % int(des.duplicated().sum()))

    for col in ("catalog_date", "pipeline_version"):
        if col not in df.columns:
            problems.append("no `%s` column" % col)
            continue
        vals = sorted(df[col].dropna().astype(str).unique())
        if len(vals) != 1:
            problems.append("%s: expected one value, found %s" % (col, vals[:5]))
    if "pipeline_version" in df.columns:
        vals = set(df["pipeline_version"].dropna().astype(str))
        if vals and vals != {CONFIG.pipeline_version}:
            problems.append("pipeline_version: catalog says %s, this package "
                            "writes %s" % (sorted(vals), CONFIG.pipeline_version))

    measured = measured_diameters(df)
    if measured < floors["measured_diameters"]:
        problems.append("measured diameters: %d, below the floor of %d"
                        % (measured, floors["measured_diameters"]))

    # Nothing physically impossible is published, however well sourced.
    problems.extend(physical_problems(df))

    counts = source_counts(df)
    for name in SOURCE_NAMES:
        if counts[name] < floors[name]:
            problems.append("%s: %d bodies, below the floor of %d -- did its "
                            "fetch fail?" % (name, counts[name], floors[name]))

    if previous and not allow_shrink:
        tag = previous.get("release_tag", "the previous release")
        prev_rows = int(previous.get("rows", 0))
        if prev_rows and n < prev_rows * (1 - MAX_ROW_DROP):
            problems.append("rows: %d, down from %d in %s (more than %.1f%%)"
                            % (n, prev_rows, tag, MAX_ROW_DROP * 100))
        for name, prev in (previous.get("sources") or {}).items():
            now = counts.get(name, 0)
            if prev and now < prev * (1 - MAX_SOURCE_DROP):
                problems.append("%s: %d bodies, down from %d in %s (more than "
                                "%.0f%%)" % (name, now, prev, tag,
                                             MAX_SOURCE_DROP * 100))
    return problems


def write_taxonomy(path: str) -> None:
    """The composition tables, exactly: JSON floats round-trip through repr."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        # DENSITY_LIMITS_GCM3 decides which measured masses and densities a
        # build accepted, so it ships with the tables it is keyed on; and
        # DENSITY_EVIDENCE (1.5.0) with the estimates it backs, so a reader
        # of the asset can see what each class density answers to.
        json.dump({"TAXONOMY_COMPOSITION": TAXONOMY_COMPOSITION,
                   "PGM_ENRICHMENT_BY_TYPE": PGM_ENRICHMENT_BY_TYPE,
                   "DENSITY_LIMITS_GCM3": {k: list(v) for k, v in
                                           DENSITY_LIMITS_GCM3.items()},
                   "DENSITY_EVIDENCE": DENSITY_EVIDENCE},
                  fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def _notes(m: dict) -> str:
    lines = [
        "Asteroid catalog built %s, data contract **%s**, asteroid_catalog %s "
        "(commit `%s`)." % (m["catalog_date"], m["pipeline_version"],
                            m["package_version"], m["source_commit"][:12]),
        "",
        "| | |", "|---|---|",
        "| bodies | {:,} |".format(m["rows"]),
        "| columns | {:,} |".format(len(m["columns"])),
        "| measured diameters | {:,} |".format(m["measured_diameters"]),
        "| rejected at validation | {:,} |".format(m["rejected_rows"]),
    ]
    for name, count in m["sources"].items():
        lines.append("| known to {} | {:,} |".format(name, count))
    lines += ["", "| file | bytes | sha256 |", "|---|---|---|"]
    for name, entry in m["files"].items():
        lines.append("| `{}` | {:,} | `{}` |".format(name, entry["bytes"],
                                                    entry["sha256"]))
    lines += [
        "",
        "Decompressed, `asteroid_catalog.csv` is {:,} bytes with sha256 `{}`."
        .format(m["catalog_csv"]["bytes"], m["catalog_csv"]["sha256"]),
        "",
        "SsODNet and NEOWISE ask to be cited as a condition of use: see "
        "CITATIONS.md.",
        "",
    ]
    return "\n".join(lines)


def package_release(build_dir: str, out_dir: str, tag: str,
                    previous: Optional[dict] = None,
                    source_commit: str = "",
                    floors: Optional[Dict[str, int]] = None,
                    allow_shrink: bool = False) -> dict:
    """Gate a build and write its release assets to `out_dir`.

    Raises ValueError, listing every failed gate, before writing anything if
    the build must not be published.  Returns the manifest.
    """
    catalog_path = os.path.join(build_dir, CATALOG_CSV)
    rejected_path = os.path.join(build_dir, REJECTED_CSV)
    if not os.path.exists(catalog_path):
        raise FileNotFoundError("no catalog at %s" % catalog_path)

    df = read_catalog(catalog_path)
    problems = check_release(df, previous=previous, floors=floors,
                             allow_shrink=allow_shrink)
    if problems:
        raise ValueError("this build must not be published:\n  - "
                         + "\n  - ".join(problems))

    os.makedirs(out_dir, exist_ok=True)
    gzip_deterministic(catalog_path, os.path.join(out_dir, CATALOG_GZ))
    _typed_for_parquet(df).to_parquet(os.path.join(out_dir, CATALOG_PARQUET),
                                      index=False, compression="zstd")
    write_taxonomy(os.path.join(out_dir, TAXONOMY_JSON))
    n_rejected = 0
    if os.path.exists(rejected_path):
        shutil.copyfile(rejected_path, os.path.join(out_dir, REJECTED_CSV))
        n_rejected = len(pd.read_csv(rejected_path, low_memory=False))

    # `files` is exactly the downloadable assets.  The CSV inside the gzip is
    # not one, so its checksum is kept apart, for checking after decompressing.
    files = {CATALOG_GZ: _file_entry(os.path.join(out_dir, CATALOG_GZ)),
             CATALOG_PARQUET: _file_entry(os.path.join(out_dir, CATALOG_PARQUET)),
             TAXONOMY_JSON: _file_entry(os.path.join(out_dir, TAXONOMY_JSON))}
    if os.path.exists(rejected_path):
        files[REJECTED_CSV] = _file_entry(os.path.join(out_dir, REJECTED_CSV))

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "release_tag": tag,
        "catalog_date": str(df["catalog_date"].iloc[0]),
        "pipeline_version": str(df["pipeline_version"].iloc[0]),
        "package_version": __version__,
        "source_commit": source_commit,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "measured_diameters": measured_diameters(df),
        "rejected_rows": int(n_rejected),
        "sources": source_counts(df),
        "catalog_csv": _file_entry(catalog_path),
        "files": files,
    }
    with open(os.path.join(out_dir, MANIFEST), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    with open(os.path.join(out_dir, NOTES), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write(_notes(manifest))
    return manifest
