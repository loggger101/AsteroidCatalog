# asteroid_catalog

One merged, provenance-tagged table of the known asteroids.

Four public surveys, cross-matched body by body, validated, and enriched with a
cited composition estimate per taxonomy class. About 1.57 million bodies, one
row each, one CSV. A body several sources know carries all of their data, and
says which source supplied each value and whether the sources agree.

```bash
pip install git+https://github.com/loggger101/AsteroidCatalog@v0.1.0
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
| **merge** | every row re-keyed onto JPL's designation for that body, duplicates combined; JPL is the backbone and wins on conflicts, the rest fill gaps, and every measured value records who supplied it and whether the sources agree |
| **derive** | a diameter for the ~90% of bodies nobody measured one for, from absolute magnitude and an estimated albedo |
| **validate** | quality gates, with every rejection logged and counted |
| **enrich** | bulk density and four mass fractions per Bus-DeMeo class, plus an optional precious-metal layer |

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

## Four things to understand before you use a built catalog

### 1. It is not reproducible, and that is a property of the data

JPL adds bodies daily. A catalog built today is a different length from one
built last week, so **a result measured against one build must name the build
it used**. Every row carries `catalog_date` and `pipeline_version`.

This is also why `build_catalog` asks before overwriting an existing catalog:
the file it would replace cannot be fetched again.

### 2. Most diameters are derived, not measured

Only 9.6% of bodies have a measured diameter (149,740 of 1,566,616 on a
2026-09-22 build). The rest are sized from
absolute magnitude and an **estimated** albedo:

    D_km = (1329 / sqrt(p_V)) * 10 ** (-H / 5)

H is measured; `p_V` is not. So a derived diameter is uncertain by roughly the
square root of the albedo error — and a **mass** derived from it by that cubed.

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
| `<stem>_provider` | the source the value came from (JPL, then SsODNet, NEOWISE, MP3C) |
| `<stem>_n_sources` | how many sources report a value |
| `<stem>_spread` | max/min − 1 across them (max − min in magnitudes for H) |
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
10^(0.4 × 0.28) ≈ 1.29. So the `albedo` column, JPL's by precedence, is the
NEOWISE-era value and is not consistent with the H beside it. The catalog does
not re-derive it; `albedo_spread` and `albedo_provider` are there to find the
rows where it matters.

---

## Composition

`TAXONOMY_COMPOSITION` maps a spectral class to a bulk density estimate and
four mass fractions.

```python
ac.TAXONOMY_COMPOSITION["M"]
# {'group': 'X-complex', 'density_est_gcm3': 3.9, 'metal_fraction': 0.5, ...}
```

⚠️ **The fractions do not sum to 1, and must not be made to.** Every real class
sums to strictly less than one — `C` is 0.76, `Cgh` is 0.73. The residual is
the part the literature does not resolve. Floor it at a bulk-silicate value or
carry it as unknown; normalising it away invents composition.

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

It is a **valuation layer, not an observation**, and it is the one part of this
package that assumes you care about precious metals. If you do not, ignore the
`pgm_enrichment` column; nothing else depends on it.

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
asteroid-catalog lookup Bennu --catalog ./data/asteroid_catalog.csv
asteroid-catalog taxonomy M                  # one class
asteroid-catalog taxonomy                    # all of them
```

A full build downloads ~435 MB from JPL and a ~500 MB SsODNet parquet (cached
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
```

No network and no catalog required. The suite is mostly **the documented traps,
executed** — the designation regex that yields `"2024"` for `"2024 BX1"`, the
float-typed merge key, `str.contains` against regex metacharacters, an int64
designation column, and the NaN handling in the distinct-value optimisation.
Every one of those was a rule written in prose first, and cost a release before
anything ran it.

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
stride sample of a real 1.55-million-row catalog. economicspace consumes this
package as its Stage 1.

MIT licensed. See [CITATIONS.md](CITATIONS.md) for what you owe the surveys.
