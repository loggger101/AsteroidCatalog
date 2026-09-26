# Changelog

Two numbers move independently here, and conflating them is the mistake this
file exists to prevent:

| | what it tracks | where it lives |
|---|---|---|
| `asteroid_catalog.__version__` | the **package** release: a loader fix, a new helper, a docs pass | `__init__.py` (pyproject.toml reads it from there) |
| `pipeline_version` | the **data contract**, stamped into every output row | `config.py` |

A package release can leave `pipeline_version` alone. A change that moves any
number a build produces **must** move it, and that rule is one-directional:
moving it is not evidence that a number changed.

---

## Unreleased — data contract **1.4.1**

**A body's size and its class read "no classification" the same way.**
`derive_missing_diameters` recognised three spellings of an empty class
(`""`, `"nan"`, `"None"`) and `enrich_composition` eight (`"-"`, `"NA"`,
`"<NA>"`, ...).  So a Bus column holding `"-"` blocked the Tholen fallback in
the first and not the second: the body was sized off its orbit bin (p_V 0.066
in the outer belt) and typed by its Tholen class (S: 0.234), a diameter 1.9x
and a mass 6.6x what its own class implies.  Both now read
`taxonomy._BLANK_CLASSES`.  This moves numbers for such bodies, so the data
contract moves; **no row of `data-2026-09-25` is one** (checked against the
published parquet), and on synthetic sources built to contain them only those
rows' `albedo_assumed_for_diameter`, `diameter_km`, `diameter_source` and
`estimated_mass_kg` change.

Everything else below moves no number: a full offline build against faked
services writes the same catalog, cell for cell, under pandas 3 and 2.2.

**Bugs fixed**

| where | what went wrong |
|---|---|
| `lookup_asteroid` | under pandas 2, `astype(str)` spells a missing name `"nan"`, so `lookup NA` or `lookup nan` returned ~1.54 M rows of the published catalog; and a blank query returned every row, which the CLI then printed |
| `build_catalog` | never created its output directory (only the CLI did), so a library build fetched everything and then failed writing the CSV |
| `CatalogConfig` | the default `output_dir` and `ASTEROID_CATALOG_OUTPUT_DIR` were read once, at import; set after `import asteroid_catalog`, they were ignored |
| SsODNet | a failed refresh threw away the cached parquet, and the whole source with it; it now falls back to the stale copy, as the MPC links already did |
| NEOWISE async | the wait ceiling counted only sleeps, not polls that may each take `request_timeout`; a relative job URL was used as-is; a refused `PHASE=RUN` was polled for the full ceiling; the session was never closed |
| `asteroid-catalog` | a malformed or missing `--previous` crashed `package` with a traceback; negative `--*-limit` values reached the APIs; `taxonomy m` or `taxonomy Sq2` found nothing; `lookup` printed every match (now 50, `--max-rows 0` for all); a failed `build` left an empty output directory |
| `pyproject.toml` | `license = "MIT"` needs setuptools 77 (PEP 639); the build requirement said 68, which fails on it |
| the tests | nothing kept them off the network; `tests/conftest.py` now refuses every socket connection |

**Documents corrected**: the SsODNet citation (the authors are Berthier,
Carry, Mahlke and Normand, A&A 671, A151; "Vachier" was wrong) with its DOI;
the column is `comp_pgm_enrichment`, not `pgm_enrichment`; the release gate
and section 5 of the README list all the checks that run, including an
albedo below 0.01 and a measured diameter its H cannot fit; the CLI, not
`build_catalog`, is what asks before overwriting; `filter_by_region` selects
on semi-major axis, so its docstring no longer offers it for NEOs, which are
defined by perihelion.

**Also, moving nothing: one copy of each thing.** The package was built by
slicing line ranges out of one 3,338-line module, and every slice kept that
module's whole import header and its own copy of the helpers around it.

