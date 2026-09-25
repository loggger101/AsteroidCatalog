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

## 0.4.0 - 2026-09-25 — data contract **1.4.0**

**Nothing physically impossible is published.** An audit of the
`data-2026-09-23` release found values no body can have, every one of them
real in a real source and taken because its source came first:

| defect | in `data-2026-09-23` | fix |
|---|---|---|
| **Impossible masses.** MP3C's 6.76e18 kg for 1686 De Sitter (29.7 km) is 495 g/cm³; its 5.43e18 kg for 152 Atala, 51 g/cm³. | 26 bodies outside 0.25–8 g/cm³ | each source's mass is checked against the densest rock its class could be (`physics.py`) before precedence applies |
| **JPL masses quoted to one figure.** SBDB `GM` gives Hygiea 7.0 and Interamnia 5.0 km³/s² (1.05e20 and 7.49e19 kg): Interamnia a B-type at 5.0 g/cm³, Hygiea 20% heavy | 2 of 17 JPL masses | mass precedence is SsODNet first: ssoBFT combines every published mass, JPL's spacecraft ones included (0.2% agreement on Ceres, Vesta, Eros, Bennu) |
| **A mass beside another catalog's diameter.** SsODNet's mass over JPL's radiometric diameter put Eunomia at 4.9 g/cm³; SsODNet's own 271 km (adaptive optics) gives 3.1 | 349 of 487 SsODNet masses sat beside a diameter >2% from their own | a mass is published with its own source's diameter |
| **System masses beside primary diameters.** Six TNO binaries: SsODNet and MP3C give the system's mass, MP3C alone the primary's size, at implied albedos up to 1.8 | 6 | when every mass contradicts the diameter, the quantity fewer sources report is dropped |
| **Masses with no determination.** 153 Hilda: 3.04e18 ± 7.04e19 kg | 4 | a sigma as large as the value is refused |
| **Mass, diameter and density disagreed in the same row.** The density was SsODNet's or the class table's, the mass another's | 486 rows | `estimated_mass_kg = density_gcm3 × volume` in every row; a measured mass sets the density |
| **H-derived diameters a measured mass refutes.** 2003 QY90: 5.2e17 kg on 257 km, 0.06 g/cm³ | 14 of 20 | re-derived from the mass at the class density, `diameter_source = "derived_mass"` |
| **Impossible source densities.** SsODNet C-types at 6.2 g/cm³, a D-type at 6.3 | 21 outside their class's range | dropped; the class estimate stands in |
| **Albedos at a fit's ceiling.** JPL's 1.000 (24) and SsODNet's 1.10 for Makemake | 25 | refused; the next source's value is used |
| **Rotation faster than breakup.** JPL periods under 1.5 h on 10–18 km bodies, where SsODNet has 48–180 h | 27 | refused for bodies ≥10 km at their class's density ceiling |
| **Icy bodies typed as rock.** Albedo inference made Pluto, Haumea, Makemake and Sedna basalt (V, 2.9 g/cm³), Quaoar and Gonggong S, and every H-sized TNO a main-belt C | 8,312 untyped bodies beyond 5.5 AU | an untyped body beyond 5.5 AU is D, `spectral_type_source = "orbit"`; a measured class is never overridden |

**New columns**: `albedo_screened_out`, `mass_screened_out`,
`rotation_period_screened_out` and `diameter_screened_out`, naming the sources
whose value was refused. A refused value still counts in `<stem>_n_sources` and
`<stem>_spread`, which describe what the sources say.

**Meanings that moved**: `density_measured` is True only for a density that rests
on measurements alone, a measured mass over a measured diameter or a source's
density. `diameter_provider` for a body with a measured mass is its mass's
source. New values: `diameter_source = "derived_mass"` and
`spectral_type_source = "orbit"`.

**The release gate** (`release.physical_problems`) refuses a build carrying any
of it; `data-2026-09-23` fails on four counts. **`tools/audit_catalog.py`** runs
the gate and the checks no limit can decide on any build or release, and the
publish workflow writes its report to the job summary. `taxonomy.json` gains
`DENSITY_LIMITS_GCM3`.

**Not fixed, and why**: a binary's mass in ssoBFT is often the system's. Pluto
carries 1.447e22 kg, the Pluto–Charon system; MP3C has Pluto's 1.30e22. Both are
possible, so no limit can choose, and precedence keeps SsODNet's. 4,755 bodies
have sources more than 1 mag apart in H, and 714 have rotation periods exactly
2x apart; the audit lists them.

`pipeline_version` moves to **1.4.0**.

---

## 0.3.0 - 2026-09-23

**The catalog is published, not just buildable.** A build cannot be repeated,
since JPL adds bodies daily, so every consumer that builds its own has its own
catalog. Builds are now published as GitHub Releases tagged `data-YYYY-MM-DD`,
and a consumer pins a tag.

