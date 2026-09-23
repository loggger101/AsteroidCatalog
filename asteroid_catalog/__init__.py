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
    fractions, from a cited 76-class table

Quick start:

    >>> import asteroid_catalog as ac
    >>> ac.set_verbose(True)               # progress output; off by default
    >>> df = ac.build_catalog()            # fetches, merges, writes CSV
    >>> ac.lookup_asteroid(df, "Bennu")

    >>> ac.TAXONOMY_COMPOSITION["M"]["metal_fraction"]
    >>> ac.pgm_enrichment_for_type("V")    # 0.2; basaltic crust, PGM-depleted

WHAT THIS PACKAGE PROMISES, AND WHAT IT DOES NOT.  It promises provenance:
every physical column is accompanied by a `*_source` column saying where the
value came from, and nothing is silently imputed.  It does not promise that a
run today reproduces a run yesterday -- JPL adds bodies daily, so the catalog
is a different length every time, and a result measured against one build must
name the build it used.  `catalog_date` and `pipeline_version` are stamped into
every row for exactly that reason.

A SOURCE THAT FAILS IS TOLERATED, NOT HIDDEN.  An unreachable survey degrades
the catalog rather than failing the build.  (MP3C was documented as "regularly
unreachable" for releases; it was reachable, at an address the fetcher did not
use.  A tolerated failure hides a wrong address as well as it hides an
outage.)  But a source that fetched rows and matched NONE of them
to the backbone is always a bug in that fetcher, never an empty upstream table,
and `merge_sources` says so on stderr whether or not you asked for progress
output.  Read the per-source match counts, not the fetch counts.

THE COMPOSITION FRACTIONS DO NOT SUM TO 1 AND MUST NOT BE MADE TO.  Every real
taxonomy class sums to strictly less than one; the residual is the part the
literature does not resolve, and a consumer is expected to floor it at a
bulk-silicate value rather than to normalise it away.

PROVENANCE.  Extracted from Module 1 of `economicspace`, the asteroid-mining
profitability pipeline, at pipeline_version 1.2.0 (commit 1ce0dba).  Nothing
was re-typed: the package was built by slicing source line ranges, 2,953 of
that module's 3,338 lines, so the derivation chain here is the one fourteen
releases of measurement were taken against.  economicspace consumes this
package as its Stage 1.

The tables and the fetchers are split out because nothing in their schema knows
what a mine is.  A merged asteroid catalog with honest provenance is useful to
anyone doing population statistics, survey planning or target selection, and
the mining-specific layer is one clearly-labelled column.
"""

import pandas as pd

from ._log import say, warn, set_verbose, is_verbose

from .config import CatalogConfig, CONFIG

from .taxonomy import (
    TAXONOMY_COMPOSITION,
    PGM_ENRICHMENT_BY_TYPE,
    pgm_enrichment_for_type,
)

from .designations import _extract_canonical_designation

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
)
from .validate import validate_and_filter
from .enrich import enrich_composition
from .build import build_catalog
from .query import lookup_asteroid, filter_by_region, filter_by_spectral_group

__version__ = "0.3.0"

#: The DATA contract, stamped into every output row.  Mirrored by the
#: economicspace adapter, which asserts the two are equal at import.  See
#: config.py for why this is not the same number as `__version__`.
DATA_VERSION = CONFIG.pipeline_version


# ---------------------------------------------------------------------------
# COLLISION-PROOF SECOND NAMES
# ---------------------------------------------------------------------------
# THESE ARE NOT CONVENIENCE ALIASES AND MUST NOT BE DELETED AS DUPLICATES.
#
# economicspace concatenates four standalone modules into one `master.py`
# namespace, and resolves the name collisions that creates with a whole-word
# regex over each module's ENTIRE TEXT -- code, comments and string literals
# alike.  For its Stage 1 module the rewritten words are `CONFIG`,
# `build_catalog` and `lookup_asteroid`.
#
# So an adapter there cannot write
#
#     from asteroid_catalog import build_catalog as _pkg_build
#
# because the word `build_catalog` is rewritten on its way into master.py and
# the import asks this package for a name that does not exist.  Aliasing the
# LOCAL name does not help; the imported name is still a bare word.  The fix
# has to be on this side, and the same lesson cost the spacecost split a
# release before it was written down there as `validate_tables`.
#
# `build_catalog_table` and `lookup_body` are chosen so that the rewrite cannot
# match them: a word boundary needs a non-word character, and `_` is a word
# character, so `\bbuild_catalog\b` does not match inside `build_catalog_table`.
# Verified by `tests/test_consumer_contract.py`, which runs the real regex.
#
# If you rename these, that adapter breaks at import with an ImportError that
# names a function nobody wrote.

def build_catalog_table(config: CatalogConfig = CONFIG) -> pd.DataFrame:
    """`build_catalog`, under a name a rewriting build cannot break.

    Identical behaviour; see the block above this definition for why a second
    name has to exist at all.

    THE SIGNATURE IS PART OF THE ALIAS.  `tests/test_consumer_contract.py`
    holds it equal to `build_catalog`'s, because a second name that drifts
    from the first is worse than no second name: the caller who needs this one
    is the one who cannot use the other, so they have no way to notice.
    """
    return build_catalog(config)


def lookup_body(catalog: pd.DataFrame, query: str) -> pd.DataFrame:
    """`lookup_asteroid`, under a name a rewriting build cannot break.

    Identical behaviour; see the block above `build_catalog_table` for why a
    second name has to exist at all.
    """
    return lookup_asteroid(catalog, query)


__all__ = [
    # configuration
    "CatalogConfig", "CONFIG", "DATA_VERSION", "__version__",
    # output control
    "set_verbose", "is_verbose", "say", "warn",
    # reference data
    "TAXONOMY_COMPOSITION", "PGM_ENRICHMENT_BY_TYPE", "pgm_enrichment_for_type",
    "ALBEDO_FALLBACK", "ALBEDO_BY_SPECTRAL_TYPE", "ALBEDO_BY_SEMI_MAJOR_AXIS_AU",
    # sources
    "fetch_jpl_sbdb", "fetch_ssodnet", "fetch_neowise", "fetch_mp3c",
    "JPL_SBDB_URL",
    # the chain
    "merge_sources", "deduplicate_catalog", "derive_missing_diameters",
    "validate_and_filter", "enrich_composition", "build_catalog",
    # reading a built catalog
    "lookup_asteroid", "filter_by_region", "filter_by_spectral_group",
    # collision-proof second names -- see the block above
    "build_catalog_table", "lookup_body",
]
