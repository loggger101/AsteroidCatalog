# -*- coding: utf-8 -*-
"""Configuration for a catalog build.

Sliced from `CatalogConfig` in economicspace `modules/catalog.py`,
pipeline_version 1.2.0.  The per-field comments are the original text: they
are the documentation for every dial, and the dashboard in that project
scrapes them as its help strings, so they are kept verbatim rather than
re-worded.

FOUR THINGS CHANGED ON THE WAY OUT OF THAT REPO, AND NOTHING ELSE:

  * the output directory defaults to `./asteroid_catalog_data` and reads
    `ASTEROID_CATALOG_OUTPUT_DIR`, where the original defaulted into
    `./asteroid_pipeline` and read `ASTEROID_PIPELINE_OUTPUT_DIR`,
  * the module no longer creates the output directory at import time, because
    a library that makes a folder when you import it for one constant is a
    library with a side effect,
  * the module no longer eagerly creates the download cache directory either,
    for the same reason; `_resolve_cache_dir` still creates it when something
    actually asks where the cache is,
  * the module no longer prints its configuration at import time.  The banner
    is not lost -- `say()` prints it when the caller asks for verbose output,
    and the CLI asks.

TWO VERSION NUMBERS LIVE HERE AND THEY MEAN DIFFERENT THINGS.  Do not
conflate them:

    `pipeline_version`        the DATA contract.  It is stamped into every
                              output CSV and is the only way to tell which
                              code produced a given catalog.  It moves when a
                              change moves any number a run produces, and that
                              rule is ONE-DIRECTIONAL: moving it is not
                              evidence that a number changed.
    `asteroid_catalog.__version__`
                              the PACKAGE release.  It moves for a loader fix,
                              a new helper or a docs pass -- changes that alter
                              no row and no output byte.

A package release can leave `pipeline_version` alone.  See CHANGELOG.md.
"""

import os
import sys

from dataclasses import dataclass


# The launcher to name in a printed instruction.  `py` is the Windows launcher
# and exists nowhere else, so a hint that says it is wrong advice on the host
# that most needs the hint.
_PY = "py" if os.name == "nt" else os.path.basename(sys.executable)


def _default_output_dir() -> str:
    """Where a build writes, unless the caller says otherwise.

    `ASTEROID_CATALOG_OUTPUT_DIR` wins when set.  Otherwise
    `./asteroid_catalog_data` under the current working directory -- relative,
    deliberately, because an absolute default is wrong on every machine but
    the author's.  The original's Colab detection went with the pipeline: a
    library has no business guessing it is in a notebook.
    """
    env = os.environ.get("ASTEROID_CATALOG_OUTPUT_DIR")
    if env:
        return env
    return os.path.join(os.getcwd(), "asteroid_catalog_data")


_DEFAULT_OUTPUT_DIR = _default_output_dir()




