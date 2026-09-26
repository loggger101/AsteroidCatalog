# -*- coding: utf-8 -*-
"""MP3C (Observatoire de la Cote d'Azur): physical-properties compilation.

Pulled from MP3C's IVOA TAP service on the OCA DaCHS data center, table
`mp3c_main.best` (one row of best values per body, ~1.34 M bodies).

⚠️  UNTIL 1.3.0 THIS SOURCE CONTRIBUTED NOTHING, AND LOOKED LIKE AN OUTAGE.
The fetcher asked `mp3c.oca.eu/api/data`, `/catalogue/Astorbphys` and
`mp3c.oca.eu/tap/sync`.  Checked 2026-09-22, the host was up and every one of
those answered 404 or redirected to the home page: MP3C moved its TAP service
to `dachs.oca.eu/tap` and renamed its tables to `mp3c_main.*`.  Because an
unreachable MP3C was documented as normal, a fetcher pointed at the wrong
address was indistinguishable from a server that was down.  If this starts
returning nothing again, check the address before blaming the host:
https://mp3c.oca.eu/doc/tap/ documents the service.
"""

import io
import re

import numpy as np
import pandas as pd
import requests

from ._frame import coerce_numeric
from ._log import say

from .config import CatalogConfig
from .designations import _extract_canonical_designation, _unpack_mpc_number

_MP3C_TAP_URL = "https://dachs.oca.eu/tap/sync"

# Best values joined to the primary designation ("Ceres", "2005 CQ33").
_MP3C_BEST_ADQL = (
    "SELECT {top}b.bid, body.name, b.diameter, b.diameter_err, b.albedo, "
    "b.albedo_err, b.mass, b.mass_err, b.h, b.h_err, b.parent_name, "
    "b.a_p, b.e_p, b.i_p "
    "FROM mp3c_main.best AS b JOIN mp3c_main.body AS body USING (bid) "
    # Unqualified: DaCHS's parser rejects `b.bid` here, the USING column.
    "ORDER BY bid"
)

# A numbered body's NUMBER lives only in the alias table, as an MPC packed
# number ("00001", "A1955", "~0001").  `LIKE '_____'` narrows the 6 M aliases to
# the five-character ones; `_unpack_mpc_number` rejects the names among them.
_MP3C_NUMBERS_ADQL = (
    "SELECT bid, name FROM mp3c_main.name "
    "WHERE name LIKE '_____' AND priority = 3"
)

_MP3C_RENAME = {
    "diameter":     "diameter_km",
    "diameter_err": "diameter_sigma_km",
    "albedo":       "albedo",
    "albedo_err":   "albedo_sigma",
    "mass":         "estimated_mass_kg",
    "mass_err":     "estimated_mass_sigma_kg",
    "h":            "absolute_magnitude_h",
    "h_err":        "absolute_magnitude_h_sigma",
    # Collisional family, and the proper elements it is identified from.
    # Proper elements are the long-term averages of the osculating ones, so
    # they get their own columns and never fill `semi_major_axis_au` & co.
    "parent_name":  "family",
    "a_p":          "proper_semi_major_axis_au",
    "e_p":          "proper_eccentricity",
    "i_p":          "proper_inclination_deg",
}
_MP3C_NUMERIC = [
    "diameter_km", "diameter_sigma_km", "albedo", "albedo_sigma",
    "estimated_mass_kg", "estimated_mass_sigma_kg",
    "absolute_magnitude_h", "absolute_magnitude_h_sigma",
    "proper_semi_major_axis_au", "proper_eccentricity", "proper_inclination_deg",
]

# The MAXREC ceiling for an uncapped pull, comfortably above the ~1.34 M bodies
# and ~0.9 M packed numbers MP3C holds.  DaCHS truncates silently at its
# default otherwise.
_MP3C_UNLIMITED_ROWS = 5_000_000