- **`asteroid-catalog package`** (`release.py`) gates a build and writes the
  release assets: `asteroid_catalog.csv.gz` (the build's CSV byte for byte,
  gzipped with a zeroed header so the same CSV always gives the same sha256),
  `asteroid_catalog.parquet`, `rejected_entries.csv`, `taxonomy.json` (the
  composition tables the build used), and `manifest.json`.
- **The gates refuse a build that lost a source.** Floors on total rows,
  measured diameters and bodies per source, single-valued current stamps,
  unique designations, and no shrink against the previous release. A build
  tolerates a failed source by design; a published one must not.
- **`publish catalog` workflow**, run by hand from the Actions tab: build on a
  runner, gate, publish. `dry_run` and `allow_shrink` inputs. A tag that exists
  stops the run; releases are never overwritten.

**economicspace stops importing this package** once its master v1.34.0 lands:
its Stage 1 installs a pinned `data-*` release instead, so it no longer mirrors
`CatalogConfig` or `DATA_VERSION`, and a config field or contract change here
no longer breaks it at import. `build_catalog_table`, `lookup_body` and the
private names in `tests/test_consumer_contract.py` stay for now; retiring them
is a separate decision.

No number a build produces moved; the data contract stays at **1.3.0**.

---

## 0.2.0 - 2026-09-22 — data contract **1.3.0**

**An audit of every source against its live service, and a merge that joins
bodies instead of designations.** Every source was pulled in full on
2026-09-22 and joined back to JPL by hand. Six defects came out, all silent:
each build succeeded and printed plausible counts.

| defect | measured | fix |
|---|---|---|
| **MP3C never contributed.** Every URL the fetcher tried answered 404 or redirected; the service had moved to `dachs.oca.eu/tap` and renamed its tables. Documented as "regularly unreachable", so a wrong address read as an outage. | 0 rows, every build | new fetcher on `mp3c_main.best`: 1,335,502 bodies, 147,556 diameters, 436 masses, 139,961 family memberships, 1,031,612 proper-element sets |
| **NEOWISE bodies joined nothing** when NEOWISE carries them under a provisional designation JPL has since numbered, a secondary designation, or its own spelling `"1996 GQ0"` (a zero cycle count nobody else writes). They were dropped at validation. | 10,627 of 143,318 bodies (7.4%) | re-keyed onto JPL's designation (below): 99.94% match |
| **Duplicate bodies.** SsODNet rows keyed on a secondary designation carry their own orbit, so they survived validation beside the JPL row for the same body. | 182 in the 2026-08-11 build (`2001 FF217` beside `2015 KN450`) | same re-keying; 0 with the current ssoBFT |
| **Duplicates culled, not combined.** The dedup kept the most complete row and dropped the rest, and NEOWISE's repeat fits were settled by row order. A sigma could also be filled from a different source than its value. | 27,864 NEOWISE bodies with 2–8 fits | rows are combined column by column; NEOWISE fits error-weighted; a value's sigma always comes from the value's source |
| **`orbital_period_yr` was in days**, from both JPL (`per`) and SsODNet. | Ceres read 1679.85 | divided by 365.25 |
| **`name` held designations.** ssoBFT fills `name` with the provisional designation of every unnamed body, and the merge copied it into JPL's empty cells. | 1,537,189 unnamed bodies "named"; 26,520 real names | designation-shaped names masked at the source; `lookup_asteroid` also searches the new `provisional_designation` |

**Cross-source identity** (`identity.py`). Every supplement row is re-keyed
onto JPL's designation before the join: first from JPL's own number, name and
the primary provisional designation in `full_name`; then from the MPC's
designation links in `mpcorb_extended.json.gz`, one cached ~180 MB file. The
MPC links agreed with all 938 answers JPL's single-object API gave on a sample,
with 0 disagreements. That API is not used: sequential lookups at ~5/s drew an
HTTP 403 for the whole IP within about a thousand requests.

**Combined, not first-come.** `diameter_km`, `albedo`, `absolute_magnitude_h`,
`estimated_mass_kg` and `rotation_period_h` each gain `<stem>_provider`,
`<stem>_n_sources`, `<stem>_spread` and `<stem>_sources_agree`, and every row
gains `n_sources` and `sources`. Precedence is unchanged (JPL, SsODNet,
NEOWISE, MP3C). Agreement is not independence, since the catalogs share NEOWISE
upstream; the README says so where the columns are described.

**New columns**: `provisional_designation`, `absolute_magnitude_h_sigma`,
`albedo_sigma`, `estimated_mass_sigma_kg`, `neowise_n_fits`, `family`,
`proper_semi_major_axis_au`, `proper_eccentricity`, `proper_inclination_deg`,
plus the provenance columns above. JPL's `GM` now supplies a measured
`estimated_mass_kg` for the 17 bodies that have one (Ceres, Vesta, Bennu, ...).