# ═════════════════════════════════════════════════════════════════════════════
# ║                                                                           ║
# ║   ★  USER SETTINGS, EDIT THESE TO TUNE THE PIPELINE  ★                  ║
# ║                                                                           ║
# ║   Every knob the casual user is expected to touch lives in this single    ║
# ║   dataclass.  Each field has a brief note describing what it controls,    ║
# ║   the default value, and (where relevant) the range / common values.      ║
# ║                                                                           ║
# ║   Nothing below this block needs editing for normal use.                  ║
# ║                                                                           ║
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class CatalogConfig:
    """User-editable pipeline configuration.  See per-field comments below."""

    # ─── SOURCE TOGGLES ───────────────────────────────────────────────────────
    # Set any of these to False to skip that source.  An unreachable or empty
    # source is silently tolerated by the pipeline; you don't need to flip the
    # toggle just because a host is down.
    use_jpl:      bool = True   # NASA JPL Small-Body Database     (orbital + physical)
    use_mp3c:     bool = True   # MP3C @ Observatoire Côte d'Azur   (physical compilation)
    use_ssodnet:  bool = True   # SsODNet ssoBFT (IMCCE)            (mass, density, taxonomy, …)
    use_neowise:  bool = True   # NEOWISE V2.0 via IRSA TAP         (IR diameters + albedos)
    # To add a new catalog: write a fetch_<name>(config) function and add a
    # matching `use_<name>: bool = True` line here.

    # ─── FETCH LIMITS & NETWORK ──────────────────────────────────────────────
    # ONE CAP PER SOURCE, and 0 means "no cap, take the whole table".
    #
    # Until v1.1.0 `jpl_limit` was reused as the row cap for every source, which
    # quietly made the catalog SMALLER than any single source.  Each fetcher
    # takes its first N rows ordered by asteroid number, so four sources capped
    # at the same N return substantially the SAME N bodies; the merge then
    # collapses them and the union is ~N rather than 4N.  Raising the shared cap
    # to reach further down one source dragged every other source along with it.
    #
    # Measured 2026-08-08 against the live APIs, which is what the defaults are
    # sized from:
    #     JPL SBDB      1,554,321 asteroids   (139,582 with a measured diameter)
    #     SsODNet        ~1,200,000 rows      (~500 MB parquet, cached)
    #     NEOWISE V2.0     183,412 rows       (143,318 unique bodies w/ diameter)
    #     MP3C           varies; frequently unreachable
    #
    # 0 (unlimited) is the default because JPL is the only source of orbital
    # elements, so a body it does not return cannot be evaluated no matter what
    # the other sources know about it.  The full JPL pull is ~435 MB / ~80 s on
    # a warm connection; NEOWISE unlimited is ~19 MB / ~30 s.  Set a cap if you
    # want a fast interactive run: 50_000 reproduces the pre-v1.1.0 behaviour.
    jpl_limit:       int = 0   # 0 = all 1.55 M asteroids (orbital elements)
    ssodnet_limit:   int = 0   # 0 = whole cached ssoBFT table
    neowise_limit:   int = 0   # 0 = all 183 k NEOWISE rows

    # Ask IRSA for the NEOWISE table as an asynchronous (IVOA UWS) job rather
    # than a single synchronous request.  A sync query holds one connection
    # open for the server-side query AND the ~19 MB transfer, so a proxy
    # timeout anywhere in that window discards the whole result with nothing to
    # retry; that is the 502 that made NEOWISE contribute 0 rows to the run
    # behind the committed cislunar 2x2.  Async runs the job server-side and
    # leaves the result at a stable, re-fetchable URL.  Falls back to the
    # synchronous path on any failure, so turning this off only removes a way
    # to succeed.  Same ADQL and same rows either way, verified byte-identical.
    neowise_use_async: bool = True

    # How long to poll an async NEOWISE job before giving up and falling back.
    # The full table completes in well under a minute; this is a ceiling for a
    # service under load, not an expected wait.
    neowise_async_max_wait_s: int = 900
    mp3c_limit:      int = 0   # 0 = whatever MP3C will serve
    request_timeout: int = 300 # seconds per HTTP request before giving up (5 min)

    # ─── QUALITY GATES  (enforced in validate_and_filter) ────────────────────
    # `min_diameter_km` drops anything below this size.  Default 0.001 km =
    # 1 metre (essentially "keep everything that has a positive diameter").
    # Bump to e.g. 1.0 to focus on >=1-km bodies.
    min_diameter_km: float = 0.001

    # If True, asteroids with no spectral classification (Bus / Tholen) are
    # rejected.  Useful for compositional studies; False keeps more rows.
    require_spectral_type: bool = False

    # ─── DERIVED DIAMETERS  (v1.1.0) ─────────────────────────────────────────
    # validate_and_filter drops any body without a diameter, and only 139,582
    # of JPL's 1,554,321 asteroids have one measured.  1,553,812 have an
    # absolute magnitude H and a valid orbit, and diameter follows from H and
    # the geometric albedo exactly:
    #
    #     D_km = (1329 / sqrt(p_V)) * 10**(-H/5)          (Fowler & Chillemi 1992)
    #
    # so the ONLY thing being estimated is p_V.  With this on, the evaluable
    # population goes from ~139 k to ~1.55 M, an 11x larger catalog whose extra
    # rows carry a diameter uncertain by roughly the square root of the albedo
    # error, and a MASS uncertain by that cubed.  Every such row is tagged
    # `diameter_source = "derived_h_*"`; a measured diameter always wins, and
    # `derived_diameter_is_estimate` gives downstream code a single boolean to
    # filter on.  Turn this off for a measured-only catalog.
    derive_diameter_from_h: bool = True

    # Floor on DERIVED diameters only (km).  Measured diameters are governed by
    # `min_diameter_km` above and are never subject to this.  0.0 keeps every
    # derived body; raise it to trim the sub-kilometre tail, which is most of
    # the 1.4 M and is where the albedo assumption hurts most.
    min_derived_diameter_km: float = 0.0

    # ─── OUTPUT  (where the CSVs land) ───────────────────────────────────────
    # `output_dir` is created at startup if it doesn't exist.  On Colab the
    # default '/content/...' lives in the session sandbox, change to a Drive
    # path like '/content/drive/MyDrive/asteroids' to persist between runs.
    output_dir:        str = _DEFAULT_OUTPUT_DIR
    catalog_filename:  str = "asteroid_catalog.csv"
    rejected_filename: str = "rejected_entries.csv"

    # ─── BULK-DOWNLOAD CACHE  (SsODNet parquet & similar) ────────────────────
    # SsODNet's ssoBFT is ~500 MB.  We cache it once per `cache_max_age_days`
    # and re-use it between runs.  Bump max_age down to force a fresh pull.
    #
    # `cache_dir` controls WHERE the cache lives:
    #   • Empty string (default) → system tmp directory (good for Drive users:
    #                              the ~500 MB parquet does NOT round-trip
    #                              through Drive sync on every run).
    #   • Any absolute path      → that exact directory.
    # If you want the cache co-located with the catalog CSV instead, set this
    # to e.g. f"{output_dir}/_cache".
    cache_dir:           str   = ""

    # How long the ssoBFT parquet cache is reused before it is re-downloaded.
    # That download is ~500 MB, so raise this for repeated offline runs.
    cache_max_age_days:  float = 7.0

    # ─── PREVIEW & SUMMARY DISPLAY  (cosmetic, affects stdout only) ──────────
    preview_rows:           int = 10   # rows shown in CATALOG PREVIEW table
    top_n_spectral_types:   int = 20   # types listed in spectral-distribution bars

    # ─── PIPELINE VERSION  (bump when changing the schema) ───────────────────
    # Stamped into every output CSV, and the only way to tell which code
    # produced a given catalog.  BUMP IT when a change moves any number a run
    # produces.  The rule is ONE-DIRECTIONAL: changing a number means bumping,
    # and a bump does NOT mean a number changed, which is why nothing may read
    # a version as evidence that a result moved.
    # THE CHANGELOG IS versions.md, NOT THIS COMMENT.  It used to be 155 lines
    # of release notes sitting right here, a second copy of a record versions.md
    # already held, which is the documentation form of the defect this project
    # keeps cataloguing; it was also what the dashboard rendered as this field's
    # help text, because ui_meta scrapes a field's comment block.  Moved out on
    # 2026-09-02.  Two places to write, neither of them here:
    #     versions.md > Releases            what the release did, and what it
    #                                       measured to say so
    #     versions.md > Module changelogs   this module's own stamp-by-stamp
    #                                       record: Stage 1 changelog
    pipeline_version: str = "1.2.0"

