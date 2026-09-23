# -*- coding: utf-8 -*-
"""NEOWISE Diameters and Albedos V2.0, via the IRSA TAP service.

Thermal-IR diameters and albedos, which upgrade those columns wherever they
overlap the backbone.  Fetched asynchronously by default: a synchronous query
holds one connection open for both the server-side query and the ~19 MB
transfer, and a proxy timeout anywhere in that window discards the result with
nothing to retry.
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
# NEOWISE V2.0 FETCHER  (IRSA TAP, neowisesbpropv2)
# ─────────────────────────────────────────────────────────────────────────────
# NEOWISE Diameters & Albedos V2.0 is a PSI/NEOWISE-team compilation of
# infrared-measured diameters, V/NIR albedos, and beaming parameters for
# ~150 k Solar-system small bodies.  We pull it via IPAC IRSA's TAP service.
#
# Documentation:
#   https://sbn.psi.edu/pds/resource/doi/neowise_2.0.html
#   https://irsa.ipac.caltech.edu/data/WISE/NEOWISE_SB/gator_docs/
#                                       neowisesbprop_colDescriptions.html
# TAP table: neowisesbpropv2
#
# Confirmed schema (CSV column names, lower-case):
#   asteroid_number, prov_desig, comet_desig, mpc_packed_name,
#   absolute_mag, slope_param, mean_jd, n_w1..n_w4, fit_code,
#   diameter, diameter_err, v_albedo, v_albedo_err,
#   ir_albedo, ir_albedo_err, beaming_param, beaming_param_err,
#   stacked_flag, reference, notes, reference2, type, cntr

_NEOWISE_TAP_URL    = "https://irsa.ipac.caltech.edu/TAP/sync"
# IVOA UWS async endpoint.  A synchronous TAP query holds ONE connection open
# for the server-side query AND the whole ~19 MB transfer, so any proxy timeout
# in that window discards the entire result with no retry surface.  That is the
# `502 Proxy Error` that made NEOWISE contribute 0 rows to the run behind the
# committed cislunar 2x2.  Async splits the three phases: the job runs
# server-side with nothing held open, and the result sits at a stable URL that
# can be re-fetched.  Same ADQL, same rows, verified byte-identical.
_NEOWISE_TAP_ASYNC  = "https://irsa.ipac.caltech.edu/TAP/async"
_NEOWISE_TAP_TABLE  = "neowisesbpropv2"

# Terminal UWS phases.  Anything else means the job is still running.
_UWS_TERMINAL = ("COMPLETED", "ERROR", "ABORTED")

_NEOWISE_SELECT = (
    "asteroid_number, prov_desig, absolute_mag, "
    "diameter, diameter_err, "
    "v_albedo, v_albedo_err, ir_albedo, ir_albedo_err, "
    "beaming_param, beaming_param_err, stacked_flag, "
    "fit_code, reference, type"
)

_NEOWISE_RENAME = {
    "diameter":          "diameter_km",
    "diameter_err":      "diameter_sigma_km",
    "v_albedo":          "albedo",
    "v_albedo_err":      "albedo_sigma",
    "ir_albedo":         "albedo_ir",
    "ir_albedo_err":     "albedo_ir_sigma",
    "beaming_param":     "neowise_beaming_param",
    "beaming_param_err": "neowise_beaming_param_sigma",
    "stacked_flag":      "neowise_stacked",
    "absolute_mag":      "absolute_magnitude_h",
    "fit_code":          "neowise_fit_code",   # e.g. "DVB-" = diameter+V-albedo+beaming
    "reference":         "neowise_reference",
    "type":              "neowise_orbit_class",
}

_NEOWISE_NUMERIC = [
    "diameter_km", "diameter_sigma_km", "albedo", "albedo_sigma",
    "albedo_ir", "albedo_ir_sigma", "neowise_beaming_param",
    "neowise_beaming_param_sigma", "absolute_magnitude_h",
]


def _neowise_fetch_async(params: dict, config: CatalogConfig) -> Optional[bytes]:
    """Run the NEOWISE query as an IVOA UWS async job; return the body or None.

    Three phases, and the point of all of them is that nothing is held open
    while the server works:

      1. POST the query to /async.  IRSA answers 303 with a job URL in the
         Location header.  Redirects are NOT followed, because following one
         fetches the job's description page instead of leaving us the URL we
         need to drive its phase endpoints.
      2. POST PHASE=RUN, then poll until a terminal phase.  A poll that raises
         is deliberately NOT fatal: the job is still running server-side, and
         surviving a transient failure here is the entire reason for using
         async rather than sync.
      3. GET the result.  This URL is stable, so a failed transfer is
         retryable in a way a synchronous query's is not.

    Returns None on any failure, which puts the caller back on the sync path.
    """
    try:
        session = requests.Session()
        resp = session.post(
            _NEOWISE_TAP_ASYNC, data=params,
            allow_redirects=False, timeout=config.request_timeout,
        )
        if resp.status_code not in (200, 302, 303):
            say(f"     WARN  async submit returned HTTP {resp.status_code}")
            return None
        job = resp.headers.get("Location")
        if not job:
            say("     WARN  async submit returned no job URL")
            return None
        say(f"     job   {job}")

        session.post(f"{job}/phase", data={"PHASE": "RUN"},
                     timeout=config.request_timeout)

        waited, phase = 0.0, "UNKNOWN"
        while waited < float(config.neowise_async_max_wait_s):
            try:
                phase = session.get(
                    f"{job}/phase", timeout=config.request_timeout,
                ).text.strip()
            except requests.exceptions.RequestException:
                phase = "UNKNOWN"          # keep waiting; the job is server-side
            if phase in _UWS_TERMINAL:
                break
            _time.sleep(2.0)
            waited += 2.0

        if phase != "COMPLETED":
            say(f"     WARN  async job ended in phase {phase}")
            return None

        for attempt in (1, 2, 3):
            try:
                res = session.get(f"{job}/results/result",
                                  timeout=config.request_timeout)
                if res.status_code == 200:
                    return res.content
                say(f"     WARN  result HTTP {res.status_code} "
                      f"(attempt {attempt})")
            except requests.exceptions.RequestException as exc:
                say(f"     WARN  result attempt {attempt}: {type(exc).__name__}")
            _time.sleep(2.0 * attempt)
        return None

    except requests.exceptions.RequestException as exc:
        say(f"     WARN  async TAP unavailable ({type(exc).__name__})")
        return None


def fetch_neowise(config: CatalogConfig) -> pd.DataFrame:
    """
    Fetch NEOWISE V2.0 diameters & albedos via IPAC IRSA's TAP service.

    NEOWISE is a PHYSICAL-only catalog, no orbital elements, so it can't
    stand alone.  Once merged it upgrades diameter / albedo for the ~150k
    rows where it overlaps the JPL backbone.

    Tries the async (UWS) endpoint first and falls back to the synchronous one,
    so the worst case is the behaviour this function had before async existed.
    Both paths return the same bytes for the same ADQL; only their failure
    surfaces differ.  See `_neowise_fetch_async`.

    Returns EMPTY DataFrame on any unrecoverable error.
    """
    say("\n   NEOWISE V2.0 diameters & albedos  (IRSA TAP) ...")

    # ADQL.  `neowise_limit` caps the pull; 0 drops the TOP clause and takes the
    # whole table, which is only ~183 k rows / ~19 MB / ~30 s, small enough
    # that capping it buys almost nothing and costs measured diameters.
    # WHERE clause skips rows without an asteroid identifier.  That is what
    # actually excludes comets: checked 2026-09-22, no row has type 'comet'
    # (the types are neos, mainbelt, hildas, jupiter_trojans, centaurs, ...),
    # and the 4 rows the identifier clause drops are the comets 29P, 167P and
    # 324P, which carry only `comet_desig`.  183,412 rows in, 183,408 fetched.
    # ORDER BY asteroid_number so small-N runs include the low-numbered
    # (most famous) bodies: Ceres, Vesta, etc.
    top = f"TOP {int(config.neowise_limit)} " if config.neowise_limit else ""
    # 🚨  THE ORDER BY MUST BE TOTAL, AND `asteroid_number` ALONE IS NOT.
    #
    # NEOWISE carries 183,408 rows for 143,318 bodies, and 27,864 bodies have
    # more than one.  `deduplicate_catalog` sorts by completeness with
    # `kind="stable"` and keeps the first, so among rows of EQUAL completeness
    # the winner is decided by nothing but the order they arrived in.
    #
    # 27,802 bodies are in exactly that state with DIFFERENT diameters:
    # median spread 11.6%, p90 27.4%, max 86.3%.  Diameter cubes into
    # `estimated_mass_kg`, which is what the whole ranking runs on, so an 11.6%
    # diameter is a 39% mass.
    #
    # Ordering on `asteroid_number` alone leaves those ties for the server to
    # break however it plans the query, and it does not break them the same way
    # twice: a sync and an async pull of the identical ADQL returned the same
    # 183,408 rows with the same content hash in a DIFFERENT order.  So this
    # was never reproducible, and the async path only made it visible.
    #
    # Ordering on enough columns to be total makes the same rows win on every
    # run and every transport.  It deliberately does NOT try to pick the
    # physically best measurement; `fit_code` and `stacked_flag` are the fields
    # that would express that, and choosing among them is a modelling decision,
    # not a reproducibility fix.
    adql = (
        f"SELECT {top}{_NEOWISE_SELECT} "
        f"FROM {_NEOWISE_TAP_TABLE} "
        f"WHERE type != 'comet' "
        f"  AND (asteroid_number IS NOT NULL OR prov_desig IS NOT NULL) "
        f"ORDER BY asteroid_number ASC, prov_desig ASC, diameter ASC, "
        f"diameter_err ASC, v_albedo ASC, ir_albedo ASC, "
        f"beaming_param ASC, fit_code ASC, reference ASC"
    )
    params = {
        "REQUEST": "doQuery",
        "LANG":    "ADQL",
        "FORMAT":  "csv",
        "QUERY":   adql,
    }

    # Async first.  On success the sync block below is skipped; on any failure
    # `body` stays None and the original synchronous path runs unchanged, so
    # this can only add a way to succeed, never remove one.
    body = None
    if config.neowise_use_async:
        body = _neowise_fetch_async(params, config)
        if body is not None:
            say(f"     OK  async TAP returned {len(body):,} bytes")
        else:
            say("     NOTE  falling back to synchronous TAP")

    try:
        if body is None:
            with requests.get(
                _NEOWISE_TAP_URL,
                params=params,
                timeout=config.request_timeout,
                stream=True,
            ) as resp:
                if resp.status_code != 200:
                    snippet = resp.text[:300].replace("\n", " ")
                    say(f"     FAIL  HTTP {resp.status_code} - {snippet}")
                    return pd.DataFrame()

                total_bytes = int(resp.headers.get("content-length") or 0) or None
                chunks: list = []
                with tqdm(
                    total=total_bytes,
                    desc="     NEOWISE",
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    leave=True,
                    mininterval=0.3,
                ) as pbar:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            chunks.append(chunk)
                            pbar.update(len(chunk))
                body = b"".join(chunks)

    except requests.exceptions.Timeout:
        say("     FAIL  NEOWISE TAP timed out")
        return pd.DataFrame()
    except requests.exceptions.ConnectionError as exc:
        say(f"     FAIL  NEOWISE TAP unreachable ({str(exc)[:80]})")
        return pd.DataFrame()
    except Exception as exc:
        say(f"     FAIL  NEOWISE TAP error: {type(exc).__name__}: {exc}")
        return pd.DataFrame()

    # IRSA may return one of several non-CSV bodies on failure:
    #   • VOTable error envelope (XML) on a bad ADQL
    #   • HTML 200-with-error-page on a backend hiccup
    #   • empty body
    # Detect each of these explicitly so we don't try to coerce HTML/XML into
    # a DataFrame and end up with garbage rows.
    head = body[:400].lstrip()
    if not head:
        say("     FAIL  TAP returned an empty body")
        return pd.DataFrame()
    if head.startswith(b"<?xml") or head.startswith(b"<VOTABLE"):
        snippet = body[:400].decode("utf-8", errors="replace").replace("\n", " ")
        say(f"     FAIL  TAP returned a VOTable error envelope: {snippet[:200]}")
        return pd.DataFrame()
    if head[:1] == b"<":   # any other tag-leading body (HTML, etc.)
        snippet = body[:400].decode("utf-8", errors="replace").replace("\n", " ")
        say(f"     FAIL  TAP returned a non-CSV body: {snippet[:200]}")
        return pd.DataFrame()
    if not head.lower().startswith(b"asteroid_number"):
        # Expected CSV header from this query begins with `asteroid_number`.
        # Anything else means the schema or query has drifted, fail loud.
        snippet = body[:400].decode("utf-8", errors="replace").replace("\n", " ")
        say(f"     FAIL  TAP body doesn't look like expected CSV: {snippet[:200]}")
        return pd.DataFrame()

    from io import BytesIO
    try:
        df = pd.read_csv(BytesIO(body))
    except Exception as exc:
        say(f"     FAIL  CSV parse failed: {type(exc).__name__}: {exc}")
        return pd.DataFrame()

    if df.empty:
        say("     WARN  NEOWISE TAP returned 0 rows")
        return pd.DataFrame()

    # Designation: numbered → `asteroid_number`, unnumbered → `prov_desig`.
    #
    # ⚠️  `asteroid_number` MUST be rendered as an integer, and this is not a
    # cosmetic point; it is the bug that made this entire source a no-op for
    # every large run up to v1.1.0.
    #
    # IRSA types the column by what the result slice happens to contain.  A
    # slice with no unnumbered bodies comes back int64 and `.astype("string")`
    # gives "3"; add one row whose asteroid_number is null and the column is
    # float64, so the same call gives "3.0".  The canonical extractor matches
    # neither `^(\d+)\s*$` nor `^(\d+)\s+[A-Z][a-z]` against "3.0", passes it
    # through unchanged, and the merge key can never equal JPL's "3".  Every
    # NEOWISE row then reached validate_and_filter as a body nothing else had
    # heard of, and was dropped for having no semi-major axis.
    #
    # So it worked at small caps and failed at large ones, which is the worst
    # possible shape: the fetcher still printed its ✅ and its row count, and
    # the only visible trace was neowise_* columns sitting 100% empty in the
    # output CSV.  _extract_canonical_designation strips a trailing ".0"
    # defensively now as well, but do not rely on that and remove this.
    def _as_designation(numbers: pd.Series, prov: Optional[pd.Series]) -> pd.Series:
        """IRSA's asteroid_number as a merge key, or the provisional designation.

        Through `Int64` and only then to string, which is the whole point: IRSA
        types the column float64 whenever the slice holds any unnumbered body,
        and `.astype("string")` on that yields `"3.0"`, which matches no JPL
        `pdes` and is not null either. That cost NEOWISE four releases of
        contributing zero rows. See the block above.
        """
        out = pd.Series(pd.NA, index=numbers.index, dtype="string")
        num = pd.to_numeric(numbers, errors="coerce")
        has_num = num.notna()
        # Int64 first, so 3.0 renders as "3" and not "3.0".
        out[has_num] = num[has_num].astype("Int64").astype("string")
        if prov is not None:
            fallback = prov.astype("string").str.strip()
            out[~has_num] = fallback[~has_num]
        return out.replace({"": pd.NA, "<NA>": pd.NA, "nan": pd.NA})

    if "asteroid_number" in df.columns:
        df["designation"] = _as_designation(
            df["asteroid_number"],
            df["prov_desig"] if "prov_desig" in df.columns else None,
        )
    elif "prov_desig" in df.columns:
        df["designation"] = df["prov_desig"].astype("string").str.strip()

    # Drop the source-identifier columns so the rename + merge stay tidy
    df = df.drop(columns=[c for c in ("asteroid_number", "prov_desig") if c in df.columns])

    # Standard rename + numeric coercion
    df = df.rename(columns={k: v for k, v in _NEOWISE_RENAME.items() if k in df.columns})
    for col in _NEOWISE_NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Coerce the stacked-measurement flag to True/False/NaN to match the
    # boolean convention used by `is_neo`, `is_pha`, `density_measured`, …
    # NEOWISE encodes it as "Y" for stacked measurements and blank otherwise.
    if "neowise_stacked" in df.columns:
        df["neowise_stacked"] = (
            df["neowise_stacked"].astype("string").str.strip().str.upper()
              .map({"Y": True, "N": False, "1": True, "0": False, "": False})
        )

    # Canonicalise designation to JPL-pdes form
    if "designation" in df.columns:
        df["designation"] = _extract_canonical_designation(df["designation"])

    n_rows = len(df)
    df = mask_unfitted_neowise(df)
    df = combine_neowise_fits(df)

    df["source_neowise"] = True
    say(f"     OK  {n_rows:,} records fetched from NEOWISE V2.0, "
        f"{len(df):,} bodies after combining repeat fits")
    return df


# fit_code has one slot per fitted parameter, in this order; "-" (or "F", a
# fixed beaming) in a slot means that parameter was ASSUMED for the fit, not
# measured by it.
_NEOWISE_FIT_SLOTS = (
    (0, "D", ("diameter_km", "diameter_sigma_km")),
    (1, "V", ("albedo", "albedo_sigma")),
    (2, "B", ("neowise_beaming_param", "neowise_beaming_param_sigma")),
    (3, "I", ("albedo_ir", "albedo_ir_sigma")),
)


def mask_unfitted_neowise(df: pd.DataFrame) -> pd.DataFrame:
    """Blank every value NEOWISE assumed rather than measured, and its sentinels.

    ⚠️  AN UNFITTED SLOT STILL CARRIES A NUMBER, AND IT LOOKS LIKE DATA.
    Measured over the whole table on 2026-09-22: the 104,788 `DV--` rows carry
    a beaming parameter of ~1.0 +/- 0.2, which is the assumption the fit was
    run with; `DVF-` rows carry beaming 0 +/- 0; unfitted IR albedos include
    -0.999, the survey's "no value".  Kept, they average into a body's
    beaming as if measured, and a -0.999 drags a mean negative.

    Also blanks any negative value and any sigma of exactly 0 (8 rows), which
    would otherwise take infinite weight when fits are combined.
    """
    if df.empty:
        return df
    df = df.copy()
    code = (df["neowise_fit_code"].astype("string").str.ljust(4, "-")
            if "neowise_fit_code" in df.columns else None)
    for pos, letter, cols in _NEOWISE_FIT_SLOTS:
        if code is not None:
            unfitted = code.str[pos] != letter
            for c in cols:
                if c in df.columns:
                    df.loc[unfitted.fillna(False), c] = np.nan
        val, sig = cols
        if val in df.columns and sig in df.columns:
            bad = (df[val] < 0) | (df[sig] < 0)
            df.loc[bad, [val, sig]] = np.nan
            df.loc[df[sig] == 0, sig] = np.nan
    return df


# (value, sigma) pairs that are averaged across a body's fits.  Everything else
# is taken from the best-constrained fit (smallest diameter sigma).
_NEOWISE_MEASURED = (
    ("diameter_km",           "diameter_sigma_km"),
    ("albedo",                "albedo_sigma"),
    ("albedo_ir",             "albedo_ir_sigma"),
    ("neowise_beaming_param", "neowise_beaming_param_sigma"),
)


def combine_neowise_fits(df: pd.DataFrame) -> pd.DataFrame:
    """One row per body: repeat fits averaged, not one kept and the rest lost.

    NEOWISE V2.0 carries 183,408 rows for 143,318 bodies; 27,864 bodies have
    more than one fit (different epochs, fit codes, or published analyses),
    with a median diameter spread of 11.6%.  Keeping one row per body, as the
    dedup did before 1.3.0, threw the rest away and let row order pick the
    survivor.

    Each (value, sigma) pair in `_NEOWISE_MEASURED` becomes the inverse-
    variance weighted mean of the fits that report a positive sigma, or the
    plain mean where none does.  The combined sigma is the LARGER of the
    formal error of that mean and the weighted scatter between the fits.  The
    fits are not independent (several are re-analyses of the same detections),
    so the formal error alone would claim precision the data do not have.

    `neowise_n_fits` records how many fits went in; the text columns join
    their distinct values with "|" so no reference or fit code is lost.
    """
    if df.empty or "designation" not in df.columns:
        return df
    df = df[df["designation"].notna()].copy()
    # Re-runnable: the merge calls this again after re-keying, when one body's
    # fits may arrive as two already-combined rows (two designations).  The
    # formal sigma of a combined row is its weight, so the maths carries over;
    # the fit counts add.
    if "neowise_n_fits" not in df.columns:
        df["neowise_n_fits"] = 1
    counts = df.groupby("designation", sort=False).size()
    multi = df["designation"].map(counts) > 1
    single, rep = df[~multi].copy(), df[multi].copy()
    if rep.empty:
        return single.reset_index(drop=True)

    # Row that stands for the body in every column not averaged below.
    rank = rep["diameter_sigma_km"] if "diameter_sigma_km" in rep.columns \
        else pd.Series(0.0, index=rep.index)
    rep = rep.assign(_rank=rank.fillna(np.inf)).sort_values(
        ["designation", "_rank"], kind="stable").drop(columns="_rank")
    g = rep.groupby("designation", sort=False)
    out = g.first()                       # first non-null per column

    for val, sig in _NEOWISE_MEASURED:
        if val not in rep.columns:
            continue
        x = pd.to_numeric(rep[val], errors="coerce")
        s = pd.to_numeric(rep[sig], errors="coerce") if sig in rep.columns \
            else pd.Series(np.nan, index=rep.index)
        ok = x.notna()
        w = (1.0 / s.pow(2)).where(ok & (s > 0))
        has_w = w.notna().groupby(rep["designation"]).transform("any")
        # Fits without a sigma get no say when any fit of that body has one;
        # when none has, every fit counts equally.
        w = w.where(has_w, ok.astype(float)).fillna(0.0)
        wsum = w.groupby(rep["designation"]).sum()
        mean = (w * x.fillna(0.0)).groupby(rep["designation"]).sum() / wsum
        dev2 = (w * (x - rep["designation"].map(mean)).pow(2)).fillna(0.0)
        scatter = np.sqrt(dev2.groupby(rep["designation"]).sum() / wsum)
        formal = np.sqrt(1.0 / wsum).where(
            has_w.groupby(rep["designation"]).first())
        out[val] = mean.where(wsum > 0)
        out[sig] = pd.concat([formal, scatter], axis=1).max(axis=1).where(wsum > 0)

    for col in ("neowise_fit_code", "neowise_reference", "neowise_orbit_class"):
        if col in rep.columns:
            out[col] = g[col].agg(
                lambda v: "|".join(dict.fromkeys(
                    p for t in v.dropna() for p in str(t).split("|"))) or np.nan)
    if "neowise_stacked" in rep.columns:
        out["neowise_stacked"] = g["neowise_stacked"].agg(
            lambda v: bool(v.eq(True).any()))
    out["neowise_n_fits"] = g["neowise_n_fits"].sum()

    combined = pd.concat([single, out.reset_index()], ignore_index=True)
    return combined[list(single.columns)]
