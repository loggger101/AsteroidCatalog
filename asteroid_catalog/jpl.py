# -*- coding: utf-8 -*-
"""NASA JPL Small-Body Database: the orbital backbone.

JPL is the only source of orbital elements here, so a body it does not return
cannot be evaluated no matter what the other sources know about it.  That is
why it is fetched first and why it wins on conflicts.
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

# ─────────────────────────────────────────────────────────────────────────────
# JPL SBDB FETCHER  (primary source)
# ─────────────────────────────────────────────────────────────────────────────
JPL_SBDB_URL = "https://ssd-api.jpl.nasa.gov/sbdb_query.api"

# Physical + orbital fields available in the SBDB Query API.
# Note: 'density' is NOT in the SBDB query table; it only appears in the
# single-object SBDB detail endpoint.  For our pipeline density now arrives via
# SsODNet (measured) where available, otherwise enrich_composition() fills it
# from the taxonomy-based estimate.
_JPL_FIELDS = [
    "spkid",           # SPK kernel ID
    "pdes",            # primary provisional / numbered designation
    "name",            # name (if officially named)
    "neo",             # near-Earth object flag
    "pha",             # potentially hazardous flag
    "spec_B",          # Bus / Bus-DeMeo spectral classification
    "spec_T",          # Tholen spectral classification
    "diameter",        # effective diameter (km)
    "diameter_sigma",  # 1-σ uncertainty on diameter
    "albedo",          # geometric albedo
    "rot_per",         # rotation period (h)
    "e",               # eccentricity
    "a",               # semi-major axis (AU)
    "q",               # perihelion distance (AU)
    "ad",              # aphelion distance (AU)
    "i",               # inclination (deg)
    "om",              # longitude of ascending node (deg)
    "w",               # argument of perihelion (deg)
    "ma",              # mean anomaly at epoch (deg)
    # epoch, the osculating element epoch as a Julian date (TDB).  `ma` above
    # is "mean anomaly AT EPOCH" and was fetched for nine releases without it,
    # which made it unusable rather than merely unused: a mean anomaly fixes no
    # date without the epoch it is referred to.  Nothing downstream reads any
    # of om / w / ma today, so this changes no number; it is here so that the
    # next Stage 1 run captures it rather than requiring a second full refetch
    # the day somebody wants a real launch window.
    #
    # It must stay PER ROW.  Most bodies share a common epoch, but not all: a
    # 2,000-row NEO sample returned 1,999 at JD 2461200.5 and one at
    # JD 2455562.5, 5,638 days apart.  A hardcoded constant would be silently
    # wrong for exactly the minority most likely to matter.
    "epoch",

    # ── Orbit quality ────────────────────────────────────────────────────────
    # 🚨  THE RANKING IS DERIVED FROM ORBITAL ELEMENTS AND HAD NO IDEA WHICH
    # ELEMENTS WERE ANY GOOD.  `condition_code` is the MPC orbit-uncertainty
    # parameter U, 0 (well determined) to 9 (barely constrained).  Delta-v, and
    # therefore the entire economic ranking, is computed from a, e and i; a
    # body with U = 9 from a four-day arc has elements that are provisional.
    #
    # Measured 2026-09-03 against the profitability catalog on disk: of the top
    # 30 bodies by cost/revenue, 43.3% carry U >= 5 against 13.9% in the
    # population, a 3.1x enrichment at p = 8.3e-05, and the effect is strongest
    # at the very top of the ranking (Q1 35.9%, Q2 5.1%).  That is a winner's
    # curse: ranking on a quantity derived from noisy elements preferentially
    # selects the bodies whose errors happen to flatter them.
    #
    # These are FETCHED, not applied.  Filtering or down-weighting on them
    # changes what the model answers and is a modelling decision; this only
    # makes the information available to make it.  All seven are 100% populated.
    "condition_code",  # MPC orbit uncertainty U, 0 = well determined, 9 = barely
    "data_arc",        # days between first and last observation
    "n_obs_used",      # observations used in the orbit fit
    "rms",             # RMS residual of that fit, arcsec
    "moid",            # Earth minimum orbit intersection distance (AU)
    "class",           # orbit class code: MBA, APO, AMO, ATE, TNO, ...
    "soln_date",       # when the orbit solution was last updated
    "per",             # orbital period (yr)
    "n",               # mean motion (deg/day)
    # H, absolute magnitude.  Added in v1.1.0 and it is the single highest-
    # coverage physical field in the whole pipeline: 1,553,817 of JPL's
    # 1,554,321 asteroids carry one, against 139,582 with a diameter.  Every
    # other source already supplied `absolute_magnitude_h`, so the backbone was
    # the one place it was missing and derive_missing_diameters() needs it on
    # exactly the rows the other sources never reach.
    "H",
]

_JPL_RENAME = {
    "pdes":           "designation",
    # NB: `name` passes through verbatim; no entry needed since the source
    # column is already named `name` in the SBDB JSON response.
    "spec_B":         "spectral_type",          # Bus-DeMeo is preferred primary
    "spec_T":         "spectral_type_tholen",   # kept as secondary
    "diameter":       "diameter_km",
    "diameter_sigma": "diameter_sigma_km",
    # NB: `albedo` passes through verbatim (source name == target name).
    "rot_per":        "rotation_period_h",
    # density: not in SBDB Query API; sourced from SsODNet or estimated downstream
    "a":              "semi_major_axis_au",
    "e":              "eccentricity",
    "q":              "perihelion_au",
    "ad":             "aphelion_au",
    "i":              "inclination_deg",
    "om":             "longitude_asc_node_deg",
    "w":              "arg_perihelion_deg",
    "ma":             "mean_anomaly_deg",
    "epoch":          "element_epoch_jd",
    "condition_code": "orbit_condition_code",
    "data_arc":       "observation_arc_days",
    "n_obs_used":     "n_observations",
    "rms":            "orbit_fit_rms_arcsec",
    "moid":           "earth_moid_au",
    "class":          "orbit_class",
    "soln_date":      "orbit_solution_date",
    "per":            "orbital_period_yr",
    "n":              "mean_motion_deg_day",
    "H":              "absolute_magnitude_h",
    "neo":            "is_neo",
    "pha":            "is_pha",
    "spkid":          "spk_id",
}

_JPL_NUMERIC = [
    "diameter_km", "diameter_sigma_km", "albedo", "rotation_period_h",
    "semi_major_axis_au", "eccentricity", "perihelion_au",
    "aphelion_au", "inclination_deg", "longitude_asc_node_deg",
    "arg_perihelion_deg", "mean_anomaly_deg", "orbital_period_yr",
    "mean_motion_deg_day", "absolute_magnitude_h",
    # SBDB returns the epoch as a STRING ("2461200.5").  It must be coerced
    # here or it lands in the CSV as text, which is the float-typed-identifier
    # trap in the other direction: a number that never compares numerically.
    "element_epoch_jd",
    # Same for the orbit-quality numerics.  `orbit_class` and
    # `orbit_solution_date` are deliberately NOT here: one is a category code
    # and the other a date, and coercing either would silently null it.
    "orbit_condition_code", "observation_arc_days", "n_observations",
    "orbit_fit_rms_arcsec", "earth_moid_au",
]


def fetch_jpl_sbdb(config: CatalogConfig) -> pd.DataFrame:
    """
    Fetch asteroid physical + orbital data from NASA JPL SBDB Query API.

    Strategy:
      • Attempt 1: full field list (spec_B, spec_T, diameter, albedo, …)
      • Attempt 2, minimal safe fields (orbital only + diameter + albedo)
        used as fallback if any field name in attempt 1 is rejected.
    Returns EMPTY DataFrame on any unrecoverable error.
    """
    say("\n  JPL Small-Body Database  (ssd-api.jpl.nasa.gov) ...")

    # Minimal field set guaranteed to exist in every SBDB query response.
    # Used as fallback if the full list causes a 400.
    # `epoch` is carried here as well as in _JPL_FIELDS deliberately: `ma` is in
    # this list, and a mean anomaly without its epoch is unusable, so omitting
    # it from the fallback would reintroduce the exact defect the full list
    # fixes, on precisely the runs where the full list already failed.
    _SAFE_FIELDS = "pdes,name,spkid,neo,pha,diameter,diameter_sigma,albedo,rot_per,e,a,q,ad,i,om,w,ma,epoch,per,n,H,condition_code,data_arc,n_obs_used,rms,moid,class,soln_date"

    base_params = {
        "sb-kind":   "a",           # asteroids only
        "full-prec": "true",
        # NOTE: sb-cond removed, the '>' operator encoding caused HTTP 400.
        #       Filtering by diameter > 0 is handled in Python (validate_and_filter).
    }

    # `limit` is OMITTED entirely when the cap is 0.  SBDB has no server-side
    # maximum, it returns all 1,554,321 asteroids for ~435 MB in ~80 s, and
    # sending `limit=0` would be read as a literal zero-row request rather than
    # as "no limit".
    if config.jpl_limit:
        base_params["limit"] = config.jpl_limit
    else:
        say("     NOTE   No row cap - requesting the full SBDB asteroid table "
              "(~1.55 M rows, ~435 MB).  Set CONFIG.jpl_limit for a faster run.")

    attempts = [
        ("full fields",  {**base_params, "fields": ",".join(_JPL_FIELDS)}),
        ("safe fields",  {**base_params, "fields": _SAFE_FIELDS}),
    ]

    for attempt_name, params in attempts:
        try:
            # Stream the response so we can render a byte-progress bar; the
            # full-50k payload is several MB and otherwise feels like a hang.
            with requests.get(
                JPL_SBDB_URL,
                params=params,
                timeout=config.request_timeout,
                stream=True,
            ) as resp:

                # On 400 print the API error message so future issues are diagnosable
                if resp.status_code == 400:
                    try:
                        api_msg = resp.json().get("message", resp.text[:300])
                    except Exception:
                        api_msg = resp.text[:300]
                    say(f"     WARN  HTTP 400 on {attempt_name} - API says: {api_msg}")
                    continue   # try next attempt

                resp.raise_for_status()

                # Pull the body in chunks while updating a tqdm bar.  If the
                # server reports Content-Length we get a proper percentage;
                # otherwise total=None makes tqdm show an indeterminate bar
                # that still reports bytes-downloaded in real time.
                total_bytes = int(resp.headers.get("content-length") or 0) or None
                chunks: list = []
                with tqdm(
                    total=total_bytes,
                    desc=f"     JPL ({attempt_name})",
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

            try:
                payload = json.loads(body)
            except json.JSONDecodeError as exc:
                say(f"     FAIL  JSON decode failed on {attempt_name}: {exc}")
                continue

            if "data" not in payload or not payload["data"]:
                say(f"     WARN  No data on {attempt_name} - trying next")
                continue

            # SBDB Query API returns "fields" as a plain list of strings
            # e.g. ["pdes", "name", "a", ...] NOT [{"name": "pdes"}, ...]
            raw_fields = payload["fields"]
            field_names = [
                f["name"] if isinstance(f, dict) else str(f)
                for f in raw_fields
            ]
            df = pd.DataFrame(payload["data"], columns=field_names)

            # Rename to standard schema
            df = df.rename(columns={k: v for k, v in _JPL_RENAME.items() if k in df.columns})

            # Coerce numerics
            for col in _JPL_NUMERIC:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # Boolean flags
            for flag in ("is_neo", "is_pha"):
                if flag in df.columns:
                    df[flag] = df[flag].map({"Y": True, "N": False, True: True, False: False})

            df["source_jpl"] = True
            say(f"     OK  {len(df):,} records fetched from JPL SBDB ({attempt_name})")
            return df

        except requests.exceptions.Timeout:
            say(f"     FAIL  Timeout on {attempt_name}")
        except requests.exceptions.ConnectionError:
            say("     FAIL  Connection error - JPL SBDB skipped entirely")
            return pd.DataFrame()
        except requests.exceptions.HTTPError as exc:
            say(f"     FAIL  HTTP {exc.response.status_code} on {attempt_name}")
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            say(f"     FAIL  Parse error ({exc}) on {attempt_name}")
        except Exception as exc:
            say(f"     FAIL  Unexpected error ({exc}) on {attempt_name}")

    warn("     FAIL  All JPL SBDB attempts failed - skipped")
    return pd.DataFrame()
