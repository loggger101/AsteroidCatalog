# -*- coding: utf-8 -*-
"""Command line: build a catalog, or look one up.

    asteroid-catalog build --out ./data
    asteroid-catalog build --jpl-limit 5000 --no-ssodnet
    asteroid-catalog lookup Bennu --catalog ./data/asteroid_catalog.csv
    asteroid-catalog taxonomy M

`build` is verbose by default and the library is not, which is the right way
round: somebody who typed a command wants to watch a 500 MB download, and
somebody who imported the package for one taxonomy row does not.
"""

import argparse
import os
import sys

from . import __version__
from ._log import set_verbose
from .config import CatalogConfig, CONFIG
from .taxonomy import TAXONOMY_COMPOSITION, pgm_enrichment_for_type


def _overwrite_ok(paths, what: str, assume_yes: bool) -> bool:
    """True when it is safe to overwrite `paths`; ask the user if it is not.

    A BUILD RE-FETCHES AND OVERWRITES, AND THERE IS NO UNDO.  JPL adds bodies
    daily, so the catalog this replaces cannot be fetched again: any result
    measured against it stops reproducing, and that looks exactly like a code
    regression rather than like a lost input.

    Refuses on EOF rather than hanging, because stdin may be a scheduled task's
    dead handle -- a prompt that waits forever is a worse failure than one that
    exits.
    """
    existing = [p for p in paths if os.path.exists(p)]
    if not existing or assume_yes:
        return True
    print("")
    print("  " + "=" * 71)
    print("  THIS RE-FETCHES LIVE DATA AND OVERWRITES WHAT IS ON DISK")
    print("  " + "=" * 71)
    print("  %s" % what)
    for p in existing[:8]:
        print("    %s" % p)
    if len(existing) > 8:
        print("    ... and %d more" % (len(existing) - 8))
    print("")
    print("  JPL adds bodies daily, so the file being replaced cannot be")
    print("  re-fetched.  Any measurement taken against it stops reproducing.")
    print("")
    try:
        return input("  Type 'yes' to overwrite: ").strip().lower() == "yes"
    except (EOFError, KeyboardInterrupt):
        print("")
        print("  No console to confirm on (stdin is not a terminal).")
        print("  Pass --yes if overwriting it is what you meant.")
        return False


def _build(args) -> int:
    from .build import build_catalog

    config = CatalogConfig()
    if args.out:
        config.output_dir = args.out
    for name in ("jpl", "ssodnet", "neowise", "mp3c"):
        if getattr(args, "no_" + name, False):
            setattr(config, "use_" + name, False)
        limit = getattr(args, name + "_limit", None)
        if limit is not None:
            setattr(config, name + "_limit", limit)
    if args.cache_dir:
        config.cache_dir = args.cache_dir

    os.makedirs(config.output_dir, exist_ok=True)
    targets = [os.path.join(config.output_dir, config.catalog_filename),
               os.path.join(config.output_dir, config.rejected_filename)]
    if not _overwrite_ok(targets, "A catalog build writes:", args.yes):
        print("  Cancelled; nothing was fetched and nothing was written.")
        return 1

    set_verbose(not args.quiet)
    df = build_catalog(config)
    if df.empty:
        print("FAIL  the build produced no rows", file=sys.stderr)
        return 1
    print("%d rows -> %s" % (len(df), targets[0]))
    return 0


def _lookup(args) -> int:
    import pandas as pd

    from .query import lookup_asteroid

    path = args.catalog or os.path.join(CONFIG.output_dir,
                                        CONFIG.catalog_filename)
    if not os.path.exists(path):
        print("no catalog at %s; run `asteroid-catalog build` first" % path,
              file=sys.stderr)
        return 2
    # `designation` MUST be read as a string.  A numbered asteroid's
    # designation looks like an integer, so a slice in which every row happens
    # to be numbered infers int64 and every string comparison against it
    # matches nothing.
    df = pd.read_csv(path, low_memory=False, dtype={"designation": str})
    hit = lookup_asteroid(df, args.query)
    if hit.empty:
        print("no match for %r in %d rows" % (args.query, len(df)))
        return 1
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(hit.to_string(index=False))
    return 0


def _taxonomy(args) -> int:
    if args.klass:
        row = TAXONOMY_COMPOSITION.get(args.klass)
        if row is None:
            print("unknown class %r; %d known"
                  % (args.klass, len(TAXONOMY_COMPOSITION)), file=sys.stderr)
            return 1
        for k, v in row.items():
            print("  %-20s %s" % (k, v))
        print("  %-20s %s" % ("pgm_enrichment", pgm_enrichment_for_type(args.klass)))
        return 0
    for name in sorted(TAXONOMY_COMPOSITION):
        row = TAXONOMY_COMPOSITION[name]
        print("  %-8s %-14s %s" % (name, row.get("group", ""),
                                   row.get("composition", "")))
    return 0


def _make_stdout_capable() -> None:
    """Let this program print DATA, not just its own ASCII literals.

    THE LIBRARY'S PRINTED LITERALS ARE ASCII AND THAT IS NOT ENOUGH HERE.
    Windows picks cp1252 for a redirected stdout, and the taxonomy `notes`
    fields carry real Unicode -- "~3.8-3.9 g/cm3" is written with U+2248 -- so
    `asteroid-catalog taxonomy M` died with a UnicodeEncodeError on a console
    that had no trouble with any message this package composes itself.

    The rule the package keeps is about literals, because `say()` has to be
    safe under any encoding.  A command that prints table CONTENT is the case
    that rule does not reach, so the stream is made capable instead.
    `errors="replace"` is the backstop: a mangled character is a worse outcome
    than a clean one and a far better outcome than a traceback.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _make_stdout_capable()
    p = argparse.ArgumentParser(
        prog="asteroid-catalog",
        description="Build and query a merged, provenance-tagged asteroid catalog.")
    p.add_argument("--version", action="version",
                   version="asteroid_catalog %s (data contract %s)"
                           % (__version__, CONFIG.pipeline_version))
    sub = p.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="fetch every source and write the catalog")
    b.add_argument("--out", help="output directory")
    b.add_argument("--cache-dir", help="where the ~500 MB SsODNet parquet is cached")
    b.add_argument("--quiet", action="store_true", help="suppress progress output")
    b.add_argument("--yes", action="store_true",
                   help="overwrite an existing catalog without asking")
    for name in ("jpl", "ssodnet", "neowise", "mp3c"):
        b.add_argument("--no-" + name, action="store_true",
                       help="skip the %s source" % name.upper())
        b.add_argument("--%s-limit" % name, type=int, metavar="N",
                       help="cap %s at N rows (0 = no cap)" % name.upper())
    b.set_defaults(func=_build)

    l = sub.add_parser("lookup", help="find a body in a built catalog")
    l.add_argument("query", help="designation, number or name")
    l.add_argument("--catalog", help="path to asteroid_catalog.csv")
    l.set_defaults(func=_lookup)

    t = sub.add_parser("taxonomy", help="show the composition table")
    t.add_argument("klass", nargs="?", help="a Bus-DeMeo class, e.g. M or Cgh")
    t.set_defaults(func=_taxonomy)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
