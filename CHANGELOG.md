# Changelog

Two numbers move independently here, and conflating them is the mistake this
file exists to prevent:

| | what it tracks | where it lives |
|---|---|---|
| `asteroid_catalog.__version__` | the **package** release: a loader fix, a new helper, a docs pass | `pyproject.toml` and `__init__.py` |
| `pipeline_version` | the **data contract**, stamped into every output row | `config.py` |

A package release can leave `pipeline_version` alone. A change that moves any
number a build produces **must** move it, and that rule is one-directional:
moving it is not evidence that a number changed.

---

## 0.1.2 - 2026-09-22

**A redundancy audit of the split, and the trap that closing it opened.**

The audit asked two questions of every top-level name the pre-split module
bound: is it still reachable, and is it now defined more than once. **63 names
carried, 0 dropped.** Two were defined twice, and they were opposite kinds:

| | where it was dead | where it is used |
|---|---|---|
| `_PY` | economicspace's adapter | here, by `ssodnet`'s pyarrow hint |
| `_fmt_limit` | **here** | economicspace's adapter, for its banner |

Each is the same defect seen from one end: a split moves a helper's USERS
without moving the helper, or the other way round, and what is left behind
still imports, still parses, and is called by nothing.

The adapter dropped its `_PY` and now reaches this package's `_fmt_limit`
rather than keeping a copy, so each name has exactly one definition.

🚨  **THAT MADE `_fmt_limit` A PRIVATE NAME CONSUMED ACROSS A REPOSITORY
BOUNDARY, WHICH IS A NEW TRAP.** It is underscore-prefixed, absent from
`__all__`, and called by nothing here -- so a dead-code sweep run in this
repository flags it, and one did, on the day it was written. Deleting it
breaks the consumer's first banner.

`tests/test_consumer_contract.py` gains `PRIVATE_CONSUMER_SURFACE`: the four
private names economicspace reaches through a submodule, each with the reason
it is reached, each asserted to exist. Proved by deleting one and watching the
suite name it. `config.py` carries a note where a sweep will land, so the
finding explains itself rather than looking like dead code twice.

Same arrangement `spacecost` uses for the private names economicspace's Stage 2
reaches. No number moved; the data contract stays at **1.2.0**.

---

## 0.1.1 - 2026-09-22

Two module-level banner prints left `taxonomy.py`: "Taxonomy lookup ready" and
"PGM enrichment table ready".

**They could never fire.** Verbosity is always set *after* import -- the CLI
sets it in `main()`, a consumer sets it after `import asteroid_catalog` -- so
by the time anything turns output on, those two statements have already run
silently. They were dead code that looked alive.

They are also stage banner text rather than library behaviour, so they moved to
the economicspace adapter, where they still print. One home for the sentence,
and a reachable one.

No number moved; the data contract stays at **1.2.0**. `tools/extraction_probe.py`
reports 25 checks, 107,521 values, 0 differing against the pre-split module,
unchanged.

Also adds `tools/extraction_probe.py` itself -- the probe that verified the
extraction, kept because the method is the point. It needs the pre-split
module, recovered from economicspace's history; its docstring says how.

---

## 0.1.0 — 2026-09-22

Extracted from Module 1 of
[economicspace](https://github.com/loggger101/economicspace) at
`pipeline_version` 1.2.0, commit `1ce0dba`. Data contract **1.2.0**.

**Nothing was re-typed.** The package was built by slicing source line ranges —
2,953 of that module's 3,338 lines — so the derivation chain here is the one
fourteen releases of measurement were taken against, not a careful copy of it.

### Verified

The extraction was checked in-process against the original module, because
Stage 1 cannot be re-run to answer the question: JPL adds bodies daily, so a
rebuilt catalog is a different length and comparable with nothing already
measured.

**25 checks, 107,521 values, 0 differing:**

- every reference table leaf by leaf, at full `repr` **and** raw IEEE bit
  pattern, with dict **key order** compared too — a reordered table moves a CSV
  column order without moving a number, and a float probe alone would pass it
- every pure function run both ways over a stride sample of a real
  1,555,667-row catalog, compared cell by cell on bit patterns rather than with
  a tolerance: `enrich_composition`, `derive_missing_diameters`,
  `validate_and_filter`, `merge_sources`, `deduplicate_catalog`,
  `lookup_asteroid`, `filter_by_region`, `filter_by_spectral_group`
- all 24 function bodies compared as **source text** against the original's
  line range, normalised only for the output-call rename
- the config field surface and every default except the documented adaptations

The probe was then fed a wrong answer — one PGM factor moved 2.0 → 2.5 — and
went red on both the table and the function that reads it, which is what makes
the clean run worth quoting.

### Changed on the way out, and nothing else

- **output is opt-in.** All 114 `print` calls became `say()`, silent unless
  `set_verbose(True)`. A pipeline stage that is also the program should print
  its progress; a library imported to read one taxonomy row should not.
- **ten of them became `warn()` instead**, and that split is the substance
  rather than a detail. A blanket pass silenced the zero-match alert — the one
  diagnostic that catches a fetcher contributing nothing while its own fetch
  summary reads 183,408 — and a diagnostic that has gone quiet reads exactly
  like a clean result. A defect in this code or a fatal abort is loud; an
  external condition the design tolerates is progress output.
- **no import-time side effects.** The original created its output directory
  and its download-cache directory at import, and printed its configuration.
- **the output directory** defaults to `./asteroid_catalog_data` and reads
  `ASTEROID_CATALOG_OUTPUT_DIR`. The original's Colab detection went with the
  pipeline; a library has no business guessing it is in a notebook.

### Added

- `build_catalog_table` and `lookup_body`, **collision-proof second names**.
  These are not convenience aliases. economicspace concatenates four modules
  into one namespace and resolves collisions with a whole-word regex over each
  module's entire text, so an adapter there cannot spell `build_catalog`,
  `lookup_asteroid` or `CONFIG` in an import.
  `tests/test_consumer_contract.py` runs that real regex.
- a CLI: `asteroid-catalog build | lookup | taxonomy`, with an overwrite guard,
  because the catalog a build replaces cannot be fetched again.
- `reference/*.csv`, renderings of the taxonomy tables that are regenerated and
  compared byte for byte by the test suite rather than trusted.
- a test suite of the documented traps, executed. Every one was a rule written
  in prose first, and cost a release before anything ran it.
