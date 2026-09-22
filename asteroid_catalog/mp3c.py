# -*- coding: utf-8 -*-
"""MP3C (Observatoire de la Cote d'Azur): physical-properties compilation.

Frequently unreachable, and that is tolerated by design: an empty source
degrades the catalog rather than failing the build.  Read the match counts
`merge_sources` prints before concluding a source contributed.
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

from .config import CatalogConfig
from .designations import _extract_canonical_designation

# ─────────────────────────────────────────────────────────────────────────────
# MP3C FETCHER  (Observatoire de la Côte d'Azur)
# ─────────────────────────────────────────────────────────────────────────────
# MP3C (Minor Planet Physical Properties Catalogue) exposes data via both a
# REST endpoint and an IVOA TAP service.  We try multiple URL shapes because
# the API has shifted between schema versions; the first response that yields
# rows wins.  Documented endpoints:
#   • https://mp3c.oca.eu/api/data?...
#   • https://mp3c.oca.eu/catalogue/Astorbphys?format=json
#   • TAP/ADQL: https://mp3c.oca.eu/tap/sync?REQUEST=doQuery&LANG=ADQL&...
#
# Note: this host may be unreachable from restricted-network runtimes (Colab
# has been observed to fail DNS resolution).  The fetcher returns an empty
# DataFrame gracefully in that case so the pipeline survives.

# MP3C's REST and TAP transports both require an explicit row count, so
# `mp3c_limit = 0` (unlimited) is expressed as a ceiling comfortably above the
# whole catalogue rather than as an absent clause.  MP3C tracks ~1.2 M bodies.
_MP3C_UNLIMITED_ROWS = 2_000_000

_MP3C_REST_ENDPOINTS = [
    "https://mp3c.oca.eu/api/data?format=json&limit={limit}",
    "https://mp3c.oca.eu/catalogue/Astorbphys?format=json&limit={limit}",
    "https://mp3c.oca.eu/catalogue/Astphys?format=json&limit={limit}",
]
# TAP endpoint accepts an ADQL query directly.  Four candidate table names are
# tried (schema-prefixed and bare forms of two known table names) because MP3C
# has changed schema naming between releases.
_MP3C_TAP_URL    = "https://mp3c.oca.eu/tap/sync"
_MP3C_TAP_TABLES = ("mp3c.astorbphys", "mp3c.astphys", "astorbphys", "astphys")

_MP3C_RENAME = {
    # designation (multiple alternatives; whichever exists in the response wins)
    "des":       "designation",
    "number":    "designation",
    "id":        "designation",
    "object":    "designation",
    # `name` passes through verbatim (source name == target name)
    # physical (`albedo` likewise passes through verbatim when present)
    "diameter":  "diameter_km",
    "diam":      "diameter_km",
    "d":         "diameter_km",
    "rho":       "density_gcm3",
    "density":   "density_gcm3",
    "pv":        "albedo",
    "h":         "absolute_magnitude_h",
    "rot_per":   "rotation_period_h",
    "period":    "rotation_period_h",
    # taxonomy
    "taxonomy":  "spectral_type",
    "tax":       "spectral_type",
    "class":     "spectral_type",
    # orbital
    "a":         "semi_major_axis_au",
    "sma":       "semi_major_axis_au",
    "e":         "eccentricity",
    "i":         "inclination_deg",
    "incl":      "inclination_deg",
}
_MP3C_NUMERIC = [
    "diameter_km", "density_gcm3", "albedo", "absolute_magnitude_h",
    "rotation_period_h", "semi_major_axis_au", "eccentricity",
    "inclination_deg",
]


def _mp3c_jsonish_to_df(payload) -> pd.DataFrame:
    """Coerce MP3C's various JSON envelopes into a single DataFrame."""
    if isinstance(payload, list):
        return pd.json_normalize(payload)
    if isinstance(payload, dict):
        for key in ("data", "results", "rows", "asteroids", "objects"):
            if key in payload and isinstance(payload[key], list):
                return pd.json_normalize(payload[key])
    return pd.DataFrame()


def fetch_mp3c(config: CatalogConfig) -> pd.DataFrame:
    """
    Fetch from MP3C.  Tries REST endpoints first, then TAP/ADQL.
    Returns EMPTY DataFrame if every approach fails.
    """
    say("\n  MP3C - Minor Planet Physical Properties Catalogue ...")

    # Both MP3C transports need a number in the query; neither has an
    # "everything" form, so an unlimited (0) config becomes a ceiling larger
    # than the catalogue rather than a missing clause.
    mp3c_rows = config.mp3c_limit or _MP3C_UNLIMITED_ROWS

    # ── Attempt 1: REST endpoints ────────────────────────────────────────────
    for endpoint_tpl in _MP3C_REST_ENDPOINTS:
        url = endpoint_tpl.format(limit=mp3c_rows)
        try:
            r = requests.get(url, timeout=config.request_timeout)
        except requests.exceptions.ConnectionError as exc:
            say(f"     WARN  REST unreachable ({str(exc)[:80]})")
            break  # if DNS fails for the host, no point trying other paths
        except requests.exceptions.Timeout:
            say(f"     WARN  REST timed out on {endpoint_tpl[:60]}...")
            continue
        except Exception as exc:
            say(f"     WARN  REST {type(exc).__name__}: {exc}")
            continue

        if r.status_code != 200 or not r.text.strip():
            continue

        try:
            df = _mp3c_jsonish_to_df(r.json())
        except Exception:
            continue
        if df is not None and not df.empty:
            return _normalise_mp3c_df(df, source_url=url)

    # ── Attempt 2: TAP / ADQL ────────────────────────────────────────────────
    for table in _MP3C_TAP_TABLES:
        adql = f"SELECT TOP {mp3c_rows} * FROM {table}"
        params = {
            "REQUEST": "doQuery",
            "LANG":    "ADQL",
            "FORMAT":  "json",
            "QUERY":   adql,
        }
        try:
            r = requests.get(_MP3C_TAP_URL, params=params,
                             timeout=config.request_timeout)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exc:
            say(f"     WARN  TAP unreachable for table '{table}' ({type(exc).__name__})")
            continue
        except Exception as exc:
            say(f"     WARN  TAP {type(exc).__name__}: {exc}")
            continue

        if r.status_code != 200 or not r.text.strip():
            continue

        try:
            df = _mp3c_jsonish_to_df(r.json())
        except Exception:
            continue
        if df is not None and not df.empty:
            return _normalise_mp3c_df(df, source_url=f"TAP:{table}")

    say("     NOTE  MP3C not reachable on any endpoint - continuing without it")
    return pd.DataFrame()


def _normalise_mp3c_df(df: pd.DataFrame, source_url: str) -> pd.DataFrame:
    """Lowercase column names, rename to standard schema, coerce numerics."""
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.rename(columns={k: v for k, v in _MP3C_RENAME.items() if k in df.columns})

    # Normalise designation via the shared canonical extractor (correctly
    # preserves provisional designations like "2024 BX1").
    if "designation" in df.columns:
        df["designation"] = _extract_canonical_designation(df["designation"])

    for col in _MP3C_NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["source_mp3c"] = True
    say(f"     OK  {len(df):,} records fetched from MP3C  ({source_url[:80]})")
    return df
