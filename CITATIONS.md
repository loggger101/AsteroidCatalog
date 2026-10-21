# Citations

This package is a **merger**, not a measurement. Almost nothing in a built
catalog was observed by this code: it was observed by the surveys below, and
this package cross-matched, validated and tagged it.

🔔 **Two of the sources ask to be cited as a condition of use.** Those are
marked. If you publish anything derived from a catalog built with this package,
those citations travel with it.

⚠️ **Cite the build, not just the package**: the release tag, or for a build
of your own the `catalog_date` and `pipeline_version` every row carries. JPL
adds bodies daily, so two builds are two different tables.

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

⚠️ **The fractions do not sum to 1, and must not be normalised**; see
[README > Composition](README.md#composition).

### Diameter from absolute magnitude

    D_km = (1329 / sqrt(p_V)) * 10 ** (-H / 5)

> Fowler, J. W., and Chillemi, J. R. (1992). *IRAS asteroid data processing.*
> In *The IRAS Minor Planet Survey*, Tech. Report PL-TR-92-2049.

The constant is 2 AU × 10^(V_sun/5) with the Sun's V = −26.762 ± 0.017
(Campins et al. 1985), 1329 ± 10 km, derived in Appendix A of:

> Pravec, P., and Harris, A. W. (2007). *Binary asteroid population. 1.
> Angular momentum content.* Icarus, 190, 250–259.

Two more routes give the same constant. The IRAS survey's own Eq. (31) is
D = 10^(3.1236 − 0.2H − 0.5 log p), and 10^3.1236 = 1329.2 (Fowler & Chillemi
1992, chapter 4 p. 43, read off the page image); and SsODNet derives its
albedos with the same relation and constant (Berthier et al. 2023, Eq. 5).

The V_sun uncertainty is a ~1% systematic in diameter. H is measured; the only
estimated quantity is the geometric albedo `p_V`, which is why every row
produced this way is tagged in `diameter_source` and flagged in
`derived_diameter_is_estimate`. The albedo tables are medians over a release;
`tools/albedo_tables.py` recomputes them from any built catalog.

### PGM enrichment by spectral type

`PGM_ENRICHMENT_BY_TYPE` is a **valuation layer, not an observation**; what it
does is in [README > Composition](README.md#the-precious-metal-layer-is-optional-and-labelled).
⚠️ Neither its baseline (~37 ppm total PGM + Au in the metal, a mean
iron-meteorite figure) nor the differentiated classes' factors trace to a
publication. Since 1.9.0 the S complex, Q, K and L are computed: CI bulk PGM
+ Au (Lodders 2010, Table 2) over each class's metal fraction, over the
baseline. Kargel (1994, section 3) is the second route: LL-chondrite metal
carries 50–220 ppm precious metals (the S complex computes to 57), while iron
meteorites range up to several hundred ppm.

---

## 3. The literature behind the reference values

Each entry names what it backs, so a number in the code can be traced here and
back. Values checked against the publication (or its abstract) when this
section was written; where only the journal is given, the volume and pages
were not.

The entries added in data contract 1.6.0 came through
[General_Research](https://github.com/loggger101/General_Research), the
evidence registry that extracts each source's numbers with their page
locations and records where they contradict this repo
(`revision_candidates.csv`). Each value used here was re-read from the paper's
PDF, or from its Crossref abstract where marked, except where an entry says
otherwise; volumes and pages are Crossref's.

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
- Berthier, J., et al. (2023), A&A 671, A151 (the SsODNet citation above) —
  also Eq. (5), the same 1329 km relation; Fig. 5, X-complex densities bimodal
  by albedo (P sub-class, mean p_V 0.044, below 2000 kg/m³; M, 0.129, above),
  the first route to the X split;
  and ssoBFT at publication, 591 fields for 1,223,984 bodies.

**Densities**

- Carry, B. (2012), *Density of asteroids*, Planet. Space Sci. 73, 98
  (arXiv:1203.4336) — the class averages in `DENSITY_EVIDENCE` (Table 3), the
  comet and TNO averages behind the density floor, and the Hygiea and
  Interamnia masses; Table 2's meteorite bulk densities (H 3.42, L 3.36,
  LL 3.22, CI 1.60, CM 2.25, CO 3.03, CV 2.79, CK 2.85, EH 3.47, HED 3.25,
  pallasite 4.76, mesosiderite 4.35 g/cm³) are `METEORITE_ANALOGUE_GCM3`; and
  Table 1's 617 Patroclus, 0.88 ± 0.17, is one of the P-type densities.
- Hanuš, J., et al. (2017), *Volumes and bulk densities of forty asteroids
  from ADAM shape modeling*, A&A 601, A114 — 87 Sylvia, "the only P-type
  asteroid in our sample", 1.39 ± 0.08 (the P density); and in its Table 6,
  433 Eros 2.67 ± 0.10 from NEAR (Veverka et al. 2000), the S macroporosity
  check. (General_Research files it as `adam_2017`.)
- Yeomans, D. K., et al. (2000), *Radio science results during the
  NEAR-Shoemaker spacecraft rendezvous with Eros*, Science 289, 2085 —
  Eros's mass, 6.687e15 kg, and its volume, 2503 ± 25 km³: since 1.9.0 the
  catalog's Eros diameter, the 16.846 km sphere of that volume
  (`merge.SHAPE_MODEL_VOLUMES`), so its density is 2.67. The volume as JPL
  SBDB quotes it from this paper (diameter 16.84 ± 0.06, "sphere having the
  measured volume", density 2.67 ± 0.03), and the mass as SsODNet's ssoCard
  cites it; the paper itself not re-read here. General_Research rc-174.
- Park, R. S., et al. (2025), *A small core in Vesta inferred from Dawn's
  observations*, Nat. Astron. 9, 824 (CC BY) — p. 830: Vesta's volume (7.49
  ± 0.01) × 10⁷ km³ from the SPC shape, mass 2.59028 × 10²⁰ kg, bulk density
  3.458 ± 0.005 g/cm³. Since 1.10.0 the catalog's Vesta diameter, 522.99 km.
  Read here; JPL SBDB quotes the same paper (522.77 km, 3.460).
- Daly, M. G., et al. (2020), *Hemispherical differences in the shape and
  topography of asteroid (101955) Bennu*, Sci. Adv. 6, eabd3649 (CC BY) —
  Table 1: OLA shape volume 0.061354 ± 0.00006 km³, bulk density 1194 ± 3
  kg/m³, average radius 242.22 m (which JPL SBDB doubles into its 0.48444
  km). Since 1.10.0 the catalog's Bennu diameter, 0.48934 km. Read here.
- Kretlow, M. (2022), *An astrometric mass estimate for asteroid (223) Rosa*,
  A&A 668, A141 — Rosa 1.2 ± 0.5 g/cm³, and ~1.3 as the typical P-type
  density: the P density.
- Dziadura, K., et al. (2023), *The Yarkovsky effect and bulk density of
  near-Earth asteroids from Gaia DR3*, A&A 680, A77 — Yarkovsky densities of
  57 NEAs (Table A.1): S-types median 1.37 over 23, Q-types 1.47 over 9, at
  most 2.79 (1862 Apollo); 2100 Ra-Shalom, K, 1.28 +0.33/−0.51. The `small`
  entries of `DENSITY_EVIDENCE` and the Q density. Read by General_Research
  (R73) from the CC BY publisher PDF; not re-read here.
- Chesley, S. R., et al. (2014), *Orbit and bulk density of the OSIRIS-REx
  target asteroid (101955) Bennu*, Icarus 235, 5 — 1260 ± 70 kg/m³ from the
  Yarkovsky drift, before the spacecraft, and macroporosity 40 ± 10% against
  likely analogue meteorites: the second Bennu route, and the C-complex
  macroporosity check.
- Siltala, L., and Granvik, M. (2021), *Mass and density of asteroid (16)
  Psyche*, ApJL 909, L14 — 3.88 ± 0.25 g/cm³ from ten close encounters.
- Farnocchia, D., et al. (2024), *Mass, density, and radius of asteroid (16)
  Psyche from high-precision astrometry*, AJ 168, 21 — GM 1.601 ± 0.017
  km³/s², volume 5.75 × 10⁶ km³, 4172 ± 145 kg/m³ (Crossref abstract; the GM
  over the volume reproduces the density). With Siltala & Granvik and
  SsODNet's 4.14, the Psyche range 3.8–4.2 in the M and Xk rows.
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
- Fornasier, S., Clark, B. E., and Dotto, E. (2011), *Spectroscopic survey of
  X-type asteroids*, Icarus 214, 131 — p. 5, the convention for Tholen's
  classes: an X-type with a measured albedo is E above p_V 0.3, M from 0.1 to
  0.3, P below 0.1. `taxonomy.X_SPLIT_BOUNDS`; on the release they reproduce
  80 of JPL's 83 E, M and P labels.
- Fornasier, S., et al. (2010), *Spectroscopic survey of M-type asteroids*,
  Icarus, doi:10.1016/j.icarus.2010.07.001 — 13 of 24 Tholen M-types are
  Bus-DeMeo Xk: why Xk, not Xe, carries the metal-rich row.
- Pearson, V. K., et al. (2006), *Carbon and nitrogen in carbonaceous
  chondrites*, MAPS 41, 1899 — CI chondrites 3.5–3.9 wt% C.
- Lauretta, D. S., et al. (2024), *Asteroid (101955) Bennu in the laboratory*,
  MAPS, doi:10.1111/maps.14227 — Bennu 4.5–4.7 wt% C, Ryugu ~4.0: the
  C-complex carbon fraction.
- Glavin, D. P., et al. (2025), *Abundant ammonia and nitrogen-rich soluble
  organic matter in samples from asteroid (101955) Bennu*, Nat. Astron. 9,
  199 — Bennu's total C re-measured on their own extracts, 4.5–4.7 wt%; and
  in Extended Data Table 1, Tagish Lake 4.11 ± 0.12 and 4.13 ± 0.12 wt% C and
  Tarda 3.65–3.78, the D, Z, T, P carbon fraction since 1.10.0 (re-read from
  the page; General_Research rc-075).
- Wong, I., et al. (2024), *JWST near-infrared spectroscopy of the Lucy
  Jupiter Trojan flyby targets: evidence for OH absorption, aliphatic
  organics, and CO2*, PSJ 5, 87 (arXiv:2311.11531) — no
  surface water ice, modelled ice depleted to ~10 m depth: why 1.10.0 keeps
  D and P ice rather than a comet's 0.3–0.4 (General_Research rc-013). Read
  by General_Research (arXiv copy), not re-read here.
- Lodders, K. (2010), *Solar system abundances of the elements*, Astrophys.
  Space Sci. Proc., 379–417 (arXiv:1010.2746) — Table 2, CI chondrites: C
  34,800 ± 3,500 ppm (3.48 wt%), the carbon fraction; Ru 0.686, Rh 0.139,
  Pd 0.558, Os 0.493, Ir 0.469, Pt 0.947 ppm, 3.29 ppm in all, and Au
  0.146: 3.438 ppm PGM+Au, from which 1.9.0 computes the S-complex, Q, K and
  L PGM factors. Lodders, K., and Palme, H. (2009), 72nd Meteoritical Society
  meeting abstract, Table 1, gives the same seven values; both re-read from
  the PDFs.
- Yokoyama, T., et al. (2023), *Samples returned from the asteroid Ryugu are
  similar to Ivuna-type carbonaceous meteorites*, Science 379, eabn7850 —
  Ryugu total C 4.63 ± 0.23 wt%. Read by General_Research (R73) from the
  author's version; not re-read here.
- Mahlke, M., Carry, B., and Mattei, P.-A. (2022), *Asteroid taxonomy from
  cluster analysis of spectrometry and albedo*, A&A 665, A26 — the scheme
  SsODNet prefers, so its classes (Z, and the P, M and E labels) reach the
  catalog through ssoBFT.
- Jarosewich, E. (1990), *Chemical analyses of meteorites: A compilation of
  stony and iron meteorite analyses*, Meteoritics 25, 323 — Fe-Ni-Co metal in
  H 17.8, L 8.33 and LL 3.56 wt%: the S-complex metal fraction.
- Kargel, J. S. (1994), *Metalliferous asteroids as potential sources of
  precious metals*, JGR 99(E10), 21129 — LL-chondrite metal 1.2–5.3% carrying
  50–220 ppm precious metals: the PGM caveat.

**Mineral phases (`comp_phases`, 1.7.0; `comp_phases_detailed`, 1.8.0)**

Cited here as `asteroid_catalog/mineralogy.py` cites them, which is where each
number is tied to the source behind it. ⚠️ **Not re-read from the papers for
this section**, unlike the entries above: volumes and pages are as the module
gives them, and the module lists what has no source at all.

- Dunn, T. L., Cressey, G., McSween, H. Y., and McCoy, T. J. (2010), MAPS 45,
  123 — XRD modal abundances of L and LL chondrites: the S-complex silicate
  split, troilite and chromite.
- King, A. J., Schofield, P. F., Howard, K. T., and Russell, S. S. (2015), GCA
  165, 148 — Orgueil and Ivuna by XRD: the CI phases, and pyrrhotite with
  lesser pentlandite as their sulfide.
- Howard, K. T., Alexander, C. M. O'D., Schrader, D. L., and Dyl, K. A.
  (2015), GCA 149, 206 — the CM phases.
- Alexander, C. M. O'D., et al. (2007), GCA 71, 4380 — insoluble vs soluble
  organic carbon.
- Mittlefehldt, D. W. (2015), Chemie der Erde 75, 155 — the HED phases.
- Sunshine, J. M., et al. (2008), Science 320, 514 — L-types' CAI content.
- Rubin, M., et al. (2019), MNRAS 489, 594 — 67P's bulk volatiles.
- Hiroi, T., et al. (2001), Science 293, 2234 — Tagish Lake as the D-type
  analogue, and so which accessories D, Z and P carry. Not their amounts:
  Hiroi gives only Tagish Lake's carbon (4–5 wt%) and defers the composition
  to Brown, P. G., et al. (2000), Science 290, 320, which is qualitative
  (magnetite far more abundant than in most CMs). The magnetite ~5, sulfide
  ~3 and carbonate ~3 wt% have no source; the module lists them so. Both
  papers read by General_Research (R155, R160; rc-085), not re-read here.
- Jones, R. H., McCubbin, F. M., Dreeland, L., Guan, Y., Burger, P. V., and
  Shearer, C. K. (2014), GCA 132, 120 — merrillite and chlorapatite in LL
  chondrites: the 1.8.0 phosphates.
- Keil, K. (1968), JGR 73, 6945 — the enstatite-chondrite sulfides
  (niningerite, oldhamite, daubreelite): Xe's 1.8.0 split.
- Keil, K. (2010), Chemie der Erde 70, 295 — aubrites, and their oldhamite:
  E's 1.8.0 split.
- Jarosewich (1990), above — the metal fractions behind the 1.8.0 alloy
  split: metal falls from H to LL while bulk Ni barely moves, so the metal of
  an LL-leaning S-type is Ni-rich, taenite and tetrataenite rather than
  kamacite.

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
[economicspace](https://github.com/loggger101/economicspace); see
[README > Provenance](README.md#provenance).
