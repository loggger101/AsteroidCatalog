# -*- coding: utf-8 -*-
"""asteroid_catalog: one merged, provenance-tagged table of the known asteroids.

Four public surveys, cross-matched on a canonical designation, validated, and
enriched with a composition estimate per taxonomy class:

    NASA JPL SBDB        the orbital backbone and the authority on identity:
                         elements, H, designations, and what physical
                         properties JPL carries.  ~1.57 M bodies
    IMCCE SsODNet ssoBFT best-of-literature diameter, albedo, mass, density,
                         rotation and taxonomy, cross-matched from ~3,000
                         published catalogs.  ~1.56 M rows
    NEOWISE V2.0         thermal-IR diameters and albedos.  183 k fits of
                         143 k bodies, repeat fits combined
    MP3C                 best diameter, albedo, mass and H, plus collisional
                         family and proper elements.  ~1.34 M bodies

Every supplement row is re-keyed onto JPL's designation before the join, so a
body two sources spell differently becomes one row carrying both sources'
data.  Each measured quantity says which source supplied it, how many sources
report it, and whether they agree.

Plus two things the surveys do not give you:

    a DIAMETER for the ~91% of bodies nobody measured one for, from H and an
    estimated albedo, tagged so you can always filter back to measured-only
    a COMPOSITION estimate per Bus-DeMeo class: bulk density and four mass
    fractions, from a cited per-class table

Quick start:

    >>> import asteroid_catalog as ac
    >>> ac.set_verbose(True)               # progress output; off by default
    >>> df = ac.build_catalog()            # fetches, merges, writes CSV
    >>> ac.lookup_asteroid(df, "Bennu")

    >>> ac.TAXONOMY_COMPOSITION["M"]["metal_fraction"]
    >>> ac.pgm_enrichment_for_type("V")    # 0.2; basaltic crust, PGM-depleted

WHAT THIS PACKAGE PROMISES, AND WHAT IT DOES NOT.  It promises provenance:
every measured quantity names the source it came from (`<stem>_provider`),
every estimate says how it was made (`diameter_source`,
`spectral_type_source`, `density_measured`), and nothing is silently imputed.  It does not promise that a
run today reproduces a run yesterday -- JPL adds bodies daily, so the catalog
is a different length every time, and a result measured against one build must
name the build it used.  `catalog_date` and `pipeline_version` are stamped into
every row for exactly that reason.

A SOURCE THAT FAILS IS TOLERATED, NOT HIDDEN.  An unreachable survey degrades
the catalog rather than failing the build.  (MP3C was documented as "regularly
unreachable" for releases; it was reachable, at an address the fetcher did not
use.  A tolerated failure hides a wrong address as well as it hides an
outage.)  But a source that fetched rows and matched NONE of them to the
backbone is always a bug in that fetcher, never an empty upstream table, and
`merge_sources` says so on stdout whether or not you asked for progress
output (see `_log.warn`).  Read the per-source match counts, not the fetch
counts.

THE COMPOSITION FRACTIONS DO NOT SUM TO 1 AND MUST NOT BE MADE TO.  Every real
taxonomy class sums to strictly less than one; the residual is the part the
literature does not resolve, and a consumer is expected to floor it at a
bulk-silicate value rather than to normalise it away.

PROVENANCE.  Extracted from Module 1 of `economicspace`, the asteroid-mining
profitability pipeline, at pipeline_version 1.2.0 (commit 1ce0dba).  Nothing
was re-typed: the package was built by slicing source line ranges, 2,953 of
that module's 3,338 lines, so the derivation chain here is the one fourteen
releases of measurement were taken against.  economicspace consumes the
catalog releases this package publishes as its Stage 1; it installs a pinned
`data-*` release and imports nothing from here.

The tables and the fetchers are split out because nothing in their schema knows
what a mine is.  A merged asteroid catalog with honest provenance is useful to
anyone doing population statistics, survey planning or target selection, and
the mining-specific layer is one clearly-labelled column.
"""

# Set before the submodules load, so any of them can import it at the top.
# The one place the package version is written; pyproject.toml reads it here.
__version__ = "0.6.0"

from ._log import say, warn, set_verbose, is_verbose

from .config import CatalogConfig, CONFIG

from .taxonomy import (
    TAXONOMY_COMPOSITION,
    PGM_ENRICHMENT_BY_TYPE,
    pgm_enrichment_for_type,
)

# Private, but reached as `ac._extract_canonical_designation` by the trap tests.
from .designations import _extract_canonical_designation  # noqa: F401

from .jpl import fetch_jpl_sbdb, JPL_SBDB_URL
from .mp3c import fetch_mp3c
from .ssodnet import fetch_ssodnet
from .neowise import fetch_neowise

from .merge import merge_sources, deduplicate_catalog
from .derive import (
    derive_missing_diameters,
    ALBEDO_FALLBACK,
    ALBEDO_BY_SPECTRAL_TYPE,
    ALBEDO_BY_SEMI_MAJOR_AXIS_AU,
    ALBEDO_BY_SEMI_MAJOR_AXIS_AU_NEO,
    ALBEDO_BEYOND_JUPITER_BY_H,
)
from .validate import validate_and_filter
from .enrich import enrich_composition
from .build import build_catalog
from .query import lookup_asteroid, filter_by_region, filter_by_spectral_group

#: The DATA contract, stamped into every output row and written into each
#: release's manifest, which is where a consumer checks it.  See config.py for
#: why this is not the same number as `__version__`.
DATA_VERSION = CONFIG.pipeline_version


__all__ = [
    # configuration
    "CatalogConfig", "CONFIG", "DATA_VERSION", "__version__",
    # output control
    "set_verbose", "is_verbose", "say", "warn",
    # reference data
    "TAXONOMY_COMPOSITION", "PGM_ENRICHMENT_BY_TYPE", "pgm_enrichment_for_type",
    "ALBEDO_FALLBACK", "ALBEDO_BY_SPECTRAL_TYPE", "ALBEDO_BY_SEMI_MAJOR_AXIS_AU",
    "ALBEDO_BY_SEMI_MAJOR_AXIS_AU_NEO", "ALBEDO_BEYOND_JUPITER_BY_H",
    # sources
    "fetch_jpl_sbdb", "fetch_ssodnet", "fetch_neowise", "fetch_mp3c",
    "JPL_SBDB_URL",
    # the chain
    "merge_sources", "deduplicate_catalog", "derive_missing_diameters",
    "validate_and_filter", "enrich_composition", "build_catalog",
    # reading a built catalog
    "lookup_asteroid", "filter_by_region", "filter_by_spectral_group",
]
