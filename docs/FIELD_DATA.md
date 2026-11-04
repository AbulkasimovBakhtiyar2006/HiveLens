# EFSA MUST-B: provenance of the included archive

**This is a real historical study, not a HiveLens deployment.** HiveLens imports and
visualizes a selected subset of its published measurements. It has not run SAM or
Muse Spark on these measurements and does not fabricate photographs or reports for them.

## Citation and rights

Dupont, Yoko L.; Capela, Nuno; Kryger, Per; et al. (2021).
*Research project on field data collection for honey bee colony model evaluation — datasets*,
v2. [Zenodo 5148318](https://zenodo.org/records/5148318),
[DOI 10.5281/zenodo.5148318](https://doi.org/10.5281/zenodo.5148318).
License: [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).

The associated [EFSA scientific report, EN-6695](https://doi.org/10.2903/sp.efsa.2021.EN-6695)
describes the 2019–2020 field campaign in Denmark and Portugal. Attribution is retained
in the archive, the in-app source panel and each hive download. Our transformations
are explicitly described; the license does not imply researcher or EFSA endorsement.

## Included subset

| Item | Included |
|---|---:|
| Original study hive IDs with usable observations | 57 |
| Site IDs | 7 |
| Daily mean colony weights | 13,245 |
| Varroa soapy-water samples | 143 |
| First / last observation | 2019-03-12 / 2020-11-26 |

The report describes **six experimental apiaries**. The master site table contains an
additional Flakkebjerg 2020 identifier; seven IDs are not a claim of seven separate farms.
A study hive ID is a tracking identifier; do not infer an unchanged colony or queen
throughout its entire history.

The default example is **PT_5_2, Serra da Lousa, Portugal**, with daily weight history
and six dated Varroa wash samples. The selector exposes every included hive.

## Exact source files and transformations

`python scripts/import_mustb.py` downloads the pinned version into
`data/research/mustb/` and verifies each file against Zenodo’s published MD5 checksum.
The output also records SHA-256 checksums and source URLs. The raw files are not
committed; `hivelens/datasets/mustb.json` is committed so the reference view works offline.

| Source | Role |
|---|---|
| `01_Sites_coord.csv` | Site identifiers and names |
| `Table_III_Hives.csv` | Master hive IDs, site/hive join, country and subspecies |
| `Table_V_Colony_inspection.zip` | Colony weight, filtered by measurement and kg units |
| `Table_VI_SSD2.csv` | Varroa results, sampling dates, laboratory result types and methods |

- Join weights by the original `(siteNo, hiveNo)` pair. Join laboratory samples using
  the holding/site and herd/hive identifiers. Preserve the master `hiveId`.
- Compute the arithmetic mean of available scale readings for each hive/calendar day.
  Store its reading count as `n`. These are colony-scale weights in kg, **not honey kg**.
- Retain only the **Soapy water method**, with units **number per 100 adult bees**.
  Preserve each sample’s `resId`, date, numeric value or result type.
- `LOD` means a non-detected value below a detection limit. Keep `value: null`, the
  raw result type and the source limit if supplied. Do not substitute zero. The included
  LOD rows do not provide numeric detection limits.
- Do not shift dates, interpolate missing days, smooth over gaps or generate statuses.
  The weight chart connects consecutive recorded days only; wash results are points.

## Exclusions and limitations

- **33** “Mite down-fall in 24h” rows have a conflicting “per 100 adult bees” source unit.
  They are omitted rather than silently converted to mites/day.
- **1,658** weight rows cannot be joined to the included master hive/site table.
- **4** weight rows have dates outside the documented 2019–2020 campaign. Their source
  IDs and dates are retained in `excluded_dates`; they are not silently corrected.
- Other measurement types from the much larger original study are outside this subset.
- Daily aggregation loses within-day variation. A weight change alone cannot identify
  honey yield, feeding, equipment changes, swarming or disease.

This archive does not validate HiveLens’ image detector: it supplies real longitudinal
context with different measurement protocols. Natural mite fall and wash infestation
are distinct quantities and must not share an alert threshold or be spliced into one trend.

## Importing a study apiary into Production

Run `python scripts/import_field_apiary.py --workspace production --site 5` to register
**Serra da Lousa, Portugal**, in the working farm registry. The selected subset has seven
original study hive IDs, 2,969 daily colony weights and 31 wash samples. The import is
explicit and repeatable; the other workspace is unchanged.

Each hive retains its full selected chronology in `field_history.json`. The normal
history view displays it with the source citation, original dates and sampling units.
ZIP exports include that file and its checksums/attribution. Existing photo inspections
are preserved separately. These observations are not converted into model-generated
reports, current treatment alerts, honey-mass estimates or inferred mite-drop rates.
An archived study does not establish the apiary's present-day condition or layout.

## Reviewer wording

> These are real historical hive observations from the published EFSA MUST-B study.
> We retain the original hive IDs and dates, and link every view to the dataset and
> scientific report. HiveLens visualizes this archive; the study team collected it.
> Our photo analysis and its evaluation are separate.
