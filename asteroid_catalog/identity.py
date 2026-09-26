# -*- coding: utf-8 -*-
"""Which backbone body is this row?  Answered before anything is joined.

ONE BODY, SEVERAL DESIGNATIONS, AND EVERY SOURCE PICKS A DIFFERENT ONE.  An
asteroid is found under a provisional designation, is often found again under
a second one before anybody links the two, and is later numbered.  JPL keys on
the number when there is one and otherwise on its chosen primary provisional
designation; the other sources key on whichever of those they had when their
table was built.  Joining on the raw string therefore does two wrong things at
once, and neither is visible in the output:

  * a supplement row for a body JPL knows under another designation matches
    nothing, enters as a "new" body, and is either dropped at validation (no
    orbit: NEOWISE, measured 2026-09-22 losing 10,627 of its 143,318 bodies
    this way) or, worse, KEPT as a duplicate of a body already in the catalog
    (SsODNet rows carry their own orbit: 182 duplicated bodies in the
    2026-08-11 build, e.g. SsODNet "2001 FF217" beside JPL "2015 KN450");
  * the measurement that row carries never reaches the body it belongs to.

So every supplement row is re-keyed onto the backbone's designation first:

  1. From what the backbone itself says: its designation, the primary
     provisional designation in JPL's `full_name` ("433 Eros (A898 PA)"), and
     its IAU name.  This recovers every body numbered since a source's table
     was built.
  2. From the Minor Planet Center's designation links: `mpcorb_extended`
     lists, for every body, its number, name, principal designation and every
     OTHER designation it has been identified with.  One ~180 MB file, cached;
     it places the secondary designations JPL's bulk API has no field for.

⚠️  NOT JPL'S SINGLE-OBJECT API, ALTHOUGH IT KNOWS THE SAME LINKS.  Looking
the ~5,400 leftovers up one at a time was tried on 2026-09-22: sequential
requests at ~5/s drew HTTP 403 for the whole IP address within about a
thousand lookups, which would also have blocked the bulk JPL download every
build starts with.  The 938 answers it gave before the block agree with the
MPC links on every one, so the bulk file loses nothing but the risk.
"""

import gzip
import os
import re
from typing import Dict, Optional

import pandas as pd
import requests

from ._http import write_body
from ._log import say, warn

from .config import CatalogConfig, _cache_is_fresh, _resolve_cache_dir
from .designations import _designation_key, _extract_canonical_designation

MPC_EXTENDED_URL = "https://minorplanetcenter.net/Extended_Files/mpcorb_extended.json.gz"
_MPC_CACHE_FILE = "mpcorb_extended.json.gz"


def _unambiguous(alias: pd.Series, to: pd.Series, what: str) -> Dict[str, str]:
    """alias -> to, leaving out any alias that points at two different bodies.

    A wrong join is worse than no join, because nothing downstream can see it.
    """
    pairs = pd.DataFrame({"alias": alias, "to": to}).dropna().drop_duplicates()
    ambiguous = pairs["alias"].duplicated(keep=False)
    if ambiguous.any():
        say(f"        {int(pairs.loc[ambiguous, 'alias'].nunique()):,} {what} "
            f"alias(es) name more than one body - left unresolved")
    pairs = pairs[~ambiguous]
    return dict(zip(pairs["alias"], pairs["to"]))


def build_alias_map(backbone: pd.DataFrame) -> Dict[str, str]:
    """Every string that names a backbone body, mapped to its designation.

    Reads `designation`, `provisional_designation` and `name`.
    """
    des = _extract_canonical_designation(backbone["designation"])
    alias = [_designation_key(backbone["designation"])]
    to = [des]
    for col in ("provisional_designation", "name"):
        if col in backbone.columns:
            alias.append(_designation_key(backbone[col]))
            to.append(des)
    return _unambiguous(pd.concat(alias, ignore_index=True),
                        pd.concat(to, ignore_index=True), "backbone")


def resolve_designations(
    designations: pd.Series,
    alias_map: Dict[str, str],
    links: Optional[Dict[str, str]] = None,
) -> pd.Series:
    """Re-key `designations` onto the backbone; unresolvable ones pass through.

    `links` is an extra alias -> designation table (the MPC's, from
    `fetch_mpc_identifications`).  Its answer is itself run through
    `alias_map`, because the MPC names a numbered body by its number and an
    unnumbered one by its principal designation, either of which the backbone
    may spell as an alias.

    A designation nothing recognises is returned unchanged, so it still enters
    the merge as a new body and still shows up in the match counts.  Nothing
    is dropped here.
    """
    keys = _designation_key(designations)
    out = keys.map(alias_map).astype("string")

    if links:
        todo = out.isna() & keys.notna()
        via = keys[todo].map(links).astype("string")
        via = _designation_key(via).map(alias_map).astype("string").fillna(
            _extract_canonical_designation(via))
        out.loc[via.index] = via

    return out.fillna(_extract_canonical_designation(designations))


