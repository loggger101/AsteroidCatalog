# -*- coding: utf-8 -*-
"""Which paper each SsODNet value came from, for the bodies it weighs.

IMCCE asks users of ssoBFT to publish, where possible, the reference behind
each property they use (CITATIONS.md section 1; General_Research rc-768).  The
bulk table has no reference columns: each value's `bibref` lives only in that
body's ssoCard, about 23 kB of JSON per body.  For all 1.56 M bodies that is
some 36 GB and over a million requests, so the map is scoped on purpose:

  MAPPED      every body for which SsODNet supplies a MASS or a DENSITY (about
              540 in the 2026-11 table).  Those set a body's tonnage, which is
              what this catalog's consumers price, and a mass measurement is
              rare enough that its paper matters.  For each such body every
              imported property is mapped: diameter, albedo, mass, density,
              taxonomy and H.
  NOT MAPPED  every other SsODNet value (~150,000 diameters and albedos,
              ~170,000 taxonomies, ~1.56 M H).  Their reference is one request
              away: the ssoCard of the row's `ssodnet_id`.

The map is a companion file, `ssodnet_property_refs.csv`, one row per body and
property, and a release ships it beside the catalog.  It changes no value.
Each row says what the card says the value is beside what the build imported,
because the card is served live and the bulk table is a snapshot: a row whose
values disagree names a reference for the CARD's value, which is flagged.
"""

import math
import time
from typing import Dict, List, Optional
from urllib.parse import quote

import pandas as pd
import requests

from ._log import say
from .config import CatalogConfig

# Many bodies per request (`q=A,B,...` returns a JSON list of cards).
SSOCARD_URL = "https://ssp.imcce.fr/webservices/ssodnet/api/ssocard.php?q="
REFS_FILENAME = "ssodnet_property_refs.csv"
BATCH = 40            # ~1 MB of cards per request
PAUSE_S = 1.0         # between requests: a courtesy to a public service

REFS_COLUMNS = ["designation", "ssodnet_id", "property", "imported_value",
                "card_value", "values_agree", "shortbib", "bibcode", "doi",
                "ssocard_version", "ssocard_datetime", "status"]

# catalog column -> (path into card["parameters"]["physical"], value key, scale)
# The bibref sits on the property; for H it sits on `absolute_magnitude`.
_PROPERTIES = {
    "diameter_km":          ("diameter", "value", 1.0),
    "albedo":               ("albedo", "value", 1.0),
    "estimated_mass_kg":    ("mass", "value", 1.0),
    "density_gcm3":         ("density", "value", 1e-3),    # card: kg/m^3
    "spectral_type":        ("taxonomy", "class", None),
    "absolute_magnitude_h": ("absolute_magnitude", "H", 1.0),
}


def bodies_to_map(ssodnet: pd.DataFrame) -> pd.DataFrame:
    """The SsODNet rows the map covers: those with a mass or a density."""
    if ssodnet is None or ssodnet.empty or "ssodnet_id" not in ssodnet.columns:
        return pd.DataFrame()
    has = pd.Series(False, index=ssodnet.index)
    for col in ("estimated_mass_kg", "density_gcm3"):
        if col in ssodnet.columns:
            has |= ssodnet[col].notna()
    return ssodnet[has & ssodnet["ssodnet_id"].notna()]


def _fetch_cards(ids: List[str], config: CatalogConfig) -> Dict[str, dict]:
    """ssoCards by id; a failed batch leaves its ids out."""
    cards: Dict[str, dict] = {}
    for i in range(0, len(ids), BATCH):
        batch = ids[i:i + BATCH]
        url = SSOCARD_URL + ",".join(quote(str(x), safe="") for x in batch)
        try:
            r = requests.get(url, timeout=config.request_timeout)
            r.raise_for_status()
            got = r.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            say(f"     WARN  ssoCard batch {i // BATCH + 1} failed "
                f"({type(exc).__name__}); its bodies are marked unavailable")
            continue
        for card in got if isinstance(got, list) else [got]:
            if isinstance(card, dict) and card.get("id") is not None:
                cards[str(card["id"])] = card
        if i + BATCH < len(ids):
            time.sleep(PAUSE_S)
    return cards


