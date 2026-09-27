# -*- coding: utf-8 -*-
"""Hold each class's density estimate to the masses a built catalog carries.

    python tools/density_evidence.py asteroid_catalog.parquet
    python tools/density_evidence.py asteroid_catalog.parquet --max-sigma 0.1

`taxonomy.DENSITY_EVIDENCE` holds the table to Carry (2012): his masses, his
classes.  This holds it to the masses the catalog publishes, grouped by the
row each body's composition is READ FROM (`comp_class`, or for a catalog built
before 1.6.0 the same thing recomputed: the source's class, D past 5.5 AU,
and P, M or E for an X or Xc with an albedo), so the check is of the estimate
as it is applied.  ONE selection rule:

  a SOURCE-given class       `spectral_type_source` "source" or "tholen"
  a measured density         a measured mass over its own source's measured
                             diameter (`mass_measured` and `density_measured`)
  mass known to 20%          `estimated_mass_sigma_kg / estimated_mass_kg`,
                             above 0 (a zero sigma is no sigma)
  inside Jupiter's orbit     a < 5.5 AU; past it composition is D's whatever
                             the label (physics.ICY_COMPOSITION_AU)

and DENSITY_EVIDENCE's rule: with N >= 3 such bodies, the estimate may not
exceed their mean + 2 SD, and may sit below mean - 2 SD only where
DENSITY_EVIDENCE says why (`below_because`).  N < 3 is listed, not judged.
The sigma is the mass's alone; a diameter error adds three times its own.

Two more sections.  The X complex by LABEL and albedo, P < 0.10 <= M < 0.30
<= E: the bimodality Berthier et al. (2023, Fig. 5) found, and the reason X
and Xc are split.  And the split recounted: how the bodies whose class
resolves to X or Xc divide by albedo in this catalog, and the mixture density
that implies, against the X and Xc rows (taxonomy.X_SPLIT_COUNTS).

AGREEMENT IS NOT INDEPENDENCE.  SsODNet, where most of these masses come from,
compiles the literature Carry did and a decade more of it.  Where the two
agree the masses have not moved; where they disagree (Xc, on
data-2026-09-26b), read the newer masses first.

Read-only; no network.  Exit status 1 when any class fails the rule, or the
split's mixture has drifted more than 0.05 g/cm3 from its row.
"""

import argparse
import sys
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from asteroid_catalog._frame import flag, numeric
from asteroid_catalog.enrich import composition_classes
from asteroid_catalog.physics import ICY_COMPOSITION_AU, taxonomy_group
from asteroid_catalog.query import read_catalog
from asteroid_catalog.taxonomy import (
    DENSITY_EVIDENCE, TAXONOMY_COMPOSITION, X_SPLIT_BOUNDS, X_SPLIT_CLASSES,
    X_SPLIT_COUNTS, X_SPLIT_ROWS, _by_distinct, composition_key,
)

MIN_N = 3
MIXTURE_TOLERANCE_GCM3 = 0.05
_LO, _HI = X_SPLIT_BOUNDS
X_ALBEDO_BINS = ((0.0, _LO, "P-like, p_V < %.2f" % _LO),
                 (_LO, _HI, "M-like, %.2f-%.2f" % (_LO, _HI)),
                 (_HI, 1.0, "E-like, >= %.2f" % _HI))
_COLUMNS = ["designation", "spectral_type", "spectral_type_source", "albedo",
            "estimated_mass_kg", "estimated_mass_sigma_kg", "density_gcm3",
            "mass_measured", "density_measured", "semi_major_axis_au",
            "comp_class", "catalog_date", "pipeline_version"]


def _read(path: str) -> pd.DataFrame:
    if path.endswith(".parquet"):
        import pyarrow.parquet as pq
        have = set(pq.ParquetFile(path).schema_arrow.names)
        return pd.read_parquet(path, columns=[c for c in _COLUMNS if c in have])
    return read_catalog(path)


