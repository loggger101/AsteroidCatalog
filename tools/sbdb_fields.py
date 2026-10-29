# -*- coding: utf-8 -*-
"""Which SBDB fields does the build not ask for, and do the ones it asks for still exist?

    python tools/sbdb_fields.py
    python tools/sbdb_fields.py --from fields.json    # a saved answer, no network

`_JPL_FIELDS` is a literal, so it can only hold what somebody thought of.
`epoch` was missing from it for nine releases and `condition_code` from the
beginning, and both were one call away from being visible: SBDB publishes its
field list at `?info=field`.  This asks for that list and sorts every field
into one of four answers.

  REQUESTED     in `_JPL_FIELDS` and on SBDB's list.  Nothing to do.
  DECLINED      on the list, deliberately not requested; `DECLINED` below says
                why.  A decline whose field has left the list is printed so the
                entry can go.
  UNREVIEWED    on the list, neither requested nor declined.  Nobody has decided
                about these.  Each is a line to read, not a failure: requesting
                one adds a column, which is a data-contract change.
  MISSING       requested but absent from the list.  A field SBDB drops makes
                the full-field request fail with HTTP 400, and if it is also in
                `_JPL_SAFE_FIELDS` the fallback fails too and JPL, the only
                source of orbital elements, is skipped.  A field SBDB accepts
                without listing goes in `UNLISTED_BUT_ACCEPTED`, and online the
                tool asks for each one to prove it still answers.

Exit status 1 on any MISSING field, or an unlisted one that no longer answers.
Read-only; this is the check SPACE-MAP.md section 2 in starred-repos proposed,
kept out of the build's fetch path.
"""

import argparse
import json
import sys

import requests

from asteroid_catalog.jpl import JPL_SBDB_URL, _JPL_FIELDS

# Fields SBDB offers that the build deliberately does not request.  Coverage
# figures were measured against the full asteroid table on 2026-09-03 (starred-
# repos SPACE-MAP.md section 1); coverage moves, as H_sigma's did, so a decline
# made on one is worth re-measuring before it is relied on.
DECLINED = {
    "G":         "under 1% coverage (0.10%, 2026-09-03)",
    "BV":        "under 1% coverage (0.85%, 2026-09-03)",
    "UB":        "under 1% coverage (0.81%, 2026-09-03)",
    "IR":        "under 1% coverage (0.00%, 2026-09-03)",
    "extent":    "under 1% coverage (0.02%, 2026-09-03)",
    "M1":        "comets only; the fetch asks sb-kind=a",
    "M2":        "comets only; the fetch asks sb-kind=a",
    "K1":        "comets only; the fetch asks sb-kind=a",
    "K2":        "comets only; the fetch asks sb-kind=a",
    "PC":        "comets only; the fetch asks sb-kind=a",
    "prefix":    "comets only; the fetch asks sb-kind=a",
    "epoch_mjd": "`epoch` in another form",
    "epoch_cal": "`epoch` in another form",
    "per_y":     "`per` in years, rounded to two digits even under full-prec",
    "moid_ld":   "`moid` in lunar distances",
    "tp_cal":    "`tp` in calendar form",
}

# Requested fields the query API answers although `?info=field` does not list
# them.  Each was checked by asking for it; online, the tool asks again.
UNLISTED_BUT_ACCEPTED = {
    "soln_date": "answered on 2026-10-29, 2021-04-13 11:04:44 for 1 Ceres",
}


def offered_fields(payload: dict) -> dict:
    """{field name: description} from an `?info=field` answer."""
    out = {}
    for block in payload["info"]["field"].values():
        for f in block["list"]:
            out[f["name"]] = f.get("description") or ""
    return out


def compare(offered, requested=_JPL_FIELDS, declined=DECLINED,
            unlisted_ok=UNLISTED_BUT_ACCEPTED) -> dict:
    """Sort SBDB's list against what the build requests.  Pure: no network."""
    offered = set(offered)
    requested = list(requested)
    return {
        "requested": [f for f in requested if f in offered],
        "declined": sorted(f for f in declined if f in offered),
        "stale_declines": sorted(f for f in declined if f not in offered),
        "unreviewed": sorted(offered - set(requested) - set(declined)),
        "unlisted_ok": [f for f in requested if f not in offered and f in unlisted_ok],
        "missing": [f for f in requested if f not in offered and f not in unlisted_ok],
        "declined_and_requested": sorted(set(declined) & set(requested)),
    }


def _get(params: dict, timeout: float) -> dict:
    resp = requests.get(JPL_SBDB_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def still_answers(field: str, timeout: float = 60.0) -> bool:
    """Whether the query API returns `field` when asked for it, on one row."""
    try:
        payload = _get({"fields": "pdes," + field, "limit": 1, "sb-kind": "a"}, timeout)
    except (requests.RequestException, ValueError):
        return False
    return field in (payload.get("fields") or []) and bool(payload.get("data"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="path", help="a saved ?info=field answer; skips the network")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args(argv)

    if args.path:
        with open(args.path, encoding="utf-8") as fh:
            payload = json.load(fh)
        source = args.path
    else:
        payload = _get({"info": "field"}, args.timeout)
        source = JPL_SBDB_URL + "?info=field"
    offered = offered_fields(payload)
    r = compare(offered)
    print("%s: %d fields offered, %d requested" % (source, len(offered), len(_JPL_FIELDS)))

    bad = []
    if r["declined_and_requested"]:
        bad += ["declined and requested at once: %s" % ", ".join(r["declined_and_requested"])]

    print("\nMISSING  (requested, not on SBDB's list)")
    for f in r["missing"]:
        bad.append("requested but not offered: " + f)
        print("  ! " + f)
    for f in r["unlisted_ok"]:
        if args.path:
            print("  - %-14s unlisted; not re-asked offline (%s)" % (f, UNLISTED_BUT_ACCEPTED[f]))
        elif still_answers(f, args.timeout):
            print("  - %-14s unlisted, still answers" % f)
        else:
            bad.append("unlisted and no longer answers: " + f)
            print("  ! %-14s unlisted and NO LONGER ANSWERS" % f)
    if not r["missing"] and not r["unlisted_ok"]:
        print("  none")

    print("\nUNREVIEWED  (offered, neither requested nor declined)")
    for f in r["unreviewed"]:
        print("  - %-14s %s" % (f, offered[f]))
    if not r["unreviewed"]:
        print("  none")

    print("\nDECLINED  (%d, reasons in DECLINED)" % len(r["declined"]))
    for f in r["stale_declines"]:
        print("  - %-14s no longer offered; the entry can go" % f)

    for line in bad:
        print("\n! " + line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
