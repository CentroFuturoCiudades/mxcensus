# CPV Unit 6f — 2015/2010 occupation, activity and 2010 religion in `cpv_derived`

Done **2026-10-08** (with the user, on the Mac). Gate: tests (full suite green, §Tests), a
32-state `derived=True` sweep of both editions with no unmapped code, and the new columns
checked against INEGI's tabulados (§Verification).

## Decisions (user, 2026-10-08)

| question | decision |
|---|---|
| next unit | **all four HANDOFF candidates this session, one unit each, in my order**: 6f the occupation/activity/religion items, 6g `PSIND_LIM`, 6h the EIC 2015 frame, 6i 2000/2005 derived columns |
| Censo 2010 religion 220100 «Movimientos Sincréticos Judaicos Neoisraelitas» (2010: a judaic credo, its ITER's `POTRAS_REL`; 2020: code 1325, an evangelical church) | **2020's grouping** (→ `Protestante/cristiano evangélico`): `RELIGION_CAT` means the same in every edition, as 6e's unspecified-state rule. 9,021 persons nationally (0.008%) |

Taken without asking (evidence below): SINCO 2011's group 59 joins 52, where SINCO 2019
put its occupations. The 2010 `PNCATOLICA` becomes an edition cell on 2020's
protestant/evangelical group.

## The catalogs

| edition | occupation item · catalog | activity item · catalog | religion |
|---|---|---|---|
| 2010 | `OCUACTIV_C` · `TC_OCUPACION_2010`, 465 4-digit codes (the CUO 2010, SINCO's forerunner) | `ACTTRAB_C` · `TC_SCIAN_2010`, 179 4-digit SCIAN 2007 codes | `OTRAREL_C` · `TC_RELIGION_2010`, 245 6-digit codes |
| 2015 | `OCUPACION_C` · `TC_OCUPACION_2015`, 156 3-digit SINCO 2011 subgroups | `ACTIVIDADES_C` · `TC_SECTOR_2015`, 178 4-digit codes | not asked |
| 2020 | `OCUPACION_C` · `OCUPACION`, 163 3-digit SINCO 2019 subgroups | `ACTIVIDADES_C` · `ACTIVIDAD`, 181 4-digit codes | `RELIGION`, 46 4-digit codes |

Every code in the data is a catalog row: 2010 uses all 465 occupation codes, and the
religion item has no blank.

- **Occupation.** The coarse column is SINCO's grupo principal: the first two digits.
  2015's subgroups are 2020's, up to wording (132 of 156 identical, 23 reworded, 1 split:
  241 → 241/242/243). 2010's 4-digit codes have the same three-digit prefixes. The 2-digit
  groups are the same, with one exception. INEGI's SINCO 2019 presentation (CESNIDS 2019,
  «Detalle de la actualización») says: «Se eliminó el grupo 59 "Otras ocupaciones en
  servicios personales y vigilancia no clasificados" — se elimina el único subgrupo 599»,
  and lists a new subgroup «529 Otros trabajadores no clasificados» in group 52. So
  `_RECODE` maps 2015's 599 → 529 and 2010's 5999 → 5299 (Σ `FACTOR` 5,671 and 8,303). The
  division (first digit) is unchanged, which the tabulados confirm.
- **Activity.** The coarse column is the SCIAN sector (two digits). The 2010, 2015 and 2020
  catalogs share their 24 sector prefixes (11 … 93, 99). 2010's item is `ACTTRAB_C`
  (`_ALIASES`).
- **Religion (2010).** The 2010 classification puts the group in its first two digits (11
  católica, 12 ortodoxa incl. 1207xx «cristianos tradicionalistas», 13 protestantes
  históricas, 14 pentecostales y evangélicas, 15 bíblicas diferentes de evangélicas, 21–29
  other credos, 31 sin religión, 99 no especificada). `_religion_2010` maps each group to a
  2020 code of the same `RELIGION_CAT` group (`_RELIGION_2010`), with two exact-code
  exceptions (`_RELIGION_2010_CODES`): 220100 → 1325 (the decision above) and 310100
  «sin adscripción religiosa» → 3104. A code outside these groups, a 4-digit 2020 code or
  a blank raises.

| `RELIGION_CAT` | 2010 groups | 2010 ITER indicator |
|---|---|---|
| Católica | 11 | `PCATOLICA` |
| Protestante/cristiano evangélico | 13, 14, 15, + 220100 | `PNCATOLICA` (13–15) |
| Otros credos | 12, 21–29 (except 220100) | `POTRAS_REL` (12, 21–29) |
| Sin religión / Sin adscripción religiosa | 31 | `PSIN_RELIG` |
| No especificado | 99 | — |

### Columns per edition (after 6f)

| edition | personas | viviendas |
|---|---|---|
| 2025 | 58 | 15 |
| 2020 | 60 | 15 |
| 2015 | **42** (was 40): + `OCUPACION_C_COARSE`, `ACTIVIDADES_C_COARSE` | 13 |
| 2010 | **25** (was 22): + `OCUPACION_C_COARSE`, `ACTIVIDADES_C_COARSE`, `RELIGION_CAT` | 4 |

## Constraints (`cpv_constraints`)

2010 personas **138 → 142**: `PCATOLICA`, `POTRAS_REL`, `PSIN_RELIG` (legacy cells on
`RELIGION_CAT`; the crosswalk calls them comparable) and `PNCATOLICA` (`_EDITION_CELLS`:
the 2010 ITER's own group, on 2020's `Protestante/cristiano evangélico`). `PRO_CRIEVA` has
no 2010 column. Others unchanged (2015: none; 2020: 157 + 46; 2025: 25 + 3). There are no
occupation or activity constraints: the legacy sets have none.

## Verification

**32-state sweep.** Both tabulado scripts load `load_cpv_personas(period, state=s,
derived=True)` for all 32 states of 2010 and 2015: no unmapped code, no missing value.

**INEGI's tabulados**: the employed aged 12–130, per state × sex (Total, Hombres,
Mujeres; 32 states + the nation), by division and by grouped sector:

| tabulado | rows | result |
|---|---|---|
| EIC 2015 `08_caracteristicas_economicas.xls` sheet 06: by division (SINCO 2011 first level: 9 divisions + NE) | 891 | **exact** (|Δ| = 0) |
| EIC 2015 sheet 07: by sector (agriculture; mining, manufacturing, electricity and water; construction; trade; services; NE) | 891 | **exact** |
| Censo 2010 ampliado `08_02A_ESTATAL.xls`: by division («primer nivel de la CUO 2010») | 891 | **exact** |
| Censo 2010 ampliado `08_03A_ESTATAL.xls`: by sector | 891 | **exact** |

National employed: 45,085,410 (2015) and 42,699,571 (2010). INEGI leaves out persons of
unspecified age (28,710 employed in 2015), as in 6e. The derived columns keep them. Group
59 → 52 stays in division 5, so the division tables cannot tell 52 from 59. INEGI's SINCO
2019 document settles that.

**Censo 2010 sample vs the census ITER** (religion, national; the ampliado has no religion
table):

| indicator | ITER | sample Σ FACTOR | share ITER / sample |
|---|---|---|---|
| `PCATOLICA` | 92,924,489 | 94,210,891 (+1.4%) | 82.72% / 84.15% |
| `PNCATOLICA` | 10,924,103 | 11,198,401 (+2.5%) | 9.72% / 10.00% |
| `POTRAS_REL` | 172,891 | 179,255 (+3.7%) | 0.154% / 0.160% |
| `PSIN_RELIG` | 5,262,546 | 4,749,806 (−9.7%) | 4.69% / 4.24% |

The census has about twice the «no especificado» (2.7% vs 1.4%), as in 6d/6e: the sample
reproduces its ampliado tabulados, not the census ITER. The ITER population also includes
collective dwellings (112,336,538 vs the sample's 111,960,139 in private dwellings). The
220100 group (9,021) is far below that gap.

## Tests (`tests/test_cpv_derived.py`)

- **Offline:**
  - `test_catalog_codes_derive` (8 cases; skipped without `data/dict/fd`): every code of
    the 2010/2015/2020 occupation, activity and religion catalogs derives a category; the
    SINCO groups exist up to 59 (2010's `5999`, 2015's `599` only); the 2010 religion
    groups as tabled above, with 220100 the only group-22 code in the evangelical group;
  - `test_source_codes_match_2020`: 2015 `OCUPACION_C`/`ACTIVIDADES_C` sentinels = 2020's;
    2010 `ACTTRAB_C` (as `ACTIVIDADES_C`) declares no 9999 (`_GAPS`); `OCUACTIV_C` and
    `OTRAREL_C` are own-code catalog items (`_OWN_CODES`);
  - the recodes (`test_recode_tables`), the listings per edition;
  - synthetic 2015/2010 persons (599 → group 52, 5999 → 52, 9888 → 98, sector 93/31/99,
    religion 110300/220100/310100), and unknown religion codes raise (410000, a 2020 code,
    a blank);
  - 2010 constraints include `PCATOLICA`, `POTRAS_REL`, `PSIN_RELIG`, `PNCATOLICA`.
- **Real data (local mirror):** `test_occupation_activity_equal_tabulados`: EIC 2015 state
  01 and Censo 2010 state 03, divisions and sectors = the tabulados exactly.
- **Full suite**: 1649 passed, 1 skipped (29 min, the Mac's full mirror).

## Not done (HANDOFF §Next)

- 2000/2005 derived columns (unit 6i).
- 2015 asked no religion; the 2010 occupation/activity are not bridged below the two-digit
  group/sector.
