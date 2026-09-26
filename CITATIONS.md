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

> Berthier, J., Carry, B., Mahlke, M., and Normand, J. (2023). SsODNet:
> Solar system Open Database Network. *Astronomy & Astrophysics*, 671, A151.
> https://doi.org/10.1051/0004-6361/202244878

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
four mass fractions. The taxonomy itself is Bus-DeMeo; the per-row `notes`
field carries the reasoning, and section 3 below lists the literature each
sourced value rests on. Not every value has one: the silicate fractions,
carbon outside the hydrated C-complex, and every ice fraction are estimates
with no publication behind them, and the module says so.

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

The constant is 2 AU × 10^(V_sun/5) with the Sun's V = −26.762 ± 0.017
(Campins et al. 1985), 1329 ± 10 km, derived in Appendix A of:

> Pravec, P., and Harris, A. W. (2007). *Binary asteroid population. 1.
> Angular momentum content.* Icarus, 190, 250–259.

The V_sun uncertainty is a ~1% systematic in diameter. H is measured; the only
estimated quantity is the geometric albedo `p_V`, which is why every row
produced this way is tagged in `diameter_source` and flagged in
`derived_diameter_is_estimate`. The albedo tables are medians over a release;
`tools/albedo_tables.py` recomputes them from any built catalog.

### PGM enrichment by spectral type

`PGM_ENRICHMENT_BY_TYPE` is a **valuation layer, not an observation**, and it
is the one part of this package that assumes you care about precious metals. It
scales the platinum-group fraction of a metal phase by parent-body
differentiation history: core fragments enriched, basaltic crust depleted,
primitive bodies at a chondritic baseline of 1.0.

The baseline is set to a mean iron-meteorite PGM concentration of ~37 ppm
total PGM + Au in the metal phase. ⚠️ Neither that figure nor any per-type
factor traces to a publication, and the premise that chondritic metal sits at
the same baseline is contradicted: LL-chondrite metal carries 50–220 ppm
precious metals, while iron meteorites range up to several hundred ppm
(Kargel 1994, section 3). The chondritic classes at 1.0 therefore understate
their metal's PGM, which is the conservative direction.

If you are not costing precious metals, ignore the `comp_pgm_enrichment`
column entirely. Nothing else in the package depends on it.

---

## 3. The literature behind the reference values

Each entry names what it backs, so a number in the code can be traced here and
back. Values checked against the publication (or its abstract) when this
section was written; where only the journal is given, the volume and pages
were not.

**Diameters, albedos and absolute magnitudes**

- Fowler, J. W., and Chillemi, J. R. (1992), IRAS Minor Planet Survey,
  PL-TR-92-2049 — the 1329 km constant.
- Pravec, P., and Harris, A. W. (2007), Icarus 190, 250 — its derivation from
  V_sun = −26.762 (Campins et al. 1985).
- Mainzer, A., et al. (2011), *Thermal model calibration for minor planets
  observed with WISE/NEOWISE*, ApJ 736, 100 — ±10% diameter and ±25% albedo
  against radar and spacecraft: the merge's agreement tolerances.
- Pravec, P., et al. (2012), *Absolute magnitudes of asteroids and a revision
  of asteroid albedo estimates from WISE thermal observations*, Icarus 221,
  365 — catalog H too bright by 0.4–0.5 mag near H ≈ 14: the H tolerance, and
  the independent confirmation of the NEOWISE-era albedo offset (README
  section 4).
- Buratti, B. J., et al. (2004), *Deep Space 1 photometry of the nucleus of
  Comet 19P/Borrelly*, Icarus 167, 16 — p_V 0.029 ± 0.006, the darkest
  measured whole body: `ALBEDO_FLOOR`.

**Densities**

- Carry, B. (2012), *Density of asteroids*, Planet. Space Sci. 73, 98
  (arXiv:1203.4336) — the class averages in `DENSITY_EVIDENCE`, the comet and
  TNO averages behind the density floor, and the Hygiea and Interamnia masses.