# ─────────────────────────────────────────────────────────────────────────────
# MPC DESIGNATION LINKS  (mpcorb_extended.json.gz, cached)
# ─────────────────────────────────────────────────────────────────────────────
# The file is one JSON array of ~1.57 M flat objects, ~1.5 GB uncompressed.  It
# is scanned in chunks with a regex rather than json.load()ed: an object holds
# no nested braces (Other_desigs is a list of strings), so `{[^{}]*}` delimits
# one exactly, and only four of its ~35 fields are read.  15 s for the whole
# file on 2026-09-22.
_OBJ   = re.compile(r"\{([^{}]*)\}")
_NUM   = re.compile(r'"Number":\s*"\((\d+)\)"')
_NAME  = re.compile(r'"Name":\s*"([^"]+)"')
_PRIN  = re.compile(r'"Principal_desig":\s*"([^"]+)"')
_OTHER = re.compile(r'"Other_desigs":\s*\[([^\]]*)\]')
_STR   = re.compile(r'"([^"]+)"')


def _mpc_cache_path(config: CatalogConfig) -> str:
    """Where the MPC file is cached, beside the SsODNet parquet."""
    return os.path.join(_resolve_cache_dir(config), _MPC_CACHE_FILE)


def _download_mpc(dest: str, config: CatalogConfig) -> bool:
    """Stream the MPC file to `dest` atomically; False on any failure."""
    try:
        with requests.get(MPC_EXTENDED_URL, stream=True,
                          timeout=config.request_timeout) as resp:
            resp.raise_for_status()
            write_body(resp, dest, "     MPC designations")
        return True
    except (requests.exceptions.RequestException, OSError) as exc:
        say(f"     FAIL  MPC download failed: {type(exc).__name__}: {str(exc)[:80]}")
        return False


def _parse_mpc_links(path: str) -> pd.DataFrame:
    """(alias, to) for every designation and name the MPC links to a body.

    `to` is the body's number where it has one, else its principal
    designation, which is how JPL keys the same body.
    """
    alias, to = [], []
    tail = ""
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        while True:
            chunk = fh.read(1 << 25)
            if not chunk:
                break
            text = tail + chunk
            cut = text.rfind("}") + 1
            body, tail = text[:cut], text[cut:]
            for m in _OBJ.finditer(body):
                o = m.group(1)
                num, prin = _NUM.search(o), _PRIN.search(o)
                target = num.group(1) if num else (prin.group(1) if prin else None)
                if target is None:
                    continue
                names = [prin.group(1)] if prin else []
                nm = _NAME.search(o)
                if nm:
                    names.append(nm.group(1))
                other = _OTHER.search(o)
                if other:
                    names.extend(_STR.findall(other.group(1)))
                alias.extend(names)
                to.extend([target] * len(names))
    return pd.DataFrame({"alias": alias, "to": to})


def fetch_mpc_identifications(config: CatalogConfig) -> Dict[str, str]:
    """The MPC's alias -> body table, or {} if it cannot be had.

    Cached for `cache_max_age_days` like the SsODNet parquet; a stale cache is
    used, with a note, when a refresh fails.  An empty result only costs the
    ~5,000 bodies the backbone's own aliases cannot place, so it degrades the
    merge rather than failing it.
    """
    say("\n  MPC designation links  (minorplanetcenter.net) ...")
    path = _mpc_cache_path(config)
    if _cache_is_fresh(path, config.cache_max_age_days):
        say(f"       Using cached file: {path}")
    elif not _download_mpc(path, config):
        if not os.path.exists(path):
            warn("     WARN  MPC designation links unavailable - bodies that "
                 "sources list under a secondary designation will not join "
                 "(~5,000 on a full build)")
            return {}
        say("     NOTE  refresh failed - using the stale cached copy")

    try:
        pairs = _parse_mpc_links(path)
    except (OSError, EOFError, ValueError) as exc:
        warn(f"     WARN  MPC file unreadable ({type(exc).__name__}) - "
             f"designation links skipped; delete {path} to re-download")
        return {}
    links = _unambiguous(_designation_key(pairs["alias"]),
                         _extract_canonical_designation(pairs["to"]), "MPC")
    say(f"     OK  {len(links):,} designations linked to "
        f"{pairs['to'].nunique():,} bodies")
    return links