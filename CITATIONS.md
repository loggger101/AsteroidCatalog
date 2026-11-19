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
(well determined) to 9 (barely constrained). The MPC defines it, and how it is
computed, in "Uncertainty Parameter U and Orbit Quality Codes"
(`https://docs.minorplanetcenter.net/mpc-ops-docs/orbits/uncertainty-parameter/`),
which also cautions against reading U as a prediction of a near-Earth object's
future positional uncertainty. The JPL field table above remains the reference
for the column itself.

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
  the only classification available. The original scheme:

> Tholen, D. J. (1984). *Asteroid taxonomy from cluster analysis of
> photometry.* Ph.D. dissertation, University of Arizona.
> <https://repository.arizona.edu/handle/10150/187738> (hdl:10150/187738)

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

Its two components come from:

> Campins, H., Rieke, G. H., and Lebofsky, M. J. (1985). *Absolute
> calibration of photometry at 1 through 5 microns.* The Astronomical
> Journal, 90, 896. <https://doi.org/10.1086/113799> — V_sun = −26.762 ±
> 0.017 (p. 898).

> International Astronomical Union (2012). *Resolution B2 on the
> re-definition of the astronomical unit of length.* XXVIII General Assembly.
> <https://syrte.obspm.fr/IAU_resolutions/Res_IAU2012_B2.pdf> — 1 AU =
> 149,597,870,700 m exactly: `physics.AU_KM`.

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
⚠️ Neither its baseline (~37 ppm total PGM + Au in the metal, a model
assumption standing for iron-meteorite metal) nor the differentiated classes'
factors trace to a publication; the factors are scenarios. Since 1.9.0 the S complex, Q, K and L are computed: CI bulk PGM
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
- Mainzer, A., et al. (2011), *NEOWISE studies of spectrophotometrically
  classified asteroids: preliminary results*, ApJ 741, 90 — Table 1, Tholen M:
  median p_V 0.125, n = 33, SD 0.037, beside the catalog's 0.133 (n = 139);
  visible-selected samples bias class albedos upward. A comparator, not a
  replacement (General_Research rc-386, R520; not re-read here).
- Pravec, P., et al. (2012), *Absolute magnitudes of asteroids and a revision
  of asteroid albedo estimates from WISE thermal observations*, Icarus 221,
  365 — catalog H too bright by 0.4–0.5 mag near H ≈ 14: the H tolerance, and
  the independent confirmation of the NEOWISE-era albedo offset (README
  section 4).
- Buratti, B. J., et al. (2004), *Deep Space 1 photometry of the nucleus of
  Comet 19P/Borrelly*, Icarus 167, 16 — p_V 0.029 ± 0.006, the darkest
  measured whole body: `ALBEDO_FLOOR`.
- Buratti, B., and Veverka, J. (1984), *Voyager photometry of Rhea, Dione,
  Tethys, Enceladus and Mimas*, Icarus 58(2), 254–264,
  <https://doi.org/10.1016/0019-1035(84)90042-3> — Enceladus p_V 1.04 ±
  0.15, Bond albedo 0.9 ± 0.1 (publisher abstract); and Verbiscer, A.,
  French, R., Showalter, M., and Helfenstein, P. (2007), *Enceladus: cosmic
  graffiti artist caught in the act*, Science 315(5813), 815,
  <https://doi.org/10.1126/science.1134681> — E-ring satellites' mean
  geometric albedos "approximate or exceed unity". Why `ALBEDO_CEILING` is
  called a policy and not physics. They show a geometric albedo above 1 is
  physically possible; they do not show that a radiometric catalog fit at or
  above 1.0 is valid, which is what the ceiling screens (General_Research
  rc-780).
- Santos-Sanz, P., Lellouch, E., Fornasier, S., et al. (2012), *"TNOs are
  Cool": A survey of the trans-Neptunian region IV. Size/albedo
  characterization of 15 scattered disk and detached objects observed with
  Herschel-PACS*, A&A 541, A92, <https://doi.org/10.1051/0004-6361/201118541>
  — Table 6, p. 12: p_V falls with H across its 15 scattered-disk and
  detached objects (ρ = −0.88). This is the size-albedo trend
  `derive.ALBEDO_BEYOND_JUPITER_BY_H` mentions, as a sample-specific
  comparator only: the sample is small, and p. 3 says target selection
  favoured bright (low-H) objects. The bins' values are release medians, not
  taken from it (General_Research rc-779).
- Berthier, J., et al. (2023), A&A 671, A151 (the SsODNet citation above) —
  also Eq. (5), the same 1329 km relation; Fig. 5, X-complex densities bimodal
  by albedo (P sub-class, mean p_V 0.044, below 2000 kg/m³; M, 0.129, above),
  the first route to the X split;
  and ssoBFT at publication, 591 fields for 1,223,984 bodies.
- Campins et al. (1985) and IAU 2012 Resolution B2, in section 2 above — V_sun
  and the AU inside the 1329 km constant (General_Research rc-781).
- Trilling, D. E., et al. (2010), *ExploreNEOs. I. Description and first
  results from the Warm Spitzer Near-Earth Object Survey*, AJ 140(3),
  770–784, <https://doi.org/10.1088/0004-6256/140/3/770> (arXiv:1007.1009) —
  arXiv v1 printed p. 7: S asteroids in general have albedos above 0.15, C asteroids below
  0.10. Context for `enrich._class_from_albedo`'s 0.10 split, which is a coarse
  fallback convention: the paper leaves 0.10–0.15 unassigned, and does not
  support calling every p_V ≥ 0.10 body S. The 84.0% / 85.2% accuracies in the
  docstring are this catalog's own check, not the paper's (General_Research
  rc-695).

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
- Thomas, P. C., et al. (2000), *The Shape of Eros from NEAR Imaging Data*,
  Icarus 145(2), 348-350, <https://doi.org/10.1006/icar.2000.6406> (SsODNet
  BibRef 2000Icar..145..348T) — the source ssoBFT gives for its 17.6 km Eros
  diameter, which is not a volume-equivalent sphere and which the catalog
  replaces with Yeomans et al.'s volume (`merge.SHAPE_MODEL_VOLUMES`). Cited
  as ssoBFT attributes it; the paper itself not read here (General_Research
  rc-841).
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
- Elkins-Tanton, Asphaug, Bell III, et al. (2020),
  *Observations, meteorites, and models: A preflight assessment of the
  composition and formation of (16) Psyche*, JGR Planets 125, e2019JE006296,
  <https://doi.org/10.1029/2019JE006296> — the Psyche density and
  metal-content scope the M row's note cites: between ~30 and ~60 vol% metal
  (conclusions, PDF p. 19). A preflight review of one body, not a class value
  (General_Research rc-665).
- Rubin and Burbine (2026), *No exotic matter in asteroids*,
  Eur. Phys. J. Plus 141, 175, <https://doi.org/10.1140/epjp/s13360-026-07415-z>
  — §2.2, p. 175: ~8 g/cm³, a non-porous Fe-Ni core fragment (~90 wt% Fe,
  ~10 wt% Ni), is the approximate upper limit on an asteroid's density.
  `physics._IRON_CEILING`, the release gate's 8.0, is that rounded
  composition limit; the named groups are screened by their stricter 3.6 and
  5.0 ceilings (General_Research rc-609).
- Ferrais, M., et al. (2022), *M-type (22) Kalliope: A tiny Mercury*, A&A 662,
  A71 — 4.40 ± 0.46 g/cm³, the densest asteroid measured: the 5.0 ceiling.
- Consolmagno, G. J., Britt, D. T., and Macke, R. J. (2008), *The significance
  of meteorite density and porosity*, Chemie der Erde 68, 1; Macke, R. J., et
  al. (2011), *Density, porosity, and magnetic susceptibility of carbonaceous
  chondrites*, MAPS 46, 1842 — carbonaceous grain densities, CI 2.42 to CB
  5.66: the 3.6 carbonaceous ceiling. ⚠️ Macke et al. measure CO grain
  densities of 2.99–3.78 over 33 stones (p. 1854; Lance CO3.5 3.78 ± 0.04,
  Table 1), and a Type 3 average of 3.63, maximum 3.74 (Table 2), so 3.6 is
  not the densest CO/CV grain density. It is kept as a provisional screen:
  these are meteorite grain densities, not asteroid bulk densities, and they
  do not by themselves give a replacement (General_Research rc-610).
- Macke, R. J., et al. (2010), *Enstatite chondrite density, magnetic
  susceptibility, and porosity*, MAPS 45, 1513 — bulk 3.55, grain 3.66: the Xe
  estimate.
- Pätzold, M., et al. (2016), *A homogeneous nucleus for comet
  67P/Churyumov–Gerasimenko from its gravity field*, Nature 530, 63 — 0.533 ±
  0.006 g/cm³; Thomas, P., A'Hearn, M., Veverka, J., et al. (2013), *The
  nucleus of Comet 9P/Tempel 1: Shape and geology from two flybys*, Icarus
  222(2), 453-466, <https://doi.org/10.1016/j.icarus.2012.02.037> (NASA NTRS
  20140010174) — 9P/Tempel 1, 470 +780/−230 kg/m³ (p. 455), so 0.47
  +0.78/−0.23 g/cm³ and a lower end of 0.24: the density floor. Until 0.13.6
  this read −0.24, the lower end written as the uncertainty (General_Research
  rc-847, rc-848).
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
  C-complex carbon fraction. Also p. 2481: the sample holds 0.84–0.95 wt% H,
  at most 7.5–8.5 wt% H2O, beside the B row's 0.20 ice (under review,
  General_Research rc-334).
- Kaplan et al. (2026), *Water and hydroxyl on asteroid Bennu*, MAPS (early
  view), and King, A. J., et al. (2026), MAPS 61, 1077, p. 1088 — Bennu's
  hydration mostly OH, interlayer water up to ~2 wt%: the same review
  (rc-334). Read by General_Research, not re-read here.
- Smith, C. L., et al. (2004), MAPS 39, 2009, p. 2028 — CV chondrites
  0.3–1.8 wt% C, mean 0.77: beside K's unsourced 0.08 (under review, rc-350).
- DeMeo, F. E., and Carry, B. (2015), *The compositional structure of the
  asteroid belt*, Asteroids IV, 13 — pp. 16–18, the X complex is
  compositionally degenerate (rc-346); Table 1, Gaffey's S subclasses against
  Bus-DeMeo labels, with no mass shares (rc-419).
- Kwon, Y. G., Hasegawa, Fornasier, Ishiguro and Agarwal (2022), *Probing the surface environment of large T-type asteroids*, A&A
  666, A173, <https://doi.org/10.1051/0004-6361/202243816> — large T-types
  match CI better than Tagish Lake, whose carbon T borrows (rc-353).
- Scott, E. R. D., et al. (2015), Asteroids IV, 573, p. 578 — A-type olivine
  ~70–90% (magnesian) to monomineralic (ferroan) (rc-351).
- Abell, P. A., and Gaffey, M. J. (2000), LPSC XXXI — 349 Dembowska OPX:OL
  45:55 (rc-348).
- Cloutis, E. A., et al. (2006), MAPS 41, 1147, p. 1159 — 3628 Božněmcová,
  clinopyroxene- and plagioclase-rich (rc-352).
- Lindgren, P., et al. (2020), GCA 289, 69, Table 2 — ALH 83100 pyrrhotite 0.9,
  pentlandite 1.2 vol% (rc-380).
- Grady, M. M., et al. (2002), MAPS 37, 713 — ~2% of Tagish Lake's organic
  matter solvent soluble, against the model's 0.60 (rc-384).
  These nine were read by General_Research as comparators for unsourced
  numbers; none supplies a replacement, and none is re-read here.
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
  author's version; not re-read here. Also p. 8: 6.84 wt% H2O, 6.54 of it
  structural OH: the comparator for the C row's 0.15 ice fraction, which
  stands for bound water (General_Research rc-367, R501).
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
- Cannon, K. M., Gialich, M., and Acain, J. (2023), *Precious and structural
  metals on asteroids*, Planet. Space Sci. 225, 105608 (CC BY-NC-ND) — Table
  2: measured iron-meteorite PGM (six PGMs, no Au) median 40.78 ppm, 10th–90th
  percentile 14.70–107.86 ppm; p. 6, no remote way to place an asteroid in
  that distribution. Why the 37 ppm baseline is called an assumption and the
  class factors scenarios (General_Research rc-368, rc-369). Read by
  General_Research (R502, R503), not re-read here.

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
  lesser pentlandite as their sulfide. Its modes are by volume (Table 1,
  p. 154: phyllosilicate 83.0 and 82.5 vol%, olivine 1.0 and 2.0); the
  0.95 / 0.05 silicate split is an estimate, not a conversion (General_Research
  rc-344, R478).
- Howard, K. T., Alexander, C. M. O'D., Schrader, D. L., and Dyl, K. A.
  (2015), GCA 149, 206 — the CM phases. The 0.85 / 0.10 / 0.05 silicate split
  is an estimate; Lee, M. R., and Lindgren, P. (2016), MAPS 51, 1003, Table 4,
  reproduce Murchison's XRD modes (Howard et al. 2011), 72.5 vol%
  phyllosilicate and 23.4 olivine + orthopyroxene, as a one-sample comparator
  (General_Research rc-345, R479).
- Harrison et al. (2025), *Iron and copper sulfides in asteroid Ryugu:
  comparison to CI and CY chondrites*, MAPS 60, 506 (CC BY) — p. 510: CI
  sulfide mostly pyrrhotite, pentlandite rare, no ratio given. Why the CI
  70 / 30 sulfide split is called an estimate (General_Research rc-418,
  R552).
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
  Comparators for those amounts, neither a class value (General_Research
  rc-343): Izawa, M. R. M., et al. (2010), MAPS 45, 675, Table 3 — Tagish
  Lake samples range magnetite 6–17, siderite 4–24, pyrrhotite 10–18 wt%;
  Schrader, D. L., et al. (2024), GCA 380, 48, Table 2 — one carbonate-rich
  sample, Ca-carbonate 3.20, magnetite 4.59, Fe sulfide 1.86 vol%.
- Jones, R. H., McCubbin, F. M., Dreeland, L., Guan, Y., Burger, P. V., and
  Shearer, C. K. (2014), GCA 132, 120 — merrillite and chlorapatite in LL
  chondrites: the 1.8.0 phosphates.
- Keil, K. (1968), JGR 73, 6945 — the enstatite-chondrite sulfides
  (niningerite, oldhamite, daubreelite): Xe's 1.8.0 split.
- Keil, K. (2010), Chemie der Erde 70, 295 — aubrites, and their oldhamite:
  E's 1.8.0 split.
- Grady, M., Pratesi, G., and Moggi Cecchi, V. (2013), *Aubrites*, ch. 11 of
  *Atlas of Meteorites*, Cambridge University Press, 261-271,
  <https://doi.org/10.1017/9781139016308.012> — enstatite 75-98 vol% of
  aubrite whole rock: the comparator for E's scenario 95 / 3 / 2 silicate
  split, by volume and by analogy (General_Research rc-615).
- Jarosewich (1990), above — the metal fractions behind the 1.8.0 alloy
  split: metal falls from H to LL while bulk Ni barely moves, so the metal of
  an LL-leaning S-type is Ni-rich, taenite and tetrataenite rather than
  kamacite.