def _classes(df: pd.DataFrame) -> pd.Series:
    """The row each body's composition is read from."""
    if "comp_class" in df.columns:
        return df["comp_class"].astype(object)
    return composition_classes(df)[0]


def measured_bodies(df: pd.DataFrame, max_sigma: float = 0.20) -> pd.DataFrame:
    """The bodies the rule counts: row, label, density, its sigma, albedo."""
    src = df.get("spectral_type_source", pd.Series("", index=df.index))
    mass = numeric(df, "estimated_mass_kg")
    rel = numeric(df, "estimated_mass_sigma_kg") / mass
    keep = (src.isin(["source", "tholen"]) & flag(df, "mass_measured")
            & flag(df, "density_measured") & (rel > 0) & (rel <= max_sigma)
            & (numeric(df, "semi_major_axis_au") < ICY_COMPOSITION_AU))
    rho = numeric(df, "density_gcm3")[keep]
    return pd.DataFrame({
        "designation": df.get("designation", pd.Series("", index=df.index))[keep],
        "class": _classes(df)[keep].astype(str),
        "label": df.loc[keep, "spectral_type"].astype(str),
        "rho": rho, "sigma": rho * rel[keep],
        "albedo": numeric(df, "albedo")[keep],
    })


def _stats(g: pd.DataFrame) -> Dict[str, float]:
    w = 1.0 / g["sigma"] ** 2
    return {"n": len(g), "mean": float(g["rho"].mean()),
            "sd": float(g["rho"].std(ddof=1)) if len(g) > 1 else np.nan,
            "median": float(g["rho"].median()),
            "wmean": float((g["rho"] * w).sum() / w.sum())}