| was | now |
|---|---|
| 116 unused imports: the same 13-line header in every sliced module | removed |
| four streamed downloads with a progress bar (JPL, NEOWISE, SsODNet, MPC) | `_http.read_body` / `_http.write_body` |
| "numeric column, or NaN if absent", a dozen times inline | `_frame.numeric` / `flag` / `coerce_numeric` |
| two cache-freshness checks, two identical designation keys | `config._cache_is_fresh`, `designations._designation_key` |
| exact-class-then-root-letter lookup and Bus-DeMeo capitalisation, each in three modules | `taxonomy.composition_entry`, `taxonomy._bus_demeo_case` |
| the CLI's own catalog reader | `query.read_catalog` (still importable from `release`) |
| the version in `pyproject.toml` and `__init__.py` | `__init__.py` only |
| "how to add a source" in three places, each incomplete | `build.py`, ADDING A SOURCE |
| three spellings of "no classification" (`"-"`, `"<NA>"`, ...) | `taxonomy._BLANK_CLASSES` |
| the tests' subprocess environment and tool loader, three copies | `tests/_support.py` |
| `test_reference_export` re-typing the exporter in a subprocess string | it calls `export_reference.export()` |

**`build_catalog` creates its output directory.** Only the CLI did, so a
library call with the default config fetched every source and then failed
writing the CSV.

**No pyarrow, no SsODNet, said loudly and before the download.** The fetcher
used to fall back to reading all ~915 columns, which `pyproject.toml` already
calls worse than failing; pyarrow is a declared dependency.

⚠️  **`CatalogConfig.preview_rows` and `top_n_spectral_types` are removed.**
Nothing read them; the preview they configured stayed in economicspace. Code
passing either by keyword must drop it.

**`enrich_composition` is three steps you can read one at a time**:
`_classify`, `_add_composition`, `_reconcile_density_and_mass`.  The albedo
class inference in it is vectorised; it was a Python call per row, on ~1.4 M
rows, to choose between two letters.  Helpers that were nested inside long
fetch functions (`_as_designation`, `_first_period`, `_albedo_from_taxonomy`)
are module level, and imports that sat inside functions for no reason are at
the top.

**CI lints.**  `ruff check`, with correctness rules only (`F`, `E9`; see
`pyproject.toml`), so the dead imports cannot come back; no formatter, because
the code aligns columns by hand.  The publish workflow reads `allow_shrink`
through the environment like its other input, as its own header says every
input must.

Also: `say()` / `warn()` continuation lines realigned (they still sat where
`print(` had put them), SsODNet's parquet size corrected to the ~850 MB it now
is, the package docstring's "76-class table" (it has 32 classes) and "says so
on stderr" (`warn` writes to stdout) corrected, and comments that pointed at
economicspace's `versions.md`, at a `_lookup()` that no longer exists, or at
sections that do not exist here fixed.

---

## 0.5.0 - 2026-09-25

**The economicspace consumer contract is retired, because its consumer is
gone.** economicspace's Stage 1 has installed a pinned `data-*` release since
its master v1.34.0 and imports nothing from this package, which 0.3.0 recorded
and left "for a separate decision". This is that decision:

| removed | why it existed | why it can go |
|---|---|---|
| `build_catalog_table`, `lookup_body` | collision-proof second names for an adapter that `build_master.py`'s whole-word rewrite would otherwise break | no adapter imports them; `build_catalog` and `lookup_asteroid` are the names |
| `tests/test_consumer_contract.py` | pinned those names, and four private helpers, against that rewrite | it guarded a surface nothing reads; `test_data_version_matches_the_config` moved to `tests/test_release.py`, since a manifest is what a consumer checks now |
| `config._fmt_limit` | the adapter's banner rendered row caps with it | nothing calls it |

`config._resolve_cache_dir`, `taxonomy._by_distinct` and
`designations._extract_canonical_designation` stay: this package uses all
three itself.

**`tools/audit_catalog.py` lists five reference bodies** (Ceres, Pallas, Vesta,
Psyche, Eros) and exits non-zero if any is missing or not `measured`. It was
economicspace's `verify_stage1.py` check 6, which pinned their literature values
to three decimals and went red on `data-2026-09-25` for correct reasons (a mass
is published beside its own source's diameter now, so Vesta reads 525.400 km,
Pallas 512.588, Psyche 223.143 and Eros 17.600). The build is this repository's
question, so the check lives here, asserting the half that never goes stale.
`tests/test_audit_reference_bodies.py` holds it to that. The publish workflow
still runs the audit as information, so a failing reference body is reported
in the run's summary but does not stop a release; only the release gate does.

