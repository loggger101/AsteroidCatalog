# Citations

This package is a **merger**, not a measurement. Almost nothing in a built
catalog was observed by this code: it was observed by the surveys below, and
this package cross-matched, validated and tagged it.

🔔 **Two of the sources ask to be cited as a condition of use.** Those are
marked. If you publish anything derived from a catalog built with this package,
those citations travel with it.

⚠️ **Cite the build, not just the package.** JPL adds bodies daily, so a
catalog built today is a different table from one built last week. Every row
carries `catalog_date` and `pipeline_version` for exactly this reason. Quote
them.

---

## 1. Upstream data sources

Fetched at run time. None is vendored, and none is redistributed here.

### 🔔 IMCCE SsODNet / ssoBFT

Best-of-literature compilation: diameter, albedo, mass, density, rotation and
taxonomy, cross-matched from roughly 3,000 published catalogs. Fetched as a
bulk parquet by `fetch_ssodnet`.

> Berthier, J., Carry, B., Vachier, F., et al. (2023). *Astronomy &
> Astrophysics.* SsODNet: Solar system Open Database Network.

**The service asks explicitly**: "For any use of the table, we ask the citation
of the article: Berthier et al., 2023." It further asks that, where possible,
the bibliographic references of the underlying articles be published too, since
ssoBFT is a compilation of other people's measurements.

- API: `https://ssp.imcce.fr/webservices/ssodnet/api/ssobft`
- Bulk file: `https://ssp.imcce.fr/data/ssoBFT-latest_Asteroid.parquet`

### 🔔 NEOWISE Diameters and Albedos V2.0

Thermal-infrared diameters and albedos for ~150,000 asteroids. Fetched over
IPAC IRSA's TAP service by `fetch_neowise`.

> Mainzer, A., Bauer, J., Cutri, R., Grav, T., Kramer, E., Masiero, J.,
> Sonnett, S., and Wright, E., Eds. (2019). *NEOWISE Diameters and Albedos
> V2.0*, urn:nasa:pds:neowise_diameters_albedos::2.0. NASA Planetary Data
> System. https://doi.org/10.26033/18S3-2Z54

- TAP endpoint: `https://irsa.ipac.caltech.edu/TAP` (table `neowisesbpropv2`)
- Dataset landing page: `https://sbn.psi.edu/pds/resource/doi/neowise_2.0.html`

### NASA JPL Small-Body Database (SBDB)

The orbital and physical backbone: designations, elements, absolute magnitude,
diameter, albedo, taxonomy, the element epoch and the orbit-quality fields.

- Query API: `https://ssd-api.jpl.nasa.gov/sbdb_query.api`
- Field discovery: `https://ssd-api.jpl.nasa.gov/sbdb_query.api?info=field`

⚠️ `condition_code` is the **MPC orbit uncertainty parameter U**, and its
definition belongs to the Minor Planet Center rather than to JPL. It runs 0
(well determined) to 9 (barely constrained).

### MP3C (Observatoire de la Côte d'Azur)

Physical-properties compilation, used as a supplement: best diameter, albedo,
mass and H per body, plus collisional family and proper elements.

- TAP service: `https://dachs.oca.eu/tap`, tables `mp3c_main.best`,
  `mp3c_main.body` and `mp3c_main.name`
- Documentation: `https://mp3c.oca.eu/doc/tap/`
- The service asks that you record the database version you used:
  `SELECT * FROM mp3c_main.version`

MP3C asks to be acknowledged by name rather than through a single paper;
`https://mp3c.oca.eu/citations/` lists publications that have done so.

### Minor Planet Center (cross-source identity)

Designations that JPL's own columns cannot place are resolved through the MPC's
designation links: the `Number`, `Name`, `Principal_desig` and `Other_desigs`
fields of `mpcorb_extended.json.gz`.

- `https://minorplanetcenter.net/Extended_Files/mpcorb_extended.json.gz`

Acknowledge the MPC as the source of the links, for example with the wording
widely used for MPC data (check the MPC's current policy before publishing):

> This research has made use of data and/or services provided by the
> International Astronomical Union's Minor Planet Center.

---

## 2. The reference tables in this repository

### Taxonomy and composition

`TAXONOMY_COMPOSITION` maps a spectral class to a bulk density estimate and
four mass fractions. The taxonomy itself is Bus-DeMeo; the mineralogy per class
is literature mean values, and the per-row `notes` field carries the reasoning.

> DeMeo, F. E., Binzel, R. P., Slivan, S. M., and Bus, S. J. (2009). *An
> extension of the Bus asteroid taxonomy into the near-infrared.* Icarus,
> 202(1), 160–180.

- PDS Small Bodies Node bundle `urn:nasa:pds:ast.bus-demeo.taxonomy`
- Tholen classes are also accepted and mapped, for the bodies where that is
  the only classification available.

⚠️ **The fractions are estimates, and they do not sum to 1.** Every real class
sums to strictly less than one; the residual is the part the literature does
not resolve. Do not normalise it away — floor it at a bulk-silicate value, or
carry it as unknown.

### Diameter from absolute magnitude

    D_km = (1329 / sqrt(p_V)) * 10 ** (-H / 5)

> Fowler, J. W., and Chillemi, J. R. (1992). *IRAS asteroid data processing.*
> In *The IRAS Minor Planet Survey*, Tech. Report PL-TR-92-2049.

The constant 1329 km is the standard value. H is measured; the only estimated
quantity is the geometric albedo `p_V`, which is why every row produced this
way is tagged in `diameter_source` and flagged in
`derived_diameter_is_estimate`.

### PGM enrichment by spectral type

`PGM_ENRICHMENT_BY_TYPE` is a **valuation layer, not an observation**, and it
is the one part of this package that assumes you care about precious metals. It
scales the platinum-group fraction of a metal phase by parent-body
differentiation history: core fragments enriched, basaltic crust depleted,
primitive bodies at a chondritic baseline of 1.0.

The baseline is calibrated to mean iron-meteorite PGM concentration (~37 ppm
total PGM + Au in the metal phase). The per-type factors are conservative
midpoints; the literature variance is large — iridium alone ranges roughly
0.01–19 ppm across iron meteorites.

If you are not costing precious metals, ignore the `pgm_enrichment` column
entirely. Nothing else in the package depends on it.

---

## 3. Provenance

Extracted from Module 1 of
[economicspace](https://github.com/loggger101/economicspace), an
asteroid-mining profitability pipeline, at `pipeline_version` 1.2.0
(commit `1ce0dba`). The tables and the derivation chain were built there over
fourteen releases; they are split out because nothing in their schema knows
what a mine is.

Nothing was re-typed: the package was built by slicing source line ranges, and
the extraction was verified in-process against the original module — reference
data leaf by leaf at raw IEEE bit patterns, and every pure function over a
stride sample of a real 1.55-million-row catalog.