def by_class(bodies: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    return {str(c): _stats(g) for c, g in bodies.groupby("class")}


def x_by_albedo(bodies: pd.DataFrame) -> List[Tuple[str, Dict[str, float]]]:
    """(label, stats) per albedo bin, over the bodies LABELLED X-complex."""
    groups = np.array([taxonomy_group(c) for c in bodies["label"]], dtype=object)
    x = bodies[groups == "X-complex"]
    out = []
    for lo, hi, label in X_ALBEDO_BINS:
        g = x[(x["albedo"] > 0) & (x["albedo"] >= lo) & (x["albedo"] < hi)]
        out.append((label, _stats(g) if len(g) else {"n": 0}))
    return out


def x_split_counts(df: pd.DataFrame) -> Dict[str, Tuple[int, int, int]]:
    """{row: (P, M, E)}: the bodies inside 5.5 AU whose class resolves to X
    or Xc, by measured albedo, as X_SPLIT_COUNTS was counted."""
    key = _by_distinct(df["spectral_type"], composition_key)
    p = numeric(df, "albedo")
    base = (numeric(df, "semi_major_axis_au") < ICY_COMPOSITION_AU) & (p > 0) & (p < 1)
    out = {}
    for row in X_SPLIT_ROWS:
        m = base & key.eq(row)
        out[row] = (int((m & (p < _LO)).sum()), int((m & (p >= _LO) & (p < _HI)).sum()),
                    int((m & (p >= _HI)).sum()))
    return out


def mixture_density(counts: Tuple[int, int, int]) -> float:
    n = dict(zip(X_SPLIT_CLASSES, counts))
    total = sum(counts)
    if not total:
        return np.nan
    return sum(n[c] * TAXONOMY_COMPOSITION[c]["density_est_gcm3"] for c in n) / total


def compare(df: pd.DataFrame, max_sigma: float = 0.20) -> Tuple[List[str], List[str]]:
    """(report lines, problems).  A problem is an estimate above its class's
    mean + 2 SD, or below mean - 2 SD with no stated reason, at N >= 3; or an
    X/Xc row more than 0.05 g/cm3 from the mixture this catalog's albedos
    imply."""
    bodies = measured_bodies(df, max_sigma)
    lines = ["BY COMPOSITION ROW  (source-given class, mass known to %.0f%%, a < %.1f AU)"
             % (100 * max_sigma, ICY_COMPOSITION_AU),
             "  %-6s %4s  %-13s %6s %6s   %s" % ("row", "N", "mean +/- SD", "median",
                                               "wmean", "estimate")]
    problems = []
    for cls, s in sorted(by_class(bodies).items(), key=lambda kv: -kv[1]["n"]):
        est = TAXONOMY_COMPOSITION.get(cls, {}).get("density_est_gcm3")
        verdict = ""
        if est is not None and s["n"] >= MIN_N:
            hi, lo = s["mean"] + 2 * s["sd"], s["mean"] - 2 * s["sd"]
            reason = "below_because" in DENSITY_EVIDENCE.get(cls, {})
            if est > hi:
                verdict = "  <-- above mean + 2 SD (%.2f)" % hi
            elif est < lo and not reason:
                verdict = "  <-- below mean - 2 SD (%.2f), no reason given" % lo
            elif est < lo:
                verdict = "  below mean - 2 SD, with DENSITY_EVIDENCE's reason"
            else:
                verdict = "  ok"
            if "<--" in verdict:
                problems.append("%s: estimate %.2f against %.2f +/- %.2f (N=%d)"
                                % (cls, est, s["mean"], s["sd"], s["n"]))
        elif s["n"] < MIN_N:
            verdict = "  (N < %d, not judged)" % MIN_N
        lines.append("  %-6s %4d  %5.2f +/- %-5s %6.2f %6.2f   %s%s" % (
            cls, s["n"], s["mean"], "%.2f" % s["sd"] if np.isfinite(s["sd"]) else "-",
            s["median"], s["wmean"], "-" if est is None else "%.2f" % est, verdict))

    lines.append("X COMPLEX BY ALBEDO  (bodies LABELLED X-complex, whatever row they read)")
    for label, s in x_by_albedo(bodies):
        if s["n"]:
            lines.append("  %-20s N=%-3d mean %.2f  median %.2f" % (label, s["n"], s["mean"], s["median"]))
        else:
            lines.append("  %-20s N=0" % label)

    lines.append("THE SPLIT, RECOUNTED  (class resolving to the row, a < %.1f AU, measured albedo)"
                 % ICY_COMPOSITION_AU)
    for row, counts in x_split_counts(df).items():
        rho = mixture_density(counts)
        committed = TAXONOMY_COMPOSITION[row]["density_est_gcm3"]
        bad = np.isfinite(rho) and abs(rho - committed) > MIXTURE_TOLERANCE_GCM3
        lines.append("  %-3s P/M/E %s (committed %s)  mixture %s  row %.2f%s" % (
            row, "/".join(format(c, ",") for c in counts),
            "/".join(format(c, ",") for c in X_SPLIT_COUNTS[row]),
            "%.2f" % rho if np.isfinite(rho) else "-", committed,
            "  <-- drifted" if bad else ""))
        if bad:
            problems.append("%s: its albedos imply a mixture of %.2f, the row says %.2f"
                            % (row, rho, committed))
    return lines, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("catalog", help="asteroid_catalog.csv[.gz] or .parquet")
    ap.add_argument("--max-sigma", type=float, default=0.20,
                    help="largest relative mass uncertainty counted (default 0.20)")
    args = ap.parse_args(argv)

    df = _read(args.catalog)
    stamp = ""
    if "pipeline_version" in df.columns and len(df):
        stamp = " (data contract %s, built %s)" % (df["pipeline_version"].iloc[0],
                                                  df.get("catalog_date", pd.Series([""])).iloc[0])
    print("%s: %s rows%s\n" % (args.catalog, format(len(df), ","), stamp))
    lines, problems = compare(df, args.max_sigma)
    print("\n".join(lines))
    print("\nFAILS")
    for p in problems or ["none"]:
        print("  - " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