def _tap_csv(adql: str, maxrec: int, config: CatalogConfig,
             expect: str) -> pd.DataFrame:
    """Run one synchronous TAP query; empty frame (with a reason) on failure."""
    try:
        r = requests.post(
            _MP3C_TAP_URL,
            data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv",
                  "MAXREC": str(maxrec), "QUERY": adql},
            timeout=config.request_timeout,
        )
    except requests.exceptions.RequestException as exc:
        say(f"     WARN  MP3C TAP unreachable ({type(exc).__name__})")
        return pd.DataFrame()
    head = r.content[:200].lstrip().lower()
    if r.status_code != 200 or not head.startswith(expect.encode()):
        # TAP reports a failed query as HTTP 200 with a VOTable whose
        # QUERY_STATUS INFO holds the reason; show that, not the XML preamble.
        text = r.content[:4000].decode("utf-8", errors="replace")
        m = re.search(r'QUERY_STATUS"\s+value="ERROR">([^<]+)', text)
        reason = m.group(1) if m else text.replace("\n", " ")[:160]
        say(f"     WARN  MP3C TAP query failed (HTTP {r.status_code}): {reason[:200]}")
        return pd.DataFrame()
    return pd.read_csv(io.BytesIO(r.content),
                       dtype={"name": "string", "parent_name": "string"},
                       keep_default_na=False, na_values=[""], low_memory=False)


def _mask_mp3c_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    """Blank MP3C's "no value" placeholders, which are ordinary numbers.

    Measured 2026-09-22 against JPL for the same bodies: H = 0.00 on 342
    bodies and H = 99.99 on 96, where JPL has H 14.6-27; diameter = 0 on 77.
    An H of 0 would read as a body the size of a dwarf planet.  No real body in
    the table has H exactly 0 (the dwarf planets sit at -1.2 to +0.3 without
    touching it), so exact 0 is safe to treat as missing.
    """
    h = "absolute_magnitude_h"
    if h in df.columns:
        bad = (df[h] == 0) | (df[h] >= 90)
        df.loc[bad, [c for c in (h, "absolute_magnitude_h_sigma") if c in df.columns]] = np.nan
    for val, sig in (("diameter_km", "diameter_sigma_km"),
                     ("albedo", "albedo_sigma"),
                     ("estimated_mass_kg", "estimated_mass_sigma_kg")):
        if val in df.columns:
            bad = ~(df[val] > 0) & df[val].notna()
            df.loc[bad, [c for c in (val, sig) if c in df.columns]] = np.nan
    return df


def fetch_mp3c(config: CatalogConfig) -> pd.DataFrame:
    """
    Fetch MP3C best values through the OCA DaCHS TAP service.

    `designation` is the body's number where MP3C lists one, else its primary
    designation, so it keys the same way JPL does; identity.py re-keys what
    that misses.  Returns an EMPTY DataFrame if the service fails.
    """
    say("\n  MP3C - Minor Planet Physical Properties Catalogue  (dachs.oca.eu TAP) ...")

    maxrec = config.mp3c_limit or _MP3C_UNLIMITED_ROWS
    top = f"TOP {int(config.mp3c_limit)} " if config.mp3c_limit else ""
    best = _tap_csv(_MP3C_BEST_ADQL.format(top=top), maxrec, config, "bid")
    if best.empty:
        say("     NOTE  MP3C not reachable - continuing without it")
        return pd.DataFrame()

    numbers = _tap_csv(_MP3C_NUMBERS_ADQL, _MP3C_UNLIMITED_ROWS, config, "bid")
    if numbers.empty:
        # Without numbers every numbered body keys on its name or provisional
        # designation; the alias map still places most of them, so carry on.
        say("     WARN  MP3C numbers unavailable - keying on names only")
    else:
        numbers["number"] = _unpack_mpc_number(numbers["name"])
        numbers = numbers.dropna(subset=["number"]).drop_duplicates("bid")
        best = best.merge(numbers[["bid", "number"]], on="bid", how="left")

    key = best["number"] if "number" in best.columns \
        else pd.Series(pd.NA, index=best.index, dtype="string")
    best["designation"] = _extract_canonical_designation(
        key.astype("string").fillna(best["name"].astype("string")))

    df = best.rename(columns=_MP3C_RENAME)
    df = df.drop(columns=[c for c in ("bid", "name", "number") if c in df.columns])
    coerce_numeric(df, _MP3C_NUMERIC)
    df = _mask_mp3c_sentinels(df)
    df["family"] = df["family"].astype("string").str.strip().replace({"": pd.NA})

    df["source_mp3c"] = True
    say(f"     OK  {len(df):,} records fetched from MP3C "
        f"({int(df['diameter_km'].notna().sum()):,} with a diameter)")
    return df