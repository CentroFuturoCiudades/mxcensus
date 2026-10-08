# CPV Unit 4b — CGPV 2000 + Conteo 2005 ITER, crosswalk, municipal MGs

Done **2026-10-08** (overnight, unattended, on the Mac). **The upload waits for `wsl`**
(only host with the HF token; Tailscale re-login pending). These files join the release
batch of `HANDOFF.md`, as 3a–4a's do.

Gate: `--validate` 0 with the 2000/2005 ITER — ✅ **0/737**. The crosswalk is reviewed and
the MG files are built. "Uploaded" is pending (§Pending).

## ITER build

`build_cpv.py --periods 2000 2005 --tables iter` (ZIPs cached): **64 files** in 2 s.
- **2000**: 132 columns, 205,678 rows, 24 MB.
- **2005**: 130 columns, 194,229 rows, 23 MB.
- Both have 2010's layout: UTF-8 with a BOM before a quoted lower-case header, total rows
  `mun=000`/`loc=0000`, the 9998/9999 aggregates.
- **Markers over all 32 states** (`_AGG_SPECIALS`): 2000 `*` 11,113,608 cells, `N/D`
  115,311; 2005 `*` 9,979,707.
- **State totals**: POBTOT 97,483,412 (2000) and 103,263,388 (2005), INEGI's published
  totals for the XII Censo and the II Conteo; tested.

**Dictionary fix.** Conteo 2005's indicator dictionary writes every count's range as
`00..9999999999`. `parse_indicator_csv` read a zero-padded lower bound as a code space
(the rule for `00…32`, `001..570`), so every 2005 count came out a string. Now a range from
all zeros to all nines (5+) is a quantity. The 2010/2020/2025 dictionaries parse unchanged
(compared with the HEAD parser).

**Decimals.** Neither old dictionary states decimals, although some indicators have two:
- 2000: `pro_ovp`, `pro_ocvp`, `vp_pardes`;
- 2005: `rel_h_m`, `prom_hnv`, `graproes`, `gradoes_m`/`_f`, `pro_vipa`, `pro_c_vp`.