def _bib(refs, key: str) -> str:
    return ";".join(str(b.get(key) or "") for b in refs if isinstance(b, dict))


def _agree(imported, card) -> Optional[bool]:
    if imported is None or card is None:
        return None
    if isinstance(imported, str) or isinstance(card, str):
        return str(imported).strip() == str(card).strip()
    a, b = float(imported), float(card)
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=0.0)


def property_rows(row: pd.Series, card: Optional[dict]) -> List[dict]:
    """The map's rows for one body: one per property it imported."""
    out = []
    meta = (card or {}).get("ssocard") or {}
    phys = (((card or {}).get("parameters") or {}).get("physical")) or {}
    for col, (prop, key, scale) in _PROPERTIES.items():
        imported = row.get(col)
        if imported is None or (not isinstance(imported, str) and pd.isna(imported)):
            continue
        entry = {"designation": row.get("designation"),
                 "ssodnet_id": row.get("ssodnet_id"), "property": col,
                 "imported_value": imported, "card_value": None,
                 "values_agree": None, "shortbib": "", "bibcode": "", "doi": "",
                 "ssocard_version": meta.get("version"),
                 "ssocard_datetime": meta.get("datetime")}
        if card is None:
            entry["status"] = "card unavailable"
            out.append(entry)
            continue
        node = phys.get(prop) or {}
        value = node.get(key)
        if isinstance(value, dict):          # H: {"value": ..., "error": ...}
            value = value.get("value")
        if value is not None and scale is not None:
            value = float(value) * scale
        refs = node.get("bibref") or []
        entry.update(card_value=value, values_agree=_agree(imported, value),
                     shortbib=_bib(refs, "shortbib"), bibcode=_bib(refs, "bibcode"),
                     doi=_bib(refs, "doi"))
        if not refs:
            entry["status"] = "no bibref in card"
        elif value is None:
            entry["status"] = "no value in card"
        elif entry["values_agree"] is False:
            entry["status"] = "card value differs: reference is for the card's value"
        else:
            entry["status"] = "resolved"
        out.append(entry)
    return out


def property_refs(ssodnet: pd.DataFrame, config: CatalogConfig) -> pd.DataFrame:
    """The companion map for one build's SsODNet frame."""
    rows = bodies_to_map(ssodnet)
    if rows.empty:
        return pd.DataFrame(columns=REFS_COLUMNS)
    say(f"\n  SsODNet property references: {len(rows):,} bodies with a mass "
        f"or density, ssoCards in batches of {BATCH} ...")
    ids = [str(x) for x in rows["ssodnet_id"].tolist()]
    cards = _fetch_cards(ids, config)
    # A card the id did not find is asked for again by number.  ssoBFT's `id`
    # for a name with click consonants (469705 "ǂKá̦gára", 229762) arrives as
    # U+FFFD replacement characters, measured 2026-11-19, which matches no
    # card; the number does.
    by_number: Dict[str, dict] = {}
    retry = [str(d) for i, d in zip(ids, rows["designation"].astype(str))
             if i not in cards and d.isdigit()]
    if retry:
        for card in _fetch_cards(retry, config).values():
            if card.get("number") is not None:
                by_number[str(card["number"])] = card
    out = []
    for _, row in rows.iterrows():
        card = cards.get(str(row["ssodnet_id"])) or by_number.get(str(row["designation"]))
        out.extend(property_rows(row, card))
    df = pd.DataFrame(out, columns=REFS_COLUMNS)
    vc = df["status"].value_counts()
    say(f"     OK  {len(df):,} property rows; "
        + ", ".join(f"{k}: {int(v):,}" for k, v in vc.items()))
    return df


def refs_summary(df: pd.DataFrame) -> dict:
    """Counts for build_info.json and the release notes."""
    if df is None or df.empty:
        return {"bodies": 0, "rows": 0, "status": {}}
    return {"bodies": int(df["ssodnet_id"].nunique()), "rows": int(len(df)),
            "status": {str(k): int(v) for k, v in df["status"].value_counts().items()},
            "scope": "bodies with an SsODNet mass or density; every other "
                     "SsODNet value's reference is in the ssoCard of its ssodnet_id"}

