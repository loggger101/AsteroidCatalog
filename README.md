# asteroid_catalog

One merged, provenance-tagged table of the known asteroids.

Four public surveys, cross-matched on a canonical designation, validated, and
enriched with a cited composition estimate per taxonomy class. About 1.55
million bodies, 46 columns, one CSV.

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
| **merge** | cross-matched on a canonical designation; JPL is the backbone and wins on conflicts, the rest fill gaps |
| **derive** | a diameter for the ~90% of bodies nobody measured one for, from absolute magnitude and an estimated albedo |
| **validate** | quality gates, with every rejection logged and counted |
| **enrich** | bulk density and four mass fractions per Bus-DeMeo class, plus an optional precious-metal layer |

### The sources

| source | contributes | size |
|---|---|---|
| [NASA JPL SBDB](https://ssd-api.jpl.nasa.gov/doc/sbdb_query.html) | orbital elements, H, designations, orbit quality | ~1.55 M bodies |
| [IMCCE SsODNet ssoBFT](https://ssp.imcce.fr/) 🔔 | best-of-literature diameter, albedo, mass, density, rotation, taxonomy | ~1.2 M rows, ~500 MB parquet, cached |
| [NEOWISE V2.0](https://sbn.psi.edu/pds/resource/doi/neowise_2.0.html) 🔔 | thermal-IR diameters and albedos | ~183 k rows |
| [MP3C](https://mp3c.oca.eu/) | physical-properties compilation | varies |

🔔 **These two ask to be cited as a condition of use.** See
[CITATIONS.md](CITATIONS.md).

---

## Three things to understand before you use a built catalog

### 1. It is not reproducible, and that is a property of the data

JPL adds bodies daily. A catalog built today is a different length from one
built last week, so **a result measured against one build must name the build
it used**. Every row carries `catalog_date` and `pipeline_version`.

This is also why `build_catalog` asks before overwriting an existing catalog:
the file it would replace cannot be fetched again.

### 2. Most diameters are derived, not measured

Only 9.6% of bodies have a measured diameter (149,590 of 1,555,667 on a
2026-08 build). The rest are sized from
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

An unreachable survey is tolerated rather than fatal, because MP3C in
particular is regularly unreachable, and a build that dies on it would be
useless. But that means **a source can fail and the run still looks fine**.

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

The exception is deliberate: ten messages print regardless, because they report
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
