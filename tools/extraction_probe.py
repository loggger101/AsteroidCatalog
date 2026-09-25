# -*- coding: utf-8 -*-
"""Does the package compute what the module computed?

⚠️  THIS PROBES THE 0.1.x EXTRACTION, NOT TODAY'S CODE.  From 0.4.0 (data
contract 1.4.0) the package deliberately differs from the pre-split module:
the albedo tables, the merge's physical screens, the density/mass
reconciliation and the class Z are all new.  Run against 0.4.0 or later, it
reports those differences, and they are intended; check out v0.3.0 to re-run
the extraction proof as it was.

STAGE 1 CANNOT BE RE-RUN TO ANSWER THIS.  JPL adds bodies daily, so a rebuilt
catalog is a different length and comparable with nothing already measured, and
the file it would overwrite is the 862 MB input every other stage reads.  So
the question is answered the way catalog 1.1.1 answered it: in-process, against
the catalog already on disk, plus synthetic frames for the pure functions.

THREE LEVELS, AND THE WEAKEST IS NOT GOOD ENOUGH ON ITS OWN.

  1. REFERENCE DATA, leaf by leaf, at full repr AND raw IEEE bit pattern, with
     key ORDER compared too -- a reordered dict moves a CSV column order
     without moving a number, and a float probe alone would pass it.
  2. PURE FUNCTIONS, run both ways over a stride sample of the real catalog and
     over synthetic frames built for the documented traps, compared cell by
     cell on raw bit patterns rather than with a tolerance.
  3. THE FETCHERS, which cannot be run without fetching, compared as SOURCE
     TEXT against the original's line range.  That is weaker than running them
     and it is the honest thing to check: what it proves is that the bytes did
     not change in transit, which is the only claim being made about them.
"""

import ast
import importlib.util
import io
import os
import struct
import sys

import pandas as pd