# Instantiate.  Edit the field defaults above (inside the dataclass); DO NOT
# mutate CONFIG fields here, which defeats having one editable source of truth.
#
# NOTHING IS CREATED ON DISK BY THIS LINE.  The original made the output
# directory here and the cache directory four lines later, which is right for a
# pipeline stage that is about to write to both and wrong for a library
# imported to read one taxonomy row.
CONFIG = CatalogConfig()


def _resolve_cache_dir(config: "CatalogConfig") -> str:
    """
    Return the absolute path of the bulk-download cache.

    If `config.cache_dir` is non-empty, use it verbatim.  Otherwise default to
    a stable per-user location under the system tmp dir; this avoids the 526
    MB SsODNet parquet syncing through Google Drive on every refresh.
    """
    if config.cache_dir:
        path = config.cache_dir
    else:
        import tempfile
        path = os.path.join(tempfile.gettempdir(), "asteroid_pipeline_cache")
    os.makedirs(path, exist_ok=True)
    return path


# ⚠️  `_fmt_limit` AND `_resolve_cache_dir` ARE CONSUMED ACROSS A REPOSITORY
# BOUNDARY.  Nothing in this package calls either, so a dead-code sweep run
# here will flag them; economicspace's Stage 1 adapter reaches both as
# `asteroid_catalog.config.<name>`, rather than keeping its own copies.
# `tests/test_consumer_contract.py` is what stops the deletion.
def _fmt_limit(n: int) -> str:
    """Render a row cap for the banner; 0 is unlimited, not zero rows."""
    return "unlimited" if not n else f"{n:,}"
