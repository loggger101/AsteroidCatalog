# -*- coding: utf-8 -*-
"""Audit a built or published catalog for values that cannot be right.

    python tools/audit_catalog.py asteroid_catalog.parquet
    python tools/audit_catalog.py ./data/asteroid_catalog.csv

Two sections.  IMPOSSIBLE is `release.physical_problems`, the gate a release
must pass: any line there is a value no body can have.  SUSPECT is what the
limits cannot decide: disagreements between sources, a diameter and an H that
imply an albedo no surface has, mass sigmas as large as the mass.  Nothing in
SUSPECT is wrong for certain, and every line names rows to read.

This is the audit that found the defects data contract 1.4.0 fixes, run
against the 2026-09-23 release; see CHANGELOG.md.  Read-only; no network.
"""

import argparse
import sys

import numpy as np
import pandas as pd

from asteroid_catalog.physics import (
    albedo_from_h_and_diameter, bulk_density_gcm3, density_limits, groups_of,
)
from asteroid_catalog.release import physical_problems, read_catalog


def _read(path: str) -> pd.DataFrame:
    if path.endswith(".parquet"):
        return pd.read_parquet(path)
    return read_catalog(path)


def _col(df, name):
    return (pd.to_numeric(df[name], errors="coerce") if name in df.columns
            else pd.Series(np.nan, index=df.index))


def suspects(df: pd.DataFrame):
    """(label, mask) for every check that flags a row without proving it wrong."""
    out = []
    mass, diam, h = _col(df, "estimated_mass_kg"), _col(df, "diameter_km"), _col(df, "absolute_magnitude_h")
    measured_d = df.get("diameter_source", pd.Series("", index=df.index)).eq("measured")
    mass_meas = df.get("mass_measured", pd.Series(False, index=df.index)).fillna(False).astype(bool)

    # A measured mass outside what its SOURCE-GIVEN class allows.  The gate
    # uses the any-class limits; this uses the class.
    src = df.get("spectral_type_source", pd.Series("", index=df.index)).isin(["source", "tholen"])
    lo, hi = density_limits(groups_of(df).where(src, "Unknown"))
    rho = pd.Series(bulk_density_gcm3(mass, diam), index=df.index)
    out.append(("measured mass outside its class's possible density",
                mass_meas & ((rho < lo) | (rho > hi))))

    p = pd.Series(albedo_from_h_and_diameter(h, diam), index=df.index)
    out.append(("measured diameter and H imply an albedo above 1.5", measured_d & (p > 1.5)))
    out.append(("measured diameter and H imply an albedo below 0.005", measured_d & (p < 0.005)))

    for stem, factor in (("diameter", 1.0), ("albedo", 2.0), ("mass", 1.0),
                         ("rotation_period", 1.0)):
        out.append((f"{stem}: sources disagree by more than {1 + factor:g}x",
                    _col(df, f"{stem}_spread") > factor))
    out.append(("diameter: sources differ by ~1000x (a unit error in one)",
                (_col(df, "diameter_spread") - 999).abs() < 5))
    out.append(("H: sources disagree by more than 1 mag", _col(df, "h_spread") > 1.0))
    out.append(("rotation period: sources differ by exactly 2x (half/double period)",
                ((_col(df, "rotation_period_spread") - 1.0).abs() < 0.02)))
    out.append(("measured mass whose sigma is half the value or more",
                mass_meas & (_col(df, "estimated_mass_sigma_kg") >= 0.5 * mass)))
    out.append(("albedo whose sigma is the value or more",
                _col(df, "albedo_sigma") >= _col(df, "albedo")))
    out.append(("no mass at all (class unknown)", mass.isna()))
    for stem in ("diameter", "albedo", "mass", "rotation_period"):
        col = f"{stem}_screened_out"
        if col in df.columns:
            out.append((f"{stem}: a source's value was refused (`{col}`)", df[col].notna()))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("catalog", help="asteroid_catalog.csv[.gz] or .parquet")
    ap.add_argument("--examples", type=int, default=5)
    args = ap.parse_args(argv)

    df = _read(args.catalog)
    stamp = ""
    if "pipeline_version" in df.columns and len(df):
        stamp = " (data contract %s, built %s)" % (df["pipeline_version"].iloc[0],
                                                  df.get("catalog_date", pd.Series([""])).iloc[0])
    print("%s: %s rows%s" % (args.catalog, format(len(df), ","), stamp))

    impossible = physical_problems(df)
    print("\nIMPOSSIBLE  (the release gate)")
    for line in impossible or ["none"]:
        print("  - " + line)

    print("\nSUSPECT  (read these rows)")
    des = df["designation"].astype(str) if "designation" in df.columns else df.index.astype(str)
    for label, mask in suspects(df):
        mask = mask.fillna(False).astype(bool)
        if mask.any():
            print("  - %-66s %8s   e.g. %s" % (label, format(int(mask.sum()), ","),
                                             des[mask].head(args.examples).tolist()))
    return 1 if impossible else 0


if __name__ == "__main__":
    sys.exit(main())