ECON = os.environ.get(
    "ECONOMICSPACE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "economicspace"))
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# THE PRE-SPLIT MODULE, WHICH IS NOT IN EITHER REPOSITORY ANY MORE.
# economicspace `modules/catalog.py` is the adapter now, so re-running this
# needs the 3,338-line original, recovered from that repo's history:
#
#     git -C economicspace show <the commit before the split>:modules/catalog.py \
#         > catalog_orig.py
#     ORIG_MODULE=catalog_orig.py py tools/extraction_probe.py
#
# Kept rather than deleted because the method is the point: a split argued from
# "I was careful" is worth nothing, and this is the thing that made it a
# measurement.
ORIG_MODULE = os.environ.get("ORIG_MODULE",
                             os.path.join(os.getcwd(), "catalog_orig.py"))

sys.path.insert(0, PKG)


def load_original():
    spec = importlib.util.spec_from_file_location(
        "_orig_catalog", ORIG_MODULE)
    mod = importlib.util.module_from_spec(spec)
    buf = io.StringIO()
    keep, sys.stdout = sys.stdout, buf
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.stdout = keep
    return mod


def bits(x):
    """A value's identity for comparison: type, repr, and for a float its
    exact 64-bit pattern.  `repr` alone conflates 1 and 1.0; a float compare
    alone conflates -0.0 with 0.0 and passes NaN != NaN as a difference."""
    if isinstance(x, float):
        return ("float", struct.pack(">d", x).hex())
    if isinstance(x, bool):
        return ("bool", x)
    if isinstance(x, int):
        return ("int", x)
    if x is None:
        return ("none",)
    if isinstance(x, str):
        return ("str", x)
    if isinstance(x, (list, tuple)):
        return (type(x).__name__, tuple(bits(v) for v in x))
    if isinstance(x, dict):
        # KEY ORDER IS PART OF THE VALUE.  It becomes a column order downstream.
        return ("dict", tuple((k, bits(v)) for k, v in x.items()))
    return (type(x).__name__, repr(x))


def leaves(x, path="", out=None):
    out = [] if out is None else out
    if isinstance(x, dict):
        for k, v in x.items():
            leaves(v, "%s[%r]" % (path, k), out)
    elif isinstance(x, (list, tuple)):
        for i, v in enumerate(x):
            leaves(v, "%s[%d]" % (path, i), out)
    else:
        out.append((path, bits(x)))
    return out


def frame_bits(df):
    """Every cell of a frame, as a comparable token.  Column ORDER included."""
    out = [("__columns__", tuple(map(str, df.columns)))]
    for col in df.columns:
        s = df[col]
        out.append(("%s.__dtype__" % col, str(s.dtype)))
        for i, v in enumerate(s.tolist()):
            if isinstance(v, float) and v != v:
                out.append(("%s[%d]" % (col, i), ("nan",)))
            else:
                out.append(("%s[%d]" % (col, i), bits(v)))
    return out


def compare(label, a, b, results):
    diffs = []
    if len(a) != len(b):
        diffs.append("length %d vs %d" % (len(a), len(b)))
    for (pa, va), (pb, vb) in zip(a, b):
        if pa != pb:
            diffs.append("path %s vs %s" % (pa, pb))
        elif va != vb:
            diffs.append("%s: %r vs %r" % (pa, va, vb))
    results.append((label, len(a), diffs))
    return diffs


OUTPUT_CALLS = ("print", "say", "warn")


def normalise_calls(text):
    """Rewrite every output call to one name, so both sides are comparable.

    The extraction turns `print` into `say`, or into `warn` for the ten
    messages a silent run must not swallow.  Normalising all three to a single
    token means the comparison asks the right question -- "is anything ELSE
    different?" -- instead of re-deriving the transform and then checking its
    own arithmetic.

    THIS MUST NOT BE A STRING REPLACE.  `fetch_ssodnet` prints a hint whose
    TEXT contains "print(" -- a command the reader is meant to type -- and a
    naive replace rewrites that advice into a call to a function they do not
    have.  Caught by this probe reporting a difference that was its own.
    """
    tree = ast.parse(text)
    hits = [(n.func.lineno, n.func.col_offset, len(n.func.id))
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in OUTPUT_CALLS]
    lines = text.splitlines()
    # Right to left, so an earlier column on the same line is still valid
    # after a replacement of a different length lands to its right.
    for lineno, col, width in sorted(hits, reverse=True):
        ln = lines[lineno - 1]
        lines[lineno - 1] = ln[:col] + "print" + ln[col + width:]
    return chr(10).join(lines)


def main():
    orig = load_original()
    import asteroid_catalog as new

    results = []

    # --- 1. reference data -------------------------------------------------
    for name in ("TAXONOMY_COMPOSITION", "PGM_ENRICHMENT_BY_TYPE",
                 "ALBEDO_BY_SPECTRAL_TYPE", "ALBEDO_BY_SEMI_MAJOR_AXIS_AU"):
        compare("data:" + name,
                leaves(getattr(orig, name)), leaves(getattr(new, name)), results)

    compare("data:scalars",
            leaves({"ALBEDO_FALLBACK": orig.ALBEDO_FALLBACK,
                    "_H_DIAMETER_CONSTANT": orig._H_DIAMETER_CONSTANT,
                    "JPL_SBDB_URL": orig.JPL_SBDB_URL}),
            leaves({"ALBEDO_FALLBACK": new.ALBEDO_FALLBACK,
                    "_H_DIAMETER_CONSTANT": new.derive._H_DIAMETER_CONSTANT,
                    "JPL_SBDB_URL": new.JPL_SBDB_URL}), results)

    # --- 2. config surface -------------------------------------------------
    import dataclasses
    of = {f.name: f.type for f in dataclasses.fields(orig.CatalogConfig)}
    nf = {f.name: f.type for f in dataclasses.fields(new.CatalogConfig)}
    diffs = []
    if set(of) != set(nf):
        diffs.append("fields differ: only-orig=%s only-pkg=%s"
                     % (sorted(set(of) - set(nf)), sorted(set(nf) - set(of))))
    # every default except the four documented adaptations
    ADAPTED = {"output_dir"}
    od = {f.name: f.default for f in dataclasses.fields(orig.CatalogConfig)}
    nd = {f.name: f.default for f in dataclasses.fields(new.CatalogConfig)}
    for k in sorted(set(of) & set(nf)):
        if k in ADAPTED:
            continue
        if bits(od[k]) != bits(nd[k]):
            diffs.append("default %s: %r vs %r" % (k, od[k], nd[k]))
    results.append(("config:surface", len(of), diffs))

    # --- 3. pure functions, synthetic ---------------------------------------
    desig = pd.Series(["2024 BX1", "433", "(1) Ceres", "1 Ceres", "2021 PH27",
                       "99942", "2014 YN", None, "", "A/2017 U1"])
    compare("fn:_extract_canonical_designation",
            frame_bits(pd.DataFrame({"d": orig._extract_canonical_designation(desig)})),
            frame_bits(pd.DataFrame({"d": new._extract_canonical_designation(desig)})),
            results)

    klasses = sorted(orig.TAXONOMY_COMPOSITION) + ["M", "V", "Xe", "nope", None]
    compare("fn:pgm_enrichment_for_type",
            [(str(k), bits(orig.pgm_enrichment_for_type(k))) for k in klasses],
            [(str(k), bits(new.pgm_enrichment_for_type(k))) for k in klasses],
            results)

    # --- 4. pure functions, over the real catalog ---------------------------
    cat = os.path.join(ECON, "asteroid_pipeline", "asteroid_catalog.csv")
    if os.path.exists(cat):
        # A stride sample, read with `designation` forced to str: a slice in
        # which every row is a numbered body infers int64 and then matches
        # nothing.
        df = pd.read_csv(cat, low_memory=False, dtype={"designation": str},
                         skiprows=lambda i: i % 4000 != 0 and i != 0)
        print("  catalog sample: %d rows x %d cols" % df.shape)

        src = df.drop(columns=[c for c in df.columns
                               if c.startswith("comp_") or c == "pgm_enrichment"],
                      errors="ignore")
        compare("fn:enrich_composition",
                frame_bits(orig.enrich_composition(src.copy())),
                frame_bits(new.enrich_composition(src.copy())), results)

        compare("fn:derive_missing_diameters",
                frame_bits(orig.derive_missing_diameters(df.copy(), orig.CONFIG)),
                frame_bits(new.derive_missing_diameters(df.copy(), new.CONFIG)),
                results)

        ov, orj = orig.validate_and_filter(df.copy(), orig.CONFIG)
        nv, nrj = new.validate_and_filter(df.copy(), new.CONFIG)
        compare("fn:validate_and_filter", frame_bits(ov), frame_bits(nv), results)
        compare("fn:validate_and_filter/rejected",
                frame_bits(orj), frame_bits(nrj), results)

        compare("fn:deduplicate_catalog",
                frame_bits(orig.deduplicate_catalog(df.copy(), key="designation",
                                                    label="probe")),
                frame_bits(new.deduplicate_catalog(df.copy(), key="designation",
                                                   label="probe")), results)

        compare("fn:merge_sources",
                frame_bits(orig.merge_sources({"A": df.copy(), "B": df.head(50).copy()})),
                frame_bits(new.merge_sources({"A": df.copy(), "B": df.head(50).copy()})),
                results)

        picks = [str(x) for x in df["designation"].dropna().head(3)]
        picks += [str(x) for x in df["name"].dropna().head(3)] if "name" in df else []
        picks += ["Ceres", "no-such-body-xyz"]
        print("  lookup probes: %s" % picks)
        for q in picks:
            compare("fn:lookup_asteroid(%s)" % q,
                    frame_bits(orig.lookup_asteroid(df, q)),
                    frame_bits(new.lookup_asteroid(df, q)), results)
        compare("fn:filter_by_region",
                frame_bits(orig.filter_by_region(df, 2.0, 3.3)),
                frame_bits(new.filter_by_region(df, 2.0, 3.3)), results)
        compare("fn:filter_by_spectral_group",
                frame_bits(orig.filter_by_spectral_group(df, "X-complex")),
                frame_bits(new.filter_by_spectral_group(df, "X-complex")), results)
    else:
        results.append(("catalog checks", 0, ["NO CATALOG ON DISK -- NOT RUN"]))

    # --- 5. the fetchers, as source text ------------------------------------
    osrc = io.open(ORIG_MODULE, encoding="utf-8").read()
    otree = ast.parse(osrc)
    ofn = {n.name: ast.get_source_segment(osrc, n) for n in otree.body
           if isinstance(n, ast.FunctionDef)}
    diffs = []
    checked = 0
    for modname in ("jpl", "mp3c", "ssodnet", "neowise", "merge", "derive",
                    "validate", "enrich", "query", "designations", "taxonomy"):
        path = os.path.join(PKG, "asteroid_catalog", modname + ".py")
        psrc = io.open(path, encoding="utf-8").read()
        ptree = ast.parse(psrc)
        for n in ptree.body:
            if not isinstance(n, ast.FunctionDef) or n.name not in ofn:
                continue
            checked += 1
            a = normalise_calls(ofn[n.name])
            b = normalise_calls(ast.get_source_segment(psrc, n))
            if a != b:
                diffs.append("%s.%s: source text differs" % (modname, n.name))
    results.append(("source:functions", checked, diffs))

    # --- report -------------------------------------------------------------
    print("")
    print("  %-38s %8s  %s" % ("check", "values", "result"))
    print("  " + "-" * 68)
    bad = 0
    for label, n, diffs in results:
        if diffs:
            bad += 1
            print("  %-38s %8d  *** %d DIFFER" % (label, n, len(diffs)))
            for d in diffs[:6]:
                print("        %s" % d)
        else:
            print("  %-38s %8d  identical" % (label, n))
    total = sum(n for _, n, _ in results)
    print("  " + "-" * 68)
    print("  %d checks, %d values, %d differing" % (len(results), total, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