⚠️  **A breaking change to the public surface**, which is why the minor version
moves: code calling `build_catalog_table` or `lookup_body` must call
`build_catalog` or `lookup_asteroid`. No number a build produces moved; the data
contract stays at **1.4.0**, and no catalog release is needed.

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
| **Impossible and unrealistic densities.** SsODNet Ch-types at 4.8–5.2 g/cm³ (Hedda, Aline), P-types at 5.3, a D-type at 6.3; S-, M- and X-types at 5.4–6.9 (Kallisto, Heidelberga, Prymno), above any asteroid ever measured | 20 above the carbonaceous ceiling, 12 above the measured record | dropped; the class estimate stands in |
| **Albedos at a fit's ceiling.** JPL's 1.000 (24) and SsODNet's 1.10 for Makemake | 25 | refused; the next source's value is used |
| **Rotation faster than breakup.** JPL periods under 1.5 h on 10–18 km bodies, where SsODNet has 48–180 h | 27 | refused for bodies ≥10 km at their class's density ceiling |
| **Icy bodies typed as rock.** Albedo inference made Pluto, Haumea, Makemake and Sedna basalt (V, 2.9 g/cm³), Quaoar and Gonggong S, and every H-sized TNO a main-belt C | 8,312 untyped bodies beyond 5.5 AU; 14,879 untyped Trojans typed C where D is their commonest class | an untyped body from the Trojans out (a ≥ 4.6 AU) is D, `spectral_type_source = "orbit"`; a measured class is never overridden |

**Every calculation and assumption re-checked against that release.** Each
derived column was recomputed from its own inputs across all 1,566,618 rows:
H-derived diameters, orbit-bin albedos, composition lookups, PGM factors,
class densities and derived masses reproduce to the last bit; q, Q, period and
mean motion to JPL's rounding (1e-7); 1329 km is 2 AU × 10^(V☉/5) = 1329.09;
Ceres, Vesta, Eros and Bennu come out at their spacecraft mass, period and
spin; SsODNet's asymmetric errors are offsets (median 24% of a diameter), not
bounds.  The orbit-bin albedo medians and the 0.078 fallback reproduce
exactly on the release's JPL albedos.  Three things did not survive:

| assumption | what the release says | fix |
|---|---|---|
| **The class albedo table sizes few bodies** ("fires rarely") | it sizes 105,873, typed mostly by SsODNet, while its medians came from 1,897 JPL-typed bodies: D 0.051 against 0.082 on 2,127 bodies, T 0.065 against 0.111, K 0.142 against 0.184, V 0.388 against 0.336; subclasses like Ds (0.127) fell to their root letter's 0.051 | recomputed on the labels it is applied to: 47 classes with n ≥ 5 over 65,159 bodies; E-types (32, median 0.583) are no longer sized as dark |
| **A class lookup matches the source's spelling** | "SQ" and "SA" missed "Sq" and "Sa" and sized off the S median: 663 bodies 6% too large, 20% too heavy | capitalised as enrich_composition capitalises |
| **p_V ≥ 0.35 means V** | of 4,191 bright bodies with a source class, 916 are V and 2,473 S-complex: right 22% of the time, and V carries basaltic crust's metal and a 0.2× PGM factor | bright bodies are S; the C/S split at 0.10 is right for 84.0% (the best split, 0.13, 85.2%) |

**A second pass**, over what the first could not see, found eight more:

| assumption | what the release says | fix |
|---|---|---|
| **One orbit bin fits everyone at that a** | NEOs are 1.3–1.8x darker than the belt at the same a (0.170 against 0.4135 at 1.3–2.0 AU); the 0.2885 there was a blend fitting neither | a NEO table beside the belt table: 38,367 NEOs were up to 2.2x too light, 30,232 Hungarias 1.7x too heavy |
| **a ≥ 5.2 AU is Centaur/TNO** | 1,228 of the bin's 1,231 measured bodies were Jupiter Trojans; half the Trojans sat in the Hilda bin | Hilda (3.7–4.6, 0.055), Trojan (4.6–5.5, 0.070), beyond 5.5 AU |
| **One albedo beyond Jupiter** | the median runs 0.147 at H 3–6 down to 0.0585 past H 8; at 0.069, 532037 Chiminigagua was 1,219 km against ~740 measured, the 8th-heaviest body | albedo by H past 5.5 AU (`ALBEDO_BEYOND_JUPITER_BY_H`), over every provider's 193 |
| **A measured diameter is this body's** | 18 beside an H that puts them at p_V 0.0001–5.6: a mislinked detection (2010 BK37, 1.95 km at H 23.97) or a failed fit | refused outside p_V 0.005–2.0 (the albedo range widened by 0.75 mag); the next source's, or H's, stands in |
| **A measured albedo is a surface** | 43 below 0.01, down to 0.0007 | refused below 0.01, half the darkest body measured |
| **Untyped Trojans are C** | D is the Trojans' commonest class (36.5% of 1,559 typed; C-complex 24.6%, mostly P) | D from the orbit from 4.6 AU out |
| **Every body with a diameter has a mass** | 63 did not: 32 Mahlke "Z" (very red, D-like, Trojans up to 118 km) unknown to the class table, 27 measured diameters with no albedo or class | class `Z` (as D); the orbit-bin albedo types the 27. The 4 Tholen "U" (unclassifiable) stay Unknown |
| **A sigma is an uncertainty** | 559 JPL H sigmas and 2 diameter sigmas are 0 | a zero sigma is no sigma |

