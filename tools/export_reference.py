# -*- coding: utf-8 -*-
"""Write the reference tables to CSV, so they are readable without Python.

    py tools/export_reference.py

The tables in `asteroid_catalog/taxonomy.py` are the authority; these files are
a rendering of them.  THE RENDERING IS CHECKED, not trusted:
`tests/test_reference_export.py` regenerates them in a temp directory and holds
them byte for byte against what is committed, so a table edited without
re-exporting turns the suite red rather than leaving two answers in the repo.

CSVs are written with a pinned CRLF terminator for the same reason the catalog
writer pins one: `to_csv` defaults to os.linesep, which would make these files
differ on Linux and Windows for no data reason.
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asteroid_catalog.taxonomy import (          # noqa: E402
    TAXONOMY_COMPOSITION, PGM_ENRICHMENT_BY_TYPE, pgm_enrichment_for_type,
)

FIELDS = ["spectral_type", "group", "composition", "minerals",
          "density_est_gcm3", "metal_fraction", "silicate_fraction",
          "carbon_fraction", "ice_fraction", "fraction_sum",
          "pgm_enrichment", "notes"]


def write(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(header)
        w.writerows(rows)
    return path


def taxonomy_rows():
    for name, e in TAXONOMY_COMPOSITION.items():
        fracs = [e.get(k) for k in ("metal_fraction", "silicate_fraction",
                                    "carbon_fraction", "ice_fraction")]
        total = "" if all(f is None for f in fracs) \
            else round(sum(float(f or 0.0) for f in fracs), 6)
        yield [name, e.get("group", ""), e.get("composition", ""),
               "; ".join(e.get("minerals", []) or []),
               e.get("density_est_gcm3", ""),
               *[("" if f is None else f) for f in fracs],
               total, pgm_enrichment_for_type(name), e.get("notes", "")]


FILES = ("taxonomy_composition.csv", "pgm_enrichment.csv")


def export(ref_dir):
    """Write both files into `ref_dir`; return their paths, in FILES order."""
    os.makedirs(ref_dir, exist_ok=True)
    a = write(os.path.join(ref_dir, FILES[0]), FIELDS, taxonomy_rows())
    b = write(os.path.join(ref_dir, FILES[1]), ["spectral_type", "pgm_enrichment"],
              sorted(PGM_ENRICHMENT_BY_TYPE.items()))
    return a, b


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    a, b = export(os.path.join(here, "reference"))
    print("  %s  (%d classes)" % (os.path.basename(a), len(TAXONOMY_COMPOSITION)))
    print("  %s  (%d explicit, everything else 1.0 by fallback)"
          % (os.path.basename(b), len(PGM_ENRICHMENT_BY_TYPE)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