- Comparators named in 0.13.2's comments (General_Research rc-444 to
  rc-496). Each keeps the sample or surface scope it was cited for: none is
  a class value, and none establishes a class-level bulk composition or water
  fraction. Full references since 0.13.3 (General_Research rc-797, rc-798,
  rc-799, rc-804):
  - Beck, P., et al. (2021), *"Water" abundance at the surface of C-complex
    main-belt asteroids*, Icarus 357, 114125,
    <https://doi.org/10.1016/j.icarus.2020.114125> — C-complex surface water.
  - Kwon, Y. G., et al. (2022), *Probing the surface environment of large
    T-type asteroids*, A&A 666, A173 (above) — T-types.
  - Jones, T. D., et al. (1990), *The composition and origin of the C, P, and
    D asteroids: Water as a tracer of thermal evolution in the outer belt*,
    Icarus 88(1), 172–192, <https://doi.org/10.1016/0019-1035(90)90184-B> —
    P and D ice.
  - McAdam, M., et al. (2024), *Detection of hydration on nominally anhydrous
    S-complex main belt asteroids*, PSJ 5, 254,
    <https://doi.org/10.3847/PSJ/ad888d> — S-type 3 µm bands.
  - Rivkin, A. S., et al. (2000), *The nature of M-class asteroids from 3-µm
    observations*, Icarus 145(2), 351–368,
    <https://doi.org/10.1006/icar.2000.6354>; and Rivkin, A. S., et al.
    (1995), *3-µm spectrophotometric survey of M- and E-class asteroids*,
    Icarus 117(1), 90–100, <https://doi.org/10.1006/icar.1995.1144> — M and E
    hydration.
  - Dunn, T. L., et al. (2010), *Analysis of ordinary chondrites using powder
    X-ray diffraction: 1. Modal mineral abundances*, MAPS 45(1), 123–134,
    <https://doi.org/10.1111/j.1945-5100.2009.01011.x>, Table 5 — ordinary
    chondrite modes.
  - Martin et al. (2013), *REE and Hf distribution among mineral phases in the
    CV–CK clan*, GCA 120, 496–513,
    <https://doi.org/10.1016/j.gca.2013.07.006>, Table 2 — CV and CK maps.
  - de Kleer, K., Ehlmann, Jacobson, Wong, Tissot, Martin, Lane and King
    (2026), *The surface mineralogy of the spinel-rich asteroids from
    mid-infrared spectroscopy with JWST*, PSJ 7, 36,
    <https://doi.org/10.3847/PSJ/ae374e> — surface spectra of five L-types;
    it gives no bulk spinel or CAI share.
  - Li, S., and Milliken, R. E. (2015), *Estimating the modal mineralogy of
    eucrite and diogenite meteorites using visible–near infrared reflectance
    spectroscopy*, MAPS 50(11), 1821–1850,
    <https://doi.org/10.1111/maps.12513> — sample-level eucrite and diogenite
    modes; it does not derive the V-type mass vector.
  - Howard, K. T., Benedix, Bland and Cressey (2009), *Modal mineralogy of CV3
    chondrites by PSD-XRD: Mineralogic insights into a complex evolutionary
    history*, 40th LPSC, Abstract 1235,
    <https://www.lpi.usra.edu/meetings/lpsc2009/pdf/1235.pdf> — CV3 sulfide.
  - Zhang, P., Li, Y., Zhang, J., et al. (2023), *Compositional indication of
    E- and M-type asteroids by VIS-NIR reflectance spectra of meteorites*, A&A
    671, A77, <https://doi.org/10.1051/0004-6361/202245207>, Table 5 — M-type
    densities.

**Rotation and the outer Solar System**

- Pravec, P., and Harris, A. W. (2000), *Fast and slow rotation of asteroids*,
  Icarus 148, 12 — the breakup period, 3.3 h / √ρ.
- Holsapple, K. A. (2007), *Spin limits of Solar System bodies: From the small
  fast-rotators to 2003 EL61*, Icarus 187, 500 — gravity dominates strength
  above ~10 km.
- National Institute of Standards and Technology (2024), *CODATA recommended
  values of the fundamental physical constants: 2022*, NIST SP 961,
  <https://physics.nist.gov/cuu/pdf/wall_2022.pdf> — p. 1: Newtonian
  constant of gravitation G = 6.674 30(15) × 10⁻¹¹ m³ kg⁻¹ s⁻², the
  `physics.G_SI` used by `min_rotation_period_h` (General_Research rc-681).
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
