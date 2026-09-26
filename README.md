# asteroid_catalog

One merged, provenance-tagged table of the known asteroids.

Four public surveys, cross-matched body by body, validated, and enriched with a
cited composition estimate per taxonomy class. About 1.57 million bodies, one
row each, one CSV. A body several sources know carries all of their data, and
says which source supplied each value and whether the sources agree.

**Most people should not build it.** Every published build is a
[release](https://github.com/loggger101/AsteroidCatalog/releases): one frozen
catalog per `data-YYYY-MM-DD` tag, gzipped CSV and Parquet, with a manifest
that names its build date, data contract and checksums. Pin a tag and you have
the same rows every time. See [Published releases](#published-releases).

The current release is
[`data-2026-09-26`](https://github.com/loggger101/AsteroidCatalog/releases/tag/data-2026-09-26):
1,567,657 bodies, data contract 1.4.1, built by asteroid_catalog 0.6.0.
`data-2026-09-25` (contract 1.4.0) was the first release built under the
physical limits in [section 5](#5-nothing-physically-impossible-is-published);
1.4.1 changed no body of it. `data-2026-09-23` (contract 1.3.0) stays
published and unchanged, and carries the impossible values that section lists.

The package on `main` (0.7.0) writes data contract **1.5.0**, which corrects
reference values the literature contradicts (the Xe/Xk rows, C-complex carbon,
S-complex and V metal, the Xc density; see [CHANGELOG.md](CHANGELOG.md)). No
release has been built under it yet, so `data-2026-09-26` still carries the
1.4.1 values.

To build your own from the live sources:

```bash
pip install git+https://github.com/loggger101/AsteroidCatalog@v0.6.0
asteroid-catalog build --out ./data
```

```python
import asteroid_catalog as ac

ac.set_verbose(True)                  # progress output; off by default
df = ac.build_catalog()               # fetch, merge, validate, enrich, write
ac.lookup_asteroid(df, "Bennu")
```

---

## What it does

| stage | what happens |
|---|---|
| **fetch** | JPL SBDB, SsODNet ssoBFT, NEOWISE V2.0 and MP3C, in that order |
| **merge** | every row re-keyed onto JPL's designation for that body, duplicates combined; JPL is the backbone and wins on conflicts (SsODNet first for masses), the rest fill gaps, and every measured value records who supplied it and whether the sources agree. A source value that is physically impossible is refused before precedence applies |
| **derive** | a diameter for the ~90% of bodies nobody measured one for, from absolute magnitude and an estimated albedo |
| **validate** | quality gates, with every rejection logged and counted |
| **enrich** | bulk density and four mass fractions per Bus-DeMeo class, plus an optional precious-metal layer; mass, diameter and density made to agree in every row |

### The sources

| source | contributes | size |
|---|---|---|
| [NASA JPL SBDB](https://ssd-api.jpl.nasa.gov/doc/sbdb_query.html) | orbital elements, H, designations, orbit quality, measured masses (GM); the authority on which body is which | ~1.57 M bodies |
| [IMCCE SsODNet ssoBFT](https://ssp.imcce.fr/) 🔔 | best-of-literature diameter, albedo, mass, density, rotation, taxonomy | ~1.56 M rows, ~850 MB parquet, cached |
| [NEOWISE V2.0](https://sbn.psi.edu/pds/resource/doi/neowise_2.0.html) 🔔 | thermal-IR diameters and albedos; repeat fits of a body averaged | 183 k fits of 143 k bodies |
| [MP3C](https://mp3c.oca.eu/) | best diameter, albedo, mass and H; collisional family; proper elements | ~1.34 M bodies |

🔔 **These two ask to be cited as a condition of use.** See
[CITATIONS.md](CITATIONS.md).

---

## Published releases

Each `data-YYYY-MM-DD` release on the
[Releases page](https://github.com/loggger101/AsteroidCatalog/releases) is one
build, frozen. Releases are never overwritten or rebuilt under the same tag.

| asset | what it is |
|---|---|
| `asteroid_catalog.csv.gz` | the catalog exactly as the build wrote it (CRLF), gzipped deterministically |
| `asteroid_catalog.parquet` | the same rows, typed: designations are strings, flag columns nullable booleans |
| `rejected_entries.csv` | every row validation dropped, and why |
| `taxonomy.json` | `TAXONOMY_COMPOSITION` and `PGM_ENRICHMENT_BY_TYPE` as this build used them, so the `comp_*` columns can be re-derived without installing the package, and `DENSITY_LIMITS_GCM3`, which decided the measured masses and densities it accepted, and (from 1.5.0) `DENSITY_EVIDENCE`, the measured bodies each class density answers to |
| `manifest.json` | release tag, `catalog_date`, `pipeline_version`, package version and commit, row count, bodies per source, and a sha256 for every asset and for the CSV inside the gzip |

Download by tag, so you always get the same file:

```
https://github.com/loggger101/AsteroidCatalog/releases/download/<tag>/asteroid_catalog.csv.gz
https://github.com/loggger101/AsteroidCatalog/releases/download/<tag>/manifest.json
```

```python
import pandas as pd
df = pd.read_parquet("asteroid_catalog.parquet")
# or, from the CSV; the identifier columns MUST be read as strings
df = pd.read_csv("asteroid_catalog.csv.gz", low_memory=False,
                 dtype={"designation": str, "provisional_designation": str,
                        "name": str, "spk_id": str})
```

### How a release is made

The **publish catalog** workflow (Actions > publish catalog > Run workflow)
builds from the four live sources on a GitHub runner, then runs
`asteroid-catalog package`, which **refuses to publish** a build that:

- has fewer than 1.5 M bodies, or under 135 k measured diameters;
- has any source known to fewer bodies than its floor (JPL 1.5 M, SsODNet
  1.4 M, MP3C 1.2 M, NEOWISE 130 k): the signature of a fetch that failed
  quietly;
- has a null or duplicated designation, or more than one `catalog_date` or
  `pipeline_version`, or a `pipeline_version` other than this package's;
- is smaller than the previous release by more than 0.5% of rows, or 2% of any
  source's bodies (the `allow_shrink` input overrides this one gate only);
- carries anything physically impossible: a mass and diameter implying a
  bulk density outside 0.25–8 g/cm³, a mass that is not density × volume, an
  albedo of 1 or more or below 0.01, a measured diameter that its H puts at an
  albedo no surface has, or a body 10 km or more across spinning faster than
  it could without flying apart. See [5](#5-nothing-physically-impossible-is-published).

Every failed gate is listed and nothing is published. `dry_run` builds and
gates without publishing. The same command works locally:

```bash
asteroid-catalog build --out ./data
asteroid-catalog package ./data --out ./dist --tag data-2026-09-25 --previous manifest.json
```

---

## Five things to understand before you use a built catalog

### 1. It is not reproducible, and that is a property of the data

JPL adds bodies daily. A catalog built today is a different length from one
built last week, so **a result measured against one build must name the build
it used**. Every row carries `catalog_date` and `pipeline_version`.

This is also why `asteroid-catalog build` asks before overwriting an existing catalog:
the file it would replace cannot be fetched again. And it is why builds are
published as [releases](#published-releases): a tag is a build you can name
and fetch again.

### 2. Most diameters are derived, not measured

Only 9.6% of bodies have a measured diameter (149,718 of 1,567,657 in
`data-2026-09-26`). The rest are sized from
absolute magnitude and an **estimated** albedo:

    D_km = (1329 / sqrt(p_V)) * 10 ** (-H / 5)

H is measured; `p_V` is not. So a derived diameter is uncertain by roughly the
square root of the albedo error — and a **mass** derived from it by that cubed.

`p_V` is the median measured albedo of bodies like this one, recomputed in 1.4.0
on the labels it is applied to (`asteroid_catalog/derive.py`): its spectral
class if a source gave one (47 classes); otherwise its orbital population. NEOs
and belt bodies have separate bins, because NEOs are 1.4–2.4× darker at the
same a; Hildas and Jupiter Trojans each have their own; and past 5.5 AU the
albedo follows H, because big TNOs are brighter (0.15 at H 3–6, 0.06 past
H 8).

Every such row is tagged in `diameter_source` and flagged in
`derived_diameter_is_estimate`. Filter on it to get the measured-only
population back:

```python
measured = df[~df["derived_diameter_is_estimate"]]
```

⚠️ **Read the provenance before comparing two catalogs.** Two builds with the
same row count and a different measured/derived split are not the same
population.

### 3. A failed source degrades the catalog silently — by design

An unreachable survey is tolerated rather than fatal, because a build that
dies whenever one of four hosts has a bad hour would be useless. But that means
**a source can fail and the run still looks fine**.

MP3C is the proof. It was documented as "regularly unreachable" for releases.
It was reachable the whole time, at a TAP address the fetcher never asked:
every URL the fetcher tried answered 404. A tolerated failure hides a wrong
address exactly as well as it hides an outage.

What is *not* tolerated is a source that fetched rows and matched none of them.
That is always a bug in the fetcher, never an empty upstream table, and it
prints whether or not you asked for progress output:

```
ALERT  NEOWISE matched ZERO backbone designations. Every one of its
       183,408 rows entered as a new body with no orbital elements...
```

That exact failure — a float-typed merge key stringifying to `"3.0"` and
joining nothing — cost the upstream project four releases of a source
contributing precisely zero while its fetch summary read 183,408. **Read the
per-source match counts, not the fetch counts.**

### 4. One body is one row, and agreement is not independence

The same asteroid has several designations: provisional ones from each time it
was found, and later a number. Each source keys on whichever one it had when
its table was built. So before joining, every supplement row is **re-keyed
onto JPL's designation for that body**:

1. from JPL's own number, name and primary provisional designation
   (`433 Eros (A898 PA)`), which places bodies numbered since a source's table
   was made;
2. from the Minor Planet Center's designation links, for what that misses:
   mostly secondary designations (`2009 UH126` = `583031`). This is one cached
   ~180 MB download (`mpcorb_extended.json.gz`); `use_mpc_identifications=False`
   skips it.

On a full build this places 99.94% of NEOWISE's bodies (92.6% before) and
99.99% of MP3C's. The ~200 rows nothing can place are logged and dropped at
validation for having no orbit.

*Why not ask JPL one body at a time?* Its SBDB object API knows the same links.
Sequential lookups at ~5 per second drew HTTP 403 for the whole IP address
within about a thousand requests, which would also block the JPL bulk download
every build starts with. The MPC links agree with every one of the 938 answers
JPL gave before the block.

Rows that still name the same body are **combined**, not culled: each column
takes the first non-null value, most complete row first. NEOWISE's repeat fits
of one body are averaged, error-weighted.

Every quantity more than one source measures (`diameter_km`, `albedo`,
`absolute_magnitude_h`, `estimated_mass_kg`, `rotation_period_h`) carries:

| column | meaning |
|---|---|
| `<stem>_provider` | the source the value came from (JPL, then SsODNet, NEOWISE, MP3C; for mass, SsODNet first) |
| `<stem>_n_sources` | how many sources report a value |
| `<stem>_spread` | max/min − 1 across them (max − min in magnitudes for H) |
| `<stem>_screened_out` | albedo, mass, rotation period (and diameter, see [5](#5-nothing-physically-impossible-is-published)): the sources whose value was refused as physically impossible; empty when none was. A refused value still counts in `n_sources` and `spread`, which describe what the sources say |
| `<stem>_sources_agree` | spread within tolerance (10% diameter, 25% albedo and mass, 0.3 mag H, 2% rotation); empty with one source |

The value's sigma always comes from the same source as the value. Per body,
`n_sources` and `sources` list who knows it.

⚠️ **Agreement is not independent confirmation.** Most JPL diameters are
NEOWISE fits, and ssoBFT and MP3C both compile NEOWISE among others, so two
catalogs agreeing is often one measurement quoted twice. Agreement shows that no
catalog garbled the value; a *dis*agreement is always worth reading. Psyche's
diameter, for example, spreads 30% across the four sources.

Measured on the 2026-09-22 sources, pair by pair:

| quantity | what the sources say |
|---|---|
| diameter | all four agree to within 0.4% (median ratio 1.000): mostly one NEOWISE measurement, quoted four times |
| albedo | **SsODNet runs 22% lower than the other three** (median ratio 0.78), so only 39% of multi-source albedos agree within 25% |
| H | NEOWISE is 0.28 mag brighter than JPL's current H; the others agree to ~0.1 mag |

The albedo and H rows are one effect. Albedo from a thermal fit scales as
10^(−0.4 H). NEOWISE fitted with the brighter H of its day, and JPL and MP3C
quote those albedos; SsODNet re-derives albedo from today's H, and
10^(0.4 × 0.28) ≈ 1.29. The two rows were measured independently and agree:
a 0.28 mag H offset predicts an albedo ratio of 1/1.29 = 0.77, and the
observed one is 0.78. It is also the effect Pravec et al. (2012, Icarus 221,
365) found from their own photometry, catalog H too bright by 0.4–0.5 mag on
average near H ≈ 14, and the reason they revised the WISE albedos downward.
So the `albedo` column, JPL's by precedence, is the
NEOWISE-era value and is not consistent with the H beside it. The catalog does
not re-derive it; `albedo_spread` and `albedo_provider` are there to find the
rows where it matters.

### 5. Nothing physically impossible is published

A value in a source is not evidence that the value is possible. The
`data-2026-09-23` release, the last built before data contract 1.4.0, carried:

| body | what the catalog said | why it cannot be |
|---|---|---|
| 1686 De Sitter | 6.76e18 kg on 29.7 km (MP3C) | 495 g/cm³; nothing is denser than iron, 7.9 |
| 152 Atala | 5.43e18 kg on 59 km (MP3C) | 51 g/cm³ |
| 704 Interamnia | 7.49e19 kg (JPL GM 5.0) | a B-type at 5.0 g/cm³; carbonaceous rock tops out at 3.6 |
| 10 Hygiea | 1.05e20 kg (JPL GM 7.0) | GM quoted to one figure; the literature has 8.7e19 |
| six TNO binaries | a system mass beside the primary's diameter | 9–16 g/cm³, at albedos up to 1.8 |
| Pluto, Makemake, Haumea, Sedna | typed V from albedo | basalt; a bright surface past Jupiter is ice |

Since 1.4.0, source by source and before precedence picks a value:

- **A mass must give the body a possible bulk density,** 0.25 g/cm³ up to the
  ceiling for its class (`asteroid_catalog/physics.py`). For the
  carbonaceous classes (C-complex, D, and the CV/CO analogues K and L) the
  ceiling is 3.6, the densest carbonaceous rock at zero porosity. For
  everything else it is 5.0, and that is the measured record, not physics.
  A stony-iron could be denser, but the densest asteroid measured is (22)
  Kalliope at 4.40 ± 0.46 (Ferrais et al. 2022), and 5.0 clears it by more
  than its one-sigma error. The densest of the 77 masses known to 5% in
  `data-2026-09-26` are Kalliope (4.18) and Psyche (4.14). The release
  gate still enforces iron's 8.0 as the absolute bound. A mass whose sigma is as large as itself
  is no determination and is refused too.
- **SsODNet is preferred for mass.** JPL's `GM` covers 17 bodies, carries no
  uncertainty, and is superseded for Hygiea and Interamnia.
- **A mass is published beside its own source's diameter,** so `density_gcm3`
  is a real measurement. ssoBFT's diameters for massive bodies come from
  occultations and adaptive optics (Eunomia 271 km, where JPL has a radiometric
  232 km); pairing its mass with JPL's diameter put Eunomia at 4.9 g/cm³.
- **When every mass contradicts the diameter,** the quantity fewer sources
  report goes: De Sitter's lone MP3C mass, or a TNO binary's lone MP3C
  diameter, which is then re-derived.
- **Albedos of 1 or more are refused**, which are fits at their ceiling, and
  so are albedos below 0.01, darker than any whole body ever measured.
- **A measured diameter must fit the body's H:** together they imply an
  albedo, and outside 0.005–2.0 (the albedo limits widened by 0.75 mag of H
  error) the diameter belongs to another body or is a failed fit.
  **Rotation periods** faster than breakup, `sqrt(3π/Gρ)` at the class's
  density ceiling, are refused for bodies 10 km or more across.

After enrichment, **every row satisfies `estimated_mass_kg = density_gcm3 ×
π/6 × diameter_km³`.** An H-derived diameter that a measured mass refutes is
re-derived from the mass at the class density (`diameter_source =
"derived_mass"`). Beyond 5.5 AU, composition comes from `D` whatever class a source gave,
because an asteroid class fitted to a TNO's colours says nothing about ice.
Bodies from the Trojans out (a > 4.6 AU) with no measured class are typed `D`
(`spectral_type_source = "orbit"`), not by albedo.

The release gate refuses a build that breaks any of this, and
`python tools/audit_catalog.py asteroid_catalog.parquet` runs the same checks,
plus the ones no limit can decide, on any build or release. It also lists the
heaviest bodies and five reference bodies with spacecraft or radar sizes
(Ceres, Pallas, Vesta, Psyche, Eros), and exits non-zero if any of the five is
not `measured`. That exit code is for a person running it: the publish workflow
runs the audit as information, into the run's summary, so a reference body that
fails there does not stop a release. Only the release gate does.

⚠️ **Possible is not the same as right.** Two things the limits cannot see:

- **A binary's mass is often the system's.** SsODNet gives Pluto 1.447e22 kg,
  the Pluto–Charon system; Pluto alone is 1.303e22, which MP3C has. Both are
  possible, so precedence decides, and `mass_spread` is how to find the rows.
- **Diameters beside a mass are the mass source's, and everywhere else
  JPL's.** For large bodies with no mass, JPL's radiometric diameter may be
  5–15% below the occultation value.

---

## Composition

`TAXONOMY_COMPOSITION` maps a spectral class to a bulk density estimate and
four mass fractions.

```python
ac.TAXONOMY_COMPOSITION["M"]
# {'group': 'X-complex', 'density_est_gcm3': 3.9, 'metal_fraction': 0.5, ...}
```

⚠️ **The fractions do not sum to 1, and must not be made to.** Every real class
sums to strictly less than one — `C` is 0.55, `S` 0.82. The residual is
the part the literature does not resolve. Floor it at a bulk-silicate value or
carry it as unknown; normalising it away invents composition.

**Where a number has a source, the table says which.** Since data contract
1.5.0:

| what | value | backed by |
|---|---|---|
| carbon, hydrated C-complex (B, C, Cb, Cg, Cgh, Ch, F, G) | 0.04 | CI chondrites 3.5–3.9 wt% (Pearson et al. 2006); Bennu 4.5–4.7 and Ryugu ~4.0 (Lauretta et al. 2024). It was 0.20–0.30. |
| metal, S-complex and Q | 0.06 | the mean of LL (3.56 wt%) and L (8.33 wt%) chondrite metal (Jarosewich 1990), the analogues the rows name; it was 0.15–0.20, H-chondrite metal or more |
| metal, V | 0.01 | eucrites carry trace metal only; it was 0.05 |
| Xe and Xk | swapped | most Tholen M-types are Xk (13 of 24, Fornasier et al. 2010), Xe's 0.49 µm band is the E-types', and Carry (2012) pairs Xe with EH enstatite chondrites; the metal-rich row sat under Xe |
| density, Xc | 3.30 | the X-complex value: no density known to 20% supports lower, and the two Xc-types measured that well average 4.86 ± 0.81 (Carry 2012). It was 2.50. |

Every class density is held to [Carry (2012)](https://arxiv.org/abs/1203.4336)'s
average over the bodies measured to 20% (`taxonomy.DENSITY_EVIDENCE`): never
more than 2σ above it, and more than 2σ below it only with a named small body
to say why (B: Bennu 1.19; Sq: Itokawa 1.9; K: one large body measured). The
silicate fractions, carbon outside the hydrated C-complex, and every ice
fraction have no source; no meteorite constrains ice at all.

`Unknown` is the deliberate exception, with all four fractions `None`, so the
residual is the whole body.

**M-type is not a bare metal core.** No M-type has ever been measured near
iron-meteorite density; Psyche is ~3.8–3.9 g/cm³, and the table is set
accordingly. `tests/test_traps.py` asserts it, because "restoring" 0.80/5.30 is
a tempting and wrong edit.

### The precious-metal layer is optional and labelled

`PGM_ENRICHMENT_BY_TYPE` scales the platinum-group fraction of a metal phase by
parent-body differentiation history — core fragments enriched, basaltic crust
depleted, primitive bodies at a chondritic 1.0.

⚠️ **No factor, and not the ~37 ppm baseline, traces to a publication, and the
chondritic 1.0 is wrong in a known direction.** PGMs are siderophile, so an
undifferentiated body's little metal holds nearly all of them: LL-chondrite
metal carries 50–220 ppm (Kargel 1994), 1.4–6× the baseline. The ordinary-
chondrite classes at 1.0 therefore understate their metal's PGM, and more so
since 1.5.0 cut their metal fraction. That is the conservative direction, and
it is left there rather than replaced by another guess.

It is a **valuation layer, not an observation**, and it is the one part of this
package that assumes you care about precious metals. If you do not, ignore the
`comp_pgm_enrichment` column; nothing else depends on it.

---

## Reference tables, without Python

[`reference/taxonomy_composition.csv`](reference/taxonomy_composition.csv) and
[`reference/pgm_enrichment.csv`](reference/pgm_enrichment.csv) are renderings of
the tables in `asteroid_catalog/taxonomy.py`, browsable on GitHub.

The rendering is checked rather than trusted: `tests/test_reference_export.py`
regenerates them and holds them byte for byte against what is committed, so a
table edited without re-exporting turns the suite red instead of leaving two
answers in the repo.

---

## CLI

```bash
asteroid-catalog build --out ./data          # everything, ~1.55 M bodies
asteroid-catalog build --jpl-limit 5000 --no-ssodnet   # a fast sample
asteroid-catalog package ./data --out ./dist --tag data-2026-09-25   # gate + release assets
asteroid-catalog lookup Bennu --catalog ./data/asteroid_catalog.csv
asteroid-catalog taxonomy M                  # one class
asteroid-catalog taxonomy                    # all of them
```

A full build downloads ~435 MB from JPL and a ~850 MB SsODNet parquet (cached
for 7 days by default), and takes a few minutes on a warm connection.

---

## Library hygiene

Importing this package **writes nothing and creates nothing**. No stdout, no
output directory, no cache directory. Progress output is opt-in via
`set_verbose(True)` or the CLI, and `tests/test_library_hygiene.py` checks all
of it in a clean subprocess.

The exception is deliberate: thirteen messages print regardless, because they report
a defect rather than a condition. A diagnostic that has gone quiet reads
exactly like a clean result.

---

## Tests

```bash
pip install -e ".[test]"
pytest -q
ruff check          # unused imports and undefined names; CI runs it too
```

No network and no catalog required. The suite is mostly **the documented traps,
executed** — the designation regex that yields `"2024"` for `"2024 BX1"`, the
float-typed merge key, `str.contains` against regex metacharacters, an int64
designation column, and the NaN handling in the distinct-value optimisation.
Every one of those was a rule written in prose first, and cost a release before
anything ran it.

`tests/test_physics.py` does the same for the physical limits: every case in it
is a row of the `data-2026-09-23` release that was impossible or unrealistic
(De Sitter at 495 g/cm³, Interamnia's one-figure JPL mass, TNO binaries, NEOs
sized off the belt), reduced to the columns that made it wrong. For a built
catalog, `python tools/audit_catalog.py <catalog>` runs the release gate plus
the checks no limit can decide.

---

## Provenance

Extracted from Module 1 of
[economicspace](https://github.com/loggger101/economicspace), an
asteroid-mining profitability pipeline, at `pipeline_version` 1.2.0. The
derivation chain was built there over fourteen releases; it is split out
because nothing in its schema knows what a mine is, and a merged asteroid
catalog with honest provenance is useful to anyone doing population statistics,
survey planning or target selection.

Nothing was re-typed. The package was built by slicing source line ranges, and
the extraction was verified in-process against the original module: reference
data leaf by leaf at raw IEEE bit patterns, and every pure function over a
stride sample of a real 1.55-million-row catalog. economicspace consumes its
published releases as its Stage 1: it downloads a pinned `data-*` release and
does not build.

MIT licensed. See [CITATIONS.md](CITATIONS.md) for what you owe the surveys.