No change was needed: `label_frame` already makes a numeric column `Float64` when its
values are not integral (2020's `REL_H_M` has always relied on it). Data-derived
`Decimales` were tried and dropped, because they churned the 2010–2025 dictionaries for
nothing.

**INEGI's broken rows.** Two 2000 locality rows have a name containing ", " that spilled
into the next field:
- Oaxaca 277-0101: «V» + «, LA (R»;
- Querétaro 012-0011: «D» + «, LA».

From `LONGITUD` on, every value sits one column to the right and the row's last value is
lost, so `POBTOT` read the altitude. The mirror keeps the rows verbatim (faithful raw; the
raw schema passes, `LONGITUD` being alphanumeric). `load_cpv_iter` repairs them with a
warning (`cpv_aggregates._repair_spilled_names`): the spill is joined back to
`NOM_LOC`, the values shift one column left, the last is missing. With the repair, both
municipalities' localities add up to the municipal total exactly (12,668 and 49,554);
without it they were off by +1,427 and −1,442.

**Schema map**: ITER 2000 = `g01`, 2005 = `g02`, 2010 = `g03`, 2020 = `g04`. AGEB and the
microdata are unchanged; 27 groups in all. The 2010/2020 ITER dictionaries are identical
under their new gids.

## Crosswalk (`cpv_iter_crosswalk.yaml`, 296 → 388 indicators)

`_XW_PERIODS` = 2020, 2010, 2005, 2000 (newest first: the 2020 names are canonical). The
2005 and 2000 ITER renamed most mnemonics (`P_TOTAL`, `PMASCUL`, `O_VIVPAR`…), so:
- **Automatic pairs** (`_XW_DESC_PERIODS`): an older column whose normalized description
  (case, accents, punctuation; the 2000 dictionary's «Po blación» typo) equals exactly one
  newer indicator's pairs with it and is renamed. **78 pairs**, all reviewed. One is
  rejected (`_XW_UNPAIR`: 2000 `PCONDISC`, «Población con discapacidad», another question
  than 2020's `PCON_DISC` scale).
- **Manual pairs, renamed** (`_XW_PAIRS_RENAMED`), for the same indicator under other
  wording:
  - health coverage `PSDERSS`/`PCDERSS`/`PDERIMSS`/`PDERISTE` (2000);
  - households and headship (`TOT_HOG`, `HOGAR_JM`/`HOGJEFM`, `P_HOG_JF`…);
  - occupants and averages (`OCUVIVPAR`, `PRO_OVP`, `PRO_OCVP`);
  - services (`VPH_DREE`/`VP_AGDREL` → `VPH_C_SERV`, `VPH_NADE`/`VP_NOADE` → `VPH_NDEAED`);
  - goods (`VP_TV`, `VP_RADIO`, `VP_TELEF`, `VP_AUTOM`);
  - `P15_SINSTR` → `P15YM_SE`, `PECOINACT` → `PE_INAC`;
  - five 2000 ↔ 2005 pairs of indicators neither later census has (`POB6_14` →
    `P_6A14_AN`…).
- **Manual pairs that keep their name** (`_XW_PAIRS_KEPT`, 13), each with a `Nota`:
  - residence five years earlier (`P_RE2000`, `P5_RES95` … → `PRES2015`/`PRESOE15`): other
    dates; 2000 also counts residence abroad;
  - `P_SEGPOP` → `PDER_SEGP` (Seguro Popular / INSABI, already `Comparable: false`);
  - `PNACOENT` → `PNACOE` (2000 includes the foreign-born);
  - `P5_CATOLIC` → `PCATOLICA` (5+);
  - piped water `VPH_AGDV`/`VP_AGUENT`/`VPH_NOAG` (red pública / any vs within the
    dwelling);
  - `VP_SERSAN` → `VPH_EXCSA` (exclusive toilet).
- **Unpaired**: 60 indicators exist in 2000 and 37 in 2005 without a 2010/2020
  counterpart (5 shared). Examples: the 6–14 and 15–24 age groups, 2000's income bands
  and hours worked, 2005's basic/post-basic education, cooking fuel, tenure.

**`Renombrar` is now the list of editions** whose spelling `harmonize=True` renames (e.g.
`POBFEM: ['2005', '2000']`, `TAMLOC: ['2010']`). `cpv._crosswalk_renames(table, periods)`
applies only the frame's own edition's renames (`_renames(table, periods)` from
`_harmonize` and `variables_cpv_labels`), since one edition's old name could be another's
indicator. A legacy `Renombrar: true` still means every edition.

## Municipal Marco Geoestadístico 2000 and 2005

`build_marco_geo.py --period 2000|2005` (national ZIPs, 37 and 66 MB; three layers each):

| period | `ent` | `mun` | `a` (urban AGEBs) |
|---|---|---|---|
| 2000 | 32 | 2,480 polygons = 2,443 municipalities (`CVEMUNI` repeats for multi-part ones) | 40,089 |
| 2005 | 32 | 2,454 | 49,212 |

Both municipality counts equal their ITER's (2,443 and 2,454).

**Builder changes**:
- 2000's AGEB shapefile is `agebs_urb_2000` (`_NATIONAL_LAYERS` `^agebs?_urb`).
- **Entity code columns** (`_state_codes`: `_ENTITY_COLUMNS`, `_ENTITY_PREFIX_COLUMNS`):
  - 2005 has `CVE_EDO` and `CLAVE` (AGEBs, 13 characters);
  - 2000 has `CVEMUNI` (municipalities, entity + municipality) and `CLVAGB` (AGEBs,
    `010010001293-5`).
- **MG 2005's `Entidades`/`Municipios` ship without a `.prj`**. They take the one CRS the
  edition's other layers declare (`_edition_crs`: the AGEB layer's `ccl_itrf92` LCC), with
  a printed note. The build raises if the declared CRSs disagree or none exists.
  - **Check**: in EPSG:6372, the 2005 states' centroids lie a median 105 m (max 2.8 km)
    from MG 2010's, with areas 96–101% of them. 2000 (own `.prj`): a median 189 m.
- The CRSs differ within an edition (2000: LCC ITRF92 for `ent`/`mun`, `MEXICO_ITRF_2008_LCC`
  for the AGEBs). The mirror keeps each; `load_mg` returns EPSG:6372.
- Attribute names stay INEGI's (`CVE_EDO`, `CVEMUNI`, `CLAVE`…), faithful like 2010's.

Files: 96 + 96, 40 MB (2000) and 73 MB (2005). MG 1995 (`ent` + `mun`) is unit 5b.

## Tests

`tests/test_cpv_aggregates.py`:
- the 2005 range rule (`parse_indicator_csv`);
- the crosswalk pairs (automatic, manual, kept, unpaired, old-only, the «Po blación»
  normalization);
- edition-scoped renames and a harmonized 2005 frame;
- `_repair_spilled_names`;
- `test_iter_2000_2005_real` for all 32 states of both: state = Σ municipalities =
  Σ localities, the published Aguascalientes totals, renamed indicators present, counts
  `Int64` and averages `Float64`; the repair warning in 2000's states 20/22;
- the national totals;
- the broken rows kept verbatim in the mirror;
- 2000–2020 ITER stacking.

The schema-map and crosswalk-coverage tests now span the four ITER editions.

`tests/test_mg.py`:
- the old frames' code columns;
- the missing-`.prj` CRS fallback;
- `test_real_mg_2000_2005`: counts, distinct municipalities, EPSG:6372, and the same place
  as MG 2010.

**Results**:
- `tests/test_cpv_aggregates.py`: 157 passed over 32 states (12 min).
- `tests/test_mg.py`: 27 passed, 1 skipped.
- `tests/test_cpv.py` + `tests/test_cli.py` + `tests/test_schema_groups.py`: 664 passed (9 min).

## Deviations from the plan

- The plan's "municipal MGs (`mun`, `ent`)": 2000 and 2005 also ship urban AGEBs; they are
  built as `a`.
- The crosswalk's automatic description pairing is new: the plan said "draft by description,
  then hand-review", and the draft is now code with a reject list.
- The ITER repair of INEGI's two broken rows happens in the loader; the mirror stays
  faithful.

## Pending (needs `wsl`)

The release batch (`HANDOFF.md`) gains these 64 `cpv_iter_{2000,2005}_NN` and 192
`mg_{ent,mun,a}_{2000,2005}_NN` files: copy them to `wsl` or rebuild there (ITER in seconds,
MGs ~2 min each), then register and upload.