- Ferrais, M., et al. (2022), *M-type (22) Kalliope: A tiny Mercury*, A&A 662,
  A71 — 4.40 ± 0.46 g/cm³, the densest asteroid measured: the 5.0 ceiling.
- Consolmagno, G. J., Britt, D. T., and Macke, R. J. (2008), *The significance
  of meteorite density and porosity*, Chemie der Erde 68, 1; Macke, R. J., et
  al. (2011), *Density, porosity, and magnetic susceptibility of carbonaceous
  chondrites*, MAPS 46, 1842 — carbonaceous grain densities, CI 2.42 to CB
  5.66: the 3.6 carbonaceous ceiling.
- Macke, R. J., et al. (2010), *Enstatite chondrite density, magnetic
  susceptibility, and porosity*, MAPS 45, 1513 — bulk 3.55, grain 3.66: the Xe
  estimate.
- Pätzold, M., et al. (2016), *A homogeneous nucleus for comet
  67P/Churyumov–Gerasimenko from its gravity field*, Nature 530, 63 — 0.533 ±
  0.006 g/cm³; Thomas, P. C., et al. (2013), Icarus — 9P/Tempel 1, 0.47
  +0.78/−0.24: the density floor.
- Lauretta, D. S., et al. (2019), *The unexpected surface of asteroid (101955)
  Bennu*, Nature 568, 55 — 1.190 ± 0.013 g/cm³; Fujiwara, A., et al. (2006),
  *The rubble-pile asteroid Itokawa as observed by Hayabusa*, Science 312,
  1330 — 1.9 ± 0.13: why the B and Sq estimates sit below Carry's large-body
  averages.

**Composition**

- DeMeo, F. E., et al. (2009), Icarus 202, 160 — the Bus-DeMeo classes.
- Fornasier, S., et al. (2010), *Spectroscopic survey of M-type asteroids*,
  Icarus, doi:10.1016/j.icarus.2010.07.001 — 13 of 24 Tholen M-types are
  Bus-DeMeo Xk: why Xk, not Xe, carries the metal-rich row.
- Pearson, V. K., et al. (2006), *Carbon and nitrogen in carbonaceous
  chondrites*, MAPS 41, 1899 — CI chondrites 3.5–3.9 wt% C.
- Lauretta, D. S., et al. (2024), *Asteroid (101955) Bennu in the laboratory*,
  MAPS, doi:10.1111/maps.14227 — Bennu 4.5–4.7 wt% C, Ryugu ~4.0: the
  C-complex carbon fraction.
- Jarosewich, E. (1990), *Chemical analyses of meteorites: A compilation of
  stony and iron meteorite analyses*, Meteoritics 25, 323 — Fe-Ni-Co metal in
  H 17.8, L 8.33 and LL 3.56 wt%: the S-complex metal fraction.
- Kargel, J. S. (1994), *Metalliferous asteroids as potential sources of
  precious metals*, JGR 99(E10), 21129 — LL-chondrite metal 1.2–5.3% carrying
  50–220 ppm precious metals: the PGM caveat.

**Rotation and the outer Solar System**

- Pravec, P., and Harris, A. W. (2000), *Fast and slow rotation of asteroids*,
  Icarus 148, 12 — the breakup period, 3.3 h / √ρ.
- Holsapple, K. A. (2007), *Spin limits of Solar System bodies: From the small
  fast-rotators to 2003 EL61*, Icarus 187, 500 — gravity dominates strength
  above ~10 km.
- Emery, J. P., Burr, D. M., and Cruikshank, D. P. (2011), *Near-infrared
  spectroscopy of Trojan asteroids: evidence for two compositional groups*,
  AJ 141, 25 — the Trojans' D-type majority.
- Gil-Hutton, R., and Brunini, A. (2008), *Surface composition of Hilda
  asteroids from the analysis of the Sloan Digital Sky Survey colors*, Icarus
  193, 567 — the Hildas' P/D bimodality.

---

## 4. Provenance

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