**Also fixed**: `_extract_canonical_designation` turned a nullable-string NA
into the literal `"<NA>"`, a ghost key; it is now missing.

**Same-day A/B**: the 0.1.3 code and this one both run on the full
2026-09-22 sources.

| | 0.1.3 | 0.2.0 |
|---|---|---|
| bodies after validation | 1,566,600 | 1,566,616 (all 1,566,600 kept, +16) |
| rejected for no orbit | 10,632 | 210 |
| bodies with NEOWISE data | 132,691 | 143,015 |
| MP3C rows | 0 | 1,335,502 |
| measured diameters | 149,594 | 149,740 |
| measured masses | 532 | 540 |
| a measured diameter that changed value | | 0 of 149,594 |
| `name` non-null | 1,563,628 | 26,521 |
| columns | 64 | 95 |

143,010 bodies are known to all four sources, 1,192,036 to three.

**What the agreement columns found on day one**: SsODNet's albedos run 22%
below the other three sources (median ratio 0.78), and NEOWISE's H is 0.28 mag
brighter than JPL's. These are one effect: SsODNet re-derives albedo from
current H, and the others quote NEOWISE-era fits. Values are left as they were
(JPL precedence); the README documents it.

**Source validation, the same day.** Each source was then checked against its
own service and against the others:

| check | result |
|---|---|
| completeness | JPL 1,566,683 of 1,566,683; ssoBFT 1,563,708 of 1,563,708; MP3C 1,335,502 of 1,335,502; NEOWISE 183,408 of 183,412, the 4 left out being the comets 29P, 167P and 324P |
| JPL field mapping | 8 bodies against the SBDB object API: every physical field exact, every orbital field equal to the API's rounding |
| units across sources | masses of Ceres, Vesta, Eros and Bennu agree to 0.2% in all three sources; SsODNet densities match JPL's to 1.5% except Eros (12%, a literature difference) |
| re-keyed joins | re-keyed NEOWISE diameters reproduce JPL's or SsODNet's for the same body within 1% for 93-97%, better than direct matches; their larger H differences are NEOWISE's 2010-era H |
| SsODNet orbits | 4,711 differ from JPL's by >1% in a; 98% are U = 7-9 orbits with a median 4-day arc, and H agrees exactly |

It found five more things, fixed here:

- **NEOWISE's assumed values were read as measured.** A `-` (or `F`) in a
  `fit_code` slot means the parameter was assumed, but the number is still
  there: beaming ~1.0 ± 0.2 on all 104,788 `DV--` rows, beaming 0 ± 0 on
  `DVF-`, and IR albedo -0.999 as "no value". These are blanked now, as are
  zero sigmas, which would have taken infinite weight.
- **MP3C's placeholders are numbers.** H = 0 (342 bodies), H = 99.99 (96) and
  diameter = 0 (77), where JPL has H 14.6-27 for the same bodies. Blanked.
  They were not harmless: 26 bodies with no H from JPL took MP3C's H = 0 and
  were sized at 5,000-5,600 km, larger than Pluto. They now have no H from any
  source and are dropped for having no diameter.
- **SsODNet's H sigma is not an uncertainty.** 1.41 M of its 1.56 M values are
  exactly 0.001, 0.01, 0.1, 1 or 10, the precision H was quoted to. No longer
  fetched; JPL's `H_sigma` is a real fit uncertainty.
- **NEOWISE bodies under two designations** (214) took one designation's
  value; they are now averaged with the rest of the body's fits.
- The NEOWISE query's `type != 'comet'` clause matches nothing, since no row
  has that type; the identifier clause is what excludes comets.  The comment
  said otherwise.

Left as the sources give them, and flagged by the agreement columns: 24 JPL
albedos of exactly 1.000 (a fit at its ceiling; SsODNet gives 0.52-0.91 for
the same bodies), and 961 rotation periods where JPL and SsODNet differ by
exactly 2x or 0.5x (the half/double-period ambiguity).

**Config**: `use_mpc_identifications` (default True) is new.
`pipeline_version` moves to **1.3.0**.

⚠️ **economicspace mirrors both.** Its Stage 1 adapter raises `SystemExit` at
import when its `CatalogConfig` fields or `pipeline_version` differ from this
package's, so it needs `use_mpc_identifications` added and its stamp moved to
1.3.0 when it repins.

---

## 0.1.3 - 2026-09-22

**`requirements.txt` is gone.** It listed the same five dependencies
`pyproject.toml` declares, by hand, with nothing holding the two to each
other -- and its own comment said *"pyproject.toml is the authority"*, which is
a request for a checker rather than a checker.

Nothing needed it. `pip install git+...`, `pip install -e .` and CI's
`pip install -e ".[test]"` all read `pyproject.toml`; no test, tool, workflow
or document referenced the file. The installed artifact is unchanged -- it was
never packaged.

No number moved; the data contract stays at **1.2.0**.

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
