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
from asteroid_catalog.mineralogy import (        # noqa: E402
    GROUP_FIELDS, PHASE_DETAIL, PHASE_GROUP, detailed_fractions, phase_fractions,
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


def phase_rows():
    """One row per (class, phase): the body fraction, and its share of the group.

    The share is recomputed from the fraction, so the file shows both the
    number a consumer uses and the number the table was typed as.
    """
    for name, e in TAXONOMY_COMPOSITION.items():
        fracs = phase_fractions(name)
        if not fracs:
            continue
        for phase, frac in fracs.items():
            group = PHASE_GROUP[phase]
            coarse = e.get(GROUP_FIELDS[group]) if group in GROUP_FIELDS else None
            share = "" if not coarse else round(frac / coarse, 6)
            yield [name, phase, group, round(frac, 6), share]


def detailed_rows():
    """One row per (class, detailed phase), with the `comp_phases` entry it
    refines: the parent itself for a phase that passes through, and blank
    for an accessory new at 1.8.0."""
    for name in TAXONOMY_COMPOSITION:
        fracs = detailed_fractions(name)
        if not fracs:
            continue
        parents = {}
        split = PHASE_DETAIL.get(name, {})
        for parent in phase_fractions(name):
            for finer in split.get(parent, {parent: 1.0}):
                parents.setdefault(finer, parent)
        for phase, frac in fracs.items():
            yield [name, phase, PHASE_GROUP[phase], parents.get(phase, ""),
                   round(frac, 6)]


FILES = ("taxonomy_composition.csv", "pgm_enrichment.csv", "mineral_phases.csv",
         "mineral_phases_detailed.csv")


def export(ref_dir):
    """Write every file into `ref_dir`; return their paths, in FILES order."""
    os.makedirs(ref_dir, exist_ok=True)
    a = write(os.path.join(ref_dir, FILES[0]), FIELDS, taxonomy_rows())
    b = write(os.path.join(ref_dir, FILES[1]), ["spectral_type", "pgm_enrichment"],
              sorted(PGM_ENRICHMENT_BY_TYPE.items()))
    c = write(os.path.join(ref_dir, FILES[2]),
              ["spectral_type", "phase", "group", "fraction_of_body",
               "share_of_group"], phase_rows())
    d = write(os.path.join(ref_dir, FILES[3]),
              ["spectral_type", "phase", "group", "refines",
               "fraction_of_body"], detailed_rows())
    return a, b, c, d


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    a, b, c, d = export(os.path.join(here, "reference"))
    print("  %s  (%d classes)" % (os.path.basename(a), len(TAXONOMY_COMPOSITION)))
    print("  %s  (%d explicit, everything else 1.0 by fallback)"
          % (os.path.basename(b), len(PGM_ENRICHMENT_BY_TYPE)))
    print("  %s  (one row per class and phase)" % os.path.basename(c))
    print("  %s  (1.8.0: one row per class and detailed phase)"
          % os.path.basename(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
