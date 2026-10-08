# CPV Unit 6a — Cross-year municipal crosswalk

Done **2026-10-08** (overnight, unattended, on the Mac). Gate: a helper plus tests — ✅.

## Source: the frames' own polygons

The plan named INEGI's AGEEML catalog and its history of changes. Its web app
(`/app/ageeml/`) builds catalogs, update records and equivalence tables through a form,
with no direct download of the history. The Marco Geoestadístico frames built in units
1d–5b hold the same information as geometry. The MG ZIPs' own change log (MG 2000's
`bitacora_cambios_MGM2000.csv`) turned out to be a product log (re-indexed fields, shifted
polygons), not municipal history.

**`scripts/build_geo_crosswalk.py`** (maintainer-only, ~3 s) reads `mg_mun_*` of the six
municipal frames: 1995, 2000, 2005, 2010, 2020 and 2025 (1990 has none).
1. Each municipality's 5-character code comes from that edition's columns (`CVE_ENT` +
   `CVE_MUN`, `CVEMUNI`, `CVE_CONCA` or `CVEGEO`). Multi-part municipalities (MG 2000) are
   dissolved, and areas are taken in EPSG:6372.
2. For every consecutive pair:
   - a code missing from the later frame stops the build;
   - each code new in the later frame is overlaid on the earlier frame. Its **parents** are
     the municipalities covering ≥5% of its area, each with `parte_del_nuevo` (that share)
     and `parte_del_origen` (the share of the parent's area it took).
3. **Boundary revisions are not changes.** A code present in both frames is the same
   municipality, although frames redraw boundaries by a few percent (same-code area overlap:
   median 96–100%).

**Result** (`src/mxcensus/_yaml/cpv_mun_lineage.yaml`):

| transition | municipalities | new codes |
|---|---|---|
| 1995 → 2000 | 2,428 → 2,443 | 15 |
| 2000 → 2005 | 2,443 → 2,454 | 11 |
| 2005 → 2010 | 2,454 → 2,456 | 2 |
| 2010 → 2020 | 2,456 → 2,469 | 13 |
| 2020 → 2025 | 2,469 → 2,478 | 9 |

- **No code was ever retired**: each transition adds exactly the difference. That makes
  the newest frame's code list (`claves`) plus the creation dates enough to reconstruct
  every frame's set.
- **Parents**: each new municipality's main parent is in its own state. Examples:
  - 2025's 02007 (Baja California) came from 02001 (57%) and 02002 (42%);
  - 2010's 23009 (Bacalar) from 23008 and 23002, plus 5% of Yucatán's 31019 (the
    Quintana Roo/Yucatán boundary dispute);
  - 2000's 30210 has four parents.
- The YAML also records each frame's count, the 5% threshold and the codes.
- These municipality sets equal the ITER's for 2000 (2,443) and 2005 (2,454). MG 1995 has
  15 Chiapas municipalities the 1995 ITER lacks (`STEP_5b.md`).

## `mxcensus.cpv_geo`

- **`cpv_mun_lineage()`**: the lineage as a table, one row per parent (`PERIOD_FROM`,
  `PERIOD_TO`, `CVEGEO`, `PARENT`, `SHARE_NEW`, `SHARE_PARENT`).
- **`cpv_municipal_units(start, end, *, min_share=0.10, cross_state=False)`**: stable
  municipal units between two frames. One row per municipality of `end` (a superset of
  `start`'s, codes never retired):
  - `UNIT` is the smallest code of its unit, `FIRST` the frame where the code appeared;
  - a unit joins every municipality created after `start` (up to `end`) with the parents
    that gave it ≥ `min_share` of its area, transitively;
  - a parent in another state is ignored unless `cross_state` (that is only the
    Bacalar/31019 dispute).
  - **Use**: merge an edition's municipal rows on `CVEGEO`, aggregate by `UNIT`; two
    editions are then comparable.
  - **Sizes**: 1995 → 2025 gives 2,410 units for 2,478 municipalities, 2020 → 2025 gives
    2,466.
  - `start` = 1990 raises: no frame (the 1990 codes are a subset of 1995's, but where the
    1995 municipalities came from is not in any frame).
- Exported from `mxcensus`; `_resources.cpv_mun_lineage()` loads the YAML.

## Tests (`tests/test_cpv_geo.py`, new)

- **The document**: counts, codes never retired (new codes = the count difference), shares
  in range, parents among the codes, every main parent in its child's state, 02007's two
  parents.
- **Units**:
  - 2020 → 2025 (Baja California's three in one unit; `FIRST`);
  - the identity for one frame;
  - 1995 → 2025 coarser than 2010 → 2025;
  - the Bacalar dispute ignored by default and joined with `cross_state=True,
    min_share=0.05`;
  - errors for 1990 and a reversed span.
- **`_REAL`**:
  - the YAML equals a rebuild from `data/parquet`'s frames;
  - every 2000 and 2020 ITER municipality of all 32 states maps to a unit, both editions
    give the same set of units, and 2000's national total survives the aggregation.

## Deviations from the plan

- **Source**: geometry overlays instead of AGEEML's history. AGEEML's decrees could still
  add dates and names; the YAML has room for them.
- **Scope**: municipalities only. Locality code changes ("Archivo Histórico de
  Localidades") are not covered: the frames' locality layers differ too much between
  editions (urban polygons, rural points; 1995–2005 have no locality layer).