The gate now also refuses an albedo below 0.01 and a measured diameter outside
the H-implied range, and `tools/audit_catalog.py` lists the 25 heaviest bodies
with the provenance of every number, since they dominate any mass total.

Two assumptions checked and kept, with what they cost: C and S class
densities (1.5, 2.7) sit inside the measured spread (medians 1.64 over 83
bodies, 2.79 over 48); X-complex's 3.3 is above its measured median of 2.21
(33 bodies), so an H-sized X-type's derived mass runs ~50% heavy. That class
carries the metal fraction the mining layer values, so it is left as a
modelling decision, not changed here.

The density ceilings were checked against the meteorite literature and the
measured record before release. Carbonaceous grain densities top out at about
3.6 (CO/CV), a physical limit. For every other class the ceiling is 5.0, and
that is the measured record, not physics: stony-irons could reach 7.8, but no
asteroid has been measured above about 4.2, and the densest of the 32 masses
known to 5% is 3.54. The release gate keeps iron's 8.0 as the absolute bound.
Past 5.5 AU, composition comes from D whatever class a source gave: Ixion's
colour-class "S" had made it 2.7 g/cm³ and 5.05e20 kg.

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
of it; `data-2026-09-23` fails on six counts. **`tools/audit_catalog.py`** runs
the gate and the checks no limit can decide on any build or release, and the
publish workflow writes its report to the job summary. `taxonomy.json` gains
`DENSITY_LIMITS_GCM3`.

**Not fixed, and why**: a binary's mass in ssoBFT is often the system's. Pluto
carries 1.447e22 kg, the Pluto–Charon system; MP3C has Pluto's 1.30e22. Both are
possible, so no limit can choose, and precedence keeps SsODNet's. 4,755 bodies
have sources more than 1 mag apart in H, and 714 have rotation periods exactly
2x apart; the audit lists them.

**Verified on the live sources**, by three dry runs of the publish workflow
on 2026-09-25 (no release published): the final one built 1,567,469 bodies,
passed every gate including the physical one, and its audit lists the 25
heaviest bodies at their literature masses (Eris 1.649e22 kg, Haumea 4.04e21,
Ceres 9.384e20, Vesta 2.590e20, Pallas 2.053e20) and H-sized TNOs within ~15%
of their measured sizes. 4 bodies are left without a mass, all Tholen "U".

`pipeline_version` moves to **1.4.0**.

**Published as [`data-2026-09-25`](https://github.com/loggger101/AsteroidCatalog/releases/tag/data-2026-09-25)**,
the first 1.4.0 release: 1,567,469 bodies, built from `140942b`, audit clean.
Hygiea's share of main-belt mass is back to 0.034, from the 0.041 that JPL's
one-figure GM had given it. The first attempt at it was refused by the release
gate: SsODNet's ~500 MB download timed out once, 135 s in, the build went ahead
without it, and the gate stopped it at 0 SsODNet bodies. A re-run published.
Since then, and changing no number a build produces:

- **the SsODNet download retries** a timeout, a dropped connection or an HTTP
  5xx/429 up to three times, 30 s then 60 s apart; a 4xx or a local error
  fails at once (`tests/test_ssodnet_download.py`);
- the merge's progress line for dropped diameters counts only the
  mass-diameter arbitration's drops, where it had also counted diameters the
  H check refused (25 reported, most of them H refusals);
- both workflows use `actions/checkout@v5` and `actions/setup-python@v6`,
  which run on Node 24; GitHub had begun forcing the Node 20 majors onto it.

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

## 0.1.0 - 2026-09-22

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
