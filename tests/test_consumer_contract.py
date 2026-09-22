# -*- coding: utf-8 -*-
"""The surface economicspace imports, and the rewrite that can break it.

THIS FILE IS THE REASON `build_catalog_table` AND `lookup_body` EXIST.  Delete
either as a duplicate and the downstream adapter fails at import with an
ImportError naming a function nobody wrote.

economicspace concatenates four standalone modules into one `master.py`
namespace and resolves the resulting name collisions with a whole-word regex
over each module's ENTIRE TEXT -- code, comments and string literals alike.
For its Stage 1 module the rewritten words are `CONFIG`, `build_catalog` and
`lookup_asteroid`.  So the adapter cannot spell any of those three in an
import, and the defence has to live on this side of the seam.
"""

import re

import pytest

import asteroid_catalog as ac


# The real transform, copied from economicspace build_master.py `word_replace`.
def word_replace(content, old, new):
    return re.sub(r"\b" + re.escape(old) + r"\b", new, content)


REWRITES = [
    ("CONFIG", "CATALOG_CONFIG"),
    ("build_catalog", "build_asteroid_catalog"),
    ("lookup_asteroid", "lookup_asteroid_catalog"),
]

# What the adapter is allowed to import.  Every name here must survive all
# three rewrites unchanged, or the built master.py asks for something else.
ADAPTER_IMPORTS = [
    "CatalogConfig",
    "build_catalog_table",
    "lookup_body",
    "set_verbose",
    "TAXONOMY_COMPOSITION",
    "PGM_ENRICHMENT_BY_TYPE",
    "pgm_enrichment_for_type",
    "enrich_composition",
    "merge_sources",
    "deduplicate_catalog",
    "derive_missing_diameters",
    "validate_and_filter",
    "fetch_jpl_sbdb",
    "fetch_ssodnet",
    "fetch_neowise",
    "fetch_mp3c",
    "filter_by_region",
    "filter_by_spectral_group",
    "DATA_VERSION",
]


@pytest.mark.parametrize("name", ADAPTER_IMPORTS)
def test_adapter_import_survives_the_rewrite(name):
    """A name the adapter imports must come out of `word_replace` unchanged."""
    line = "from asteroid_catalog import %s" % name
    out = line
    for old, new in REWRITES:
        out = word_replace(out, old, new)
    assert out == line, (
        "%r is rewritten to %r on its way into master.py, so the import asks "
        "this package for a name it does not export. Add a collision-proof "
        "second name here rather than renaming the original." % (line, out))


@pytest.mark.parametrize("name", ADAPTER_IMPORTS)
def test_adapter_import_exists(name):
    """...and it has to actually be exported."""
    assert hasattr(ac, name), "asteroid_catalog does not export %r" % name


def test_the_rewrite_really_would_break_the_obvious_names():
    """The guard is not vacuous: the NAIVE names really are rewritten.

    Without this, all of the above passes trivially if somebody makes
    `word_replace` a no-op, and the test suite reports a contract it is no
    longer checking.
    """
    for bare, cooked in (("build_catalog", "build_asteroid_catalog"),
                         ("lookup_asteroid", "lookup_asteroid_catalog"),
                         ("CONFIG", "CATALOG_CONFIG")):
        line = "from asteroid_catalog import %s" % bare
        out = line
        for old, new in REWRITES:
            out = word_replace(out, old, new)
        assert cooked in out and out != line


def test_aliases_are_the_same_function():
    """A second name that drifts from the first is worse than no second name."""
    import inspect
    assert inspect.signature(ac.build_catalog_table) == \
        inspect.signature(ac.build_catalog)
    assert ac.lookup_body.__doc__ and ac.build_catalog_table.__doc__


def test_data_version_matches_the_config():
    """The stamp a consumer pins against is the one stamped into the rows."""
    assert ac.DATA_VERSION == ac.CONFIG.pipeline_version


# ---------------------------------------------------------------------------
# THE PRIVATE HELPERS THE ADAPTER REACHES THROUGH A SUBMODULE
# ---------------------------------------------------------------------------
# 🚨  THESE LOOK DEAD FROM INSIDE THIS REPOSITORY AND THEY ARE NOT.
#
# Each is underscore-prefixed, absent from `__all__`, and called by nothing in
# this package, its tests or its tools. A dead-code sweep run here will flag
# every one of them -- one did, on the day they were written -- and deleting
# them breaks economicspace's Stage 1 adapter at import or at its first banner.
#
# They are reached as `asteroid_catalog.<module>.<name>`, so they are part of
# the contract whether or not the leading underscore suggests otherwise. The
# alternative was for the adapter to keep its own copies, which is two
# definitions of one thing; this is the same arrangement `spacecost` uses for
# the private names economicspace's Stage 2 reaches.
#
# ⚠️  Delete a row here only when the adapter has stopped reaching for it.
PRIVATE_CONSUMER_SURFACE = [
    # module,       name,                     why the adapter needs it
    ("designations", "_extract_canonical_designation",
     "verify_stage1.py drives it directly, as the documented regex trap"),
    ("taxonomy", "_by_distinct",
     "verify_stage1.py check 4 holds it to a per-row apply"),
    ("config", "_resolve_cache_dir",
     "the adapter creates the download cache before its first banner"),
    ("config", "_fmt_limit",
     "the adapter's startup banner renders each row cap with it"),
]


@pytest.mark.parametrize("mod,name,why", PRIVATE_CONSUMER_SURFACE)
def test_private_consumer_surface_still_exists(mod, name, why):
    import importlib

    m = importlib.import_module("asteroid_catalog." + mod)
    assert hasattr(m, name), (
        "asteroid_catalog.%s.%s has gone, and economicspace's Stage 1 adapter "
        "reaches it: %s" % (mod, name, why))


@pytest.mark.parametrize("mod,name,why", PRIVATE_CONSUMER_SURFACE)
def test_private_consumer_surface_is_callable_or_data(mod, name, why):
    """Existing is not enough; the adapter uses these, it does not admire them."""
    import importlib

    m = importlib.import_module("asteroid_catalog." + mod)
    obj = getattr(m, name)
    assert obj is not None
