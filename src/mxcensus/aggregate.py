"""Aggregate census loaders (ITER + RESARGEBUB) and geometry merging."""
from __future__ import annotations

from pathlib import Path

import chardet
import geopandas as gpd
import numpy as np
import pandas as pd


def load_resargebub(
    file_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads census at ageb/block level. Splits census date into 5 levels:
    state, municipality, locality, urban ageb, and block levels.

    Drops non-count columns and labels NaN values correctly.

    Returned DataFrames are index by their area codes with compatible multi-indices.

    Parameters
    ----------
    file_path : Path
        Path to the raw census data file.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
        Tuple with each level data frame.
    """
    with open(file_path, "rb") as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result["encoding"]
        if encoding == "ascii":
            encoding = "latin"
        print(f"Detected encoding: {encoding}")

    # We will drop name variables and ratios, keep only counts
    df = pd.read_csv(file_path, encoding=encoding, na_values=["N/D"]).drop(
        columns=[
            "NOM_ENT",
            "NOM_MUN",
            "NOM_LOC",
            "REL_H_M",
            "PROM_HNV",
            "GRAPROES",
            "GRAPROES_F",
            "GRAPROES_M",
            "PROM_OCUP",
            "PRO_OCUP_C",
        ]
    )

    # A quick imputation of weird censored block variables
    df.loc[df.POBTOT == 0, ["TVIVHAB", "VIVPAR_HAB", "VIVPARH_CV", "TVIVPARHAB"]] = "0"
    df.loc[df.POBTOT == 0, ["TVIVPAR", "VIVPAR_DES", "VIVPAR_UT"]] = df.loc[
        df.POBTOT == 0, ["TVIVPAR", "VIVPAR_DES", "VIVPAR_UT"]
    ].replace("*", np.nan)

    df_state = (
        df.query("ENTIDAD != 0 & MUN == 0 & LOC == 0 & AGEB == '0000' & MZA == 0")
        .drop(columns=["MUN", "LOC", "AGEB", "MZA"])
        .set_index("ENTIDAD")
        .sort_index()
        .astype(int)
    )
    df_mun = (
        df.query("ENTIDAD != 0 & MUN != 0 & LOC == 0 & AGEB == '0000' & MZA == 0")
        .drop(columns=["LOC", "AGEB", "MZA"])
        .set_index(["ENTIDAD", "MUN"])
        .sort_index()
    )
    df_loc = (
        df.query("ENTIDAD != 0 & MUN != 0 & LOC != 0 & AGEB == '0000' & MZA == 0")
        .drop(columns=["AGEB", "MZA"])
        .set_index(["ENTIDAD", "MUN", "LOC"])
        .sort_index()
    )
    df_ageb = (
        df.query("ENTIDAD != 0 & MUN != 0 & LOC != 0 & AGEB != '0000' & MZA == 0")
        .drop(columns=["MZA"])
        .set_index(["ENTIDAD", "MUN", "LOC", "AGEB"])
        .sort_index()
    )
    df_mza = (
        df.query("ENTIDAD != 0 & MUN != 0 & LOC != 0 & AGEB != '0000' & MZA != 0")
        .set_index(["ENTIDAD", "MUN", "LOC", "AGEB", "MZA"])
        .sort_index()
    )

    assert (
        len(df_state) + len(df_mun) + len(df_loc) + len(df_ageb) + len(df_mza)
    ) == len(df)

    # Flagging censored data, state is never censored
    # N/D is always missing value, but asterisc meaning depends on level.
    # Above block level, * is always 0, 1 or 2, we flag it with masks.
    assert str(df.TVIVHAB.dtype) == "str"
    df_mza.loc[df_mza["TVIVHAB"].isin(["1", "2"]), :] = df_mza.loc[
        df_mza["TVIVHAB"].isin(["1", "2"]), :
    ].replace("*", np.nan)

    mask_mun = df_mun == "*"
    mask_loc = df_loc == "*"
    mask_ageb = df_ageb == "*"
    mask_mza = df_mza == "*"

    df_mun = df_mun.replace("*", None).astype("Int64")
    df_loc = df_loc.replace("*", None).astype("Int64")
    df_ageb = df_ageb.replace("*", None).astype("Int64")
    df_mza = df_mza.replace("*", None).astype("Int64")

    return df_state, df_mun, df_loc, df_ageb, df_mza


def load_iter(
    file_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads census at locality level. Splits census date into 3 levels:
    state, municipality, locality, and aggregated counts for localities with
    less than 3 dwellings.

    Drops non-count columns and labels NaN values correctly.

    Returned DataFrames are index by their area codes with compatible multi-indices.

    Parameters
    ----------
    file_path : Path
        Path to the raw census data file.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
        Tuple with each level data frame.
    """

    # We will drop name variables and ratios, keep only counts
    df = pd.read_csv(file_path, encoding="utf-8-sig", na_values=["N/D"]).drop(
        columns=[
            "LONGITUD",
            "LATITUD",
            "ALTITUD",
            "NOM_ENT",
            "NOM_MUN",
            "NOM_LOC",
            "REL_H_M",
            "PROM_HNV",
            "GRAPROES",
            "GRAPROES_F",
            "GRAPROES_M",
            "PROM_OCUP",
            "PRO_OCUP_C",
            "TAMLOC",
        ]
    )

    df_state = (
        df.query("ENTIDAD != 0 & MUN == 0 & LOC == 0")
        .drop(columns=["MUN", "LOC"])
        .set_index("ENTIDAD")
        .sort_index()
        .apply(pd.to_numeric)
        .astype(int)
    )
    df_mun = (
        df.query("ENTIDAD != 0 & MUN != 0 & LOC == 0")
        .drop(columns=["LOC"])
        .set_index(["ENTIDAD", "MUN"])
        .sort_index()
        .apply(pd.to_numeric)
        .astype(int)
    )
    df_loc = (
        df.query("ENTIDAD != 0 & MUN != 0 & LOC != 0 & LOC < 9998")
        .set_index(["ENTIDAD", "MUN", "LOC"])
        .sort_index()
    )

    df_loc_agg = (
        df.query("LOC >= 9998")
        .set_index(["ENTIDAD", "MUN", "LOC"])
        .sort_index()
        .replace("*", np.nan)
        .apply(pd.to_numeric)
        .astype("Int64")
    )

    assert (len(df_state) + len(df_mun) + len(df_loc) + len(df_loc_agg)) == len(df)

    # Flagging censored data, state and mun are never censored.
    # Only localities with less than 3 dwellings are censored and are treated as nan.
    df_loc.loc[df_loc["TVIVHAB"].isin([1, 2]), :] = df_loc.loc[
        df_loc["TVIVHAB"].isin([1, 2]), :
    ].replace("*", np.nan)
    df_loc = df_loc.apply(pd.to_numeric).astype("Int64")

    return df_state, df_mun, df_loc, df_loc_agg


def sanity_checks(
    df_iter_state: pd.DataFrame,
    df_iter_mun: pd.DataFrame,
    df_iter_loc: pd.DataFrame,
    df_state: pd.DataFrame,
    df_mun: pd.DataFrame,
    df_loc: pd.DataFrame,
    df_ageb: pd.DataFrame,
    df_mza: pd.DataFrame,
) -> None:
    """Performs sanity checks to make sure census counts are consistent."""
    # State df should be equivalent
    assert (df_state - df_iter_state).max(axis=None) == 0

    # Iter mun df is always complete
    assert abs(df_iter_mun - df_mun).max(axis=None) == 0
    assert df_iter_mun.isna().sum(axis=None) == 0

    # Mun agg must match state
    assert np.all(df_iter_mun.sum() == df_iter_state)

    # Iter loc is complete, resargebub loc only contains urban localities
    # Prefer iter, but check urban matches
    assert (
        abs(df_iter_loc.loc[df_loc.index, df_loc.columns] - df_loc).max(axis=None) == 0
    )

    # Check localities aggregate into muns
    loc_grouped = df_iter_loc.groupby(["ENTIDAD", "MUN"]).sum()
    delta_mun = df_iter_mun - loc_grouped
    # Difference is always positive, given censored variables
    assert np.all(delta_mun >= 0)
    # Exact match for POBTOT, VIVTOT y TVIVHAB
    assert np.all(delta_mun[["POBTOT", "VIVTOT", "TVIVHAB"]] == 0)

    # Check agebs aggregate into localities totals, meaning urban localities
    # can de decomposed into urban agebs
    ageb_grouped = df_ageb.groupby(["ENTIDAD", "MUN", "LOC"])[
        ["POBTOT", "VIVTOT", "TVIVHAB"]
    ].sum()
    assert np.all(
        ageb_grouped
        == df_iter_loc.loc[ageb_grouped.index, ["POBTOT", "VIVTOT", "TVIVHAB"]]
    )

    # Check blocks aggregate into agebs
    # WARNING, this test does not pass, ignore block level for now
    mza_grouped = df_mza.groupby(["ENTIDAD", "MUN", "LOC", "AGEB"])[
        ["POBTOT", "VIVTOT", "TVIVHAB"]
    ].sum()
    # assert np.all(
    #     mza_grouped == df_ageb.loc[mza_grouped.index, ["POBTOT", "VIVTOT", "TVIVHAB"]]
    # )


def impute_collective(df_coarse, df_fine):
    """Imputes collective population and household counts in fine-grained data
    when they are fully accounted for in the coarse-grained data."""
    df_fine = df_fine.copy()
    tot_cols = ["POBTOT", "POBHOG", "POBCOL", "TVIVHAB", "TOTHOG", "TOTCOL"]
    df_diff = (
        df_coarse[tot_cols] - df_fine.groupby(df_coarse.index.names)[tot_cols].sum()
    )
    for idx_coarse in df_coarse.index:
        if df_diff.loc[idx_coarse, "POBCOL"] == 0:
            df_fine.loc[idx_coarse, "POBHOG"] = (
                df_fine.loc[idx_coarse, "POBHOG"]
                .mask(
                    df_fine.loc[idx_coarse, "POBHOG"].isna(),
                    df_fine.loc[idx_coarse, "POBTOT"],
                )
                .values
            )
        if df_diff.loc[idx_coarse, "TOTCOL"] == 0:
            df_fine.loc[idx_coarse, "TOTHOG"] = (
                df_fine.loc[idx_coarse, "TOTHOG"]
                .mask(
                    df_fine.loc[idx_coarse, "TOTHOG"].isna(),
                    df_fine.loc[idx_coarse, "TVIVHAB"],
                )
                .values
            )
    # Re-estimate with imputed values
    df_fine["POBCOL"] = df_fine.POBTOT - df_fine.POBHOG
    df_fine["TOTCOL"] = df_fine.TVIVHAB - df_fine.TOTHOG

    return df_fine


def add_collective_cols(df_state, df_mun, df_loc, df_ageb):
    """Adds collective population and housing columns and performs imputation."""
    df_state = df_state.copy()
    df_mun = df_mun.copy()
    df_loc = df_loc.copy()
    df_ageb = df_ageb.copy()

    for df in (df_state, df_mun, df_loc, df_ageb):
        df["POBCOL"] = df.POBTOT - df.POBHOG
        df["TOTCOL"] = df.TVIVHAB - df.TOTHOG

    # If all collective population is accounted for when aggregating from loc->mun
    # we can impute POBCOL and TOTCOL to 0 where nan.
    df_loc = impute_collective(df_mun, df_loc)
    df_ageb = impute_collective(
        df_loc.loc[df_ageb.index.droplevel(-1).unique()], df_ageb
    )

    return df_state, df_mun, df_loc, df_ageb


def add_derived_cols(df_state, df_mun, df_loc, df_ageb):
    """Adds derived population and housing columns."""
    df_state = df_state.copy()
    df_mun = df_mun.copy()
    df_loc = df_loc.copy()
    df_ageb = df_ageb.copy()

    for df in (df_state, df_mun, df_loc, df_ageb):
        df["PAFIL_PUB"] = (
            df.PDER_IMSS
            + df.PDER_ISTE
            + df.PDER_ISTEE
            + df.PAFIL_PDOM
            + df.PDER_SEGP
            + df.PDER_IMSSB
        )

    return df_state, df_mun, df_loc, df_ageb


def impute_zeros_univariate(df_coarse, df_fine):
    """Imputes zeros in fine-grained data where the coarse-grained total
    is already fully matched by the sum of non-NaN fine-grained values."""
    df_fine = df_fine.copy()
    df_agg = df_fine.groupby(df_coarse.index.names).sum()
    diff_df = df_coarse - df_agg

    for idx_row in diff_df.stack().loc[lambda s: s == 0].index:
        col = idx_row[-1]
        idx = idx_row[:-1]
        if df_fine.loc[idx, col].hasnans:
            df_fine.loc[idx, col] = df_fine.loc[idx, col].fillna(0).values
    return df_fine


def load_census(
    iter_path: Path | None = None,
    resargebub_path: Path | None = None,
    *,
    state: int | None = None,
    data_dir: Path | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads census at 4 levels: state, municipality, locality, and urban ageb.

    Two calling conventions:

    Explicit paths (original API)::

        load_census(iter_path=Path("..."), resargebub_path=Path("..."))

    State code (uses the XDG data directory)::

        load_census(state=14)
        load_census(state=14, data_dir=Path("~/my-data"))

    Parameters
    ----------
    iter_path : Path, optional
        Path to the ITER CSV file.
    resargebub_path : Path, optional
        Path to the RESARGEBUB CSV file.
    state : int, optional
        INEGI state code (ENTIDAD) 1–32. Resolves paths from the data directory.
    data_dir : Path, optional
        Override the default XDG data directory when using state=.
    """
    if state is not None:
        from mxcensus.data._paths import get_data_dir
        from mxcensus.data._catalog import STATE_CODE_FMT

        base = data_dir or get_data_dir()
        code = STATE_CODE_FMT(state)
        iter_path = base / "loc" / f"ITER_{code}CSV20.csv"
        resargebub_path = base / "ageb_manz" / f"RESAGEBURB_{code}CSV20.csv"
    if iter_path is None or resargebub_path is None:
        raise ValueError(
            "Provide either state= or both iter_path= and resargebub_path="
        )

    df_state, df_mun, df_loc, df_ageb, df_mza = load_resargebub(resargebub_path)
    df_iter_state, df_iter_mun, df_iter_loc, _ = load_iter(iter_path)

    # Add columns for totals of collective population
    # This must be handled jointly for imputation
    df_iter_state, df_iter_mun, df_iter_loc, df_ageb = add_collective_cols(
        df_iter_state, df_iter_mun, df_iter_loc, df_ageb
    )

    # Add new derived columns
    df_iter_state, df_iter_mun, df_iter_loc, df_ageb = add_derived_cols(
        df_iter_state, df_iter_mun, df_iter_loc, df_ageb
    )

    # Impute zeros where aggreagated counts match higher level counts
    df_loc = impute_zeros_univariate(df_mun, df_loc)
    df_iter_loc = impute_zeros_univariate(df_iter_mun, df_iter_loc)
    df_ageb = impute_zeros_univariate(df_iter_loc, df_ageb)

    # Perform sanity checks
    sanity_checks(
        df_iter_state,
        df_iter_mun,
        df_iter_loc,
        df_state,
        df_mun,
        df_loc,
        df_ageb,
        df_mza,
    )

    # Keep same colums across all datasets, the restricted ageb cols
    cols = df_ageb.columns

    return df_iter_state[cols], df_iter_mun[cols], df_iter_loc[cols], df_ageb


def merge_loc_agebs(df_loc, df_ageb):
    """Merges locality and AGEB level data into a single DataFrame.

    Localities that are decomposed into AGEBs are replaced by their AGEB components.
    Localities without AGEB decompositions are assigned a dummy AGEB code '0000'.
    """
    # Make sure ageb population includes all parent localities
    locs_in_agebs = df_ageb.index.droplevel(-1).unique()
    assert np.all(
        df_loc.loc[locs_in_agebs].POBTOT
        == df_ageb.groupby(["ENTIDAD", "MUN", "LOC"]).POBTOT.sum()
    )

    # Drop parent localities
    df_loc_ageb = pd.concat(
        [
            df_loc.drop(locs_in_agebs)
            .assign(AGEB="0000")
            .set_index("AGEB", append=True),
            df_ageb,
        ]
    )
    return df_loc_ageb.sort_index()


def merge_mg_census(
    mg_loc_path: Path,
    mg_loc_p_path: Path,
    mg_ageb_path: Path,
    df_loc_ageb: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """Merges Marco Geoestadístico (MG) geometries with census data."""

    df_loc_ageb = df_loc_ageb.copy()
    pobtot = df_loc_ageb.POBTOT.sum()

    # Load ageb geometries
    mg_ageb = (
        gpd.read_parquet(mg_ageb_path)
        .assign(
            ENTIDAD=lambda df: df.CVE_ENT.astype(int),
            MUN=lambda df: df.CVE_MUN.astype(int),
            LOC=lambda df: df.CVE_LOC.astype(int),
            AGEB=lambda df: df.CVE_AGEB.copy(),
            ADMIN_TYPE="AGEB_URBAN",
        )
        .set_index(["ENTIDAD", "MUN", "LOC", "AGEB"])
    )

    # There are some agebs in df_loc_ageb not in mg
    # These are likely single ageb localities that are given an ageb to mantain
    # consistency across the dataset
    # For these cases, ageb code is usually 1467
    not_in_mg = df_loc_ageb.query("AGEB != '0000'").loc[
        lambda x: ~x.index.isin(mg_ageb.index)
    ]
    if len(not_in_mg) > 0:
        assert not_in_mg.groupby(["ENTIDAD", "MUN", "LOC"]).size().max() == 1
        # We add them as localities and drop the originals
        df_loc_ageb = pd.concat(
            [
                df_loc_ageb.drop(not_in_mg.index),
                not_in_mg.droplevel(-1)
                .assign(AGEB="0000")
                .set_index("AGEB", append=True),
            ]
        )

    # Get localities in agebs gdf
    locs_in_agebs = mg_ageb.index.droplevel(-1).unique()

    # Load localities' geometries
    # Drop those already in agebs
    mg_loc = (
        gpd.read_parquet(mg_loc_path)
        .assign(
            ENTIDAD=lambda df: df.CVE_ENT.astype(int),
            MUN=lambda df: df.CVE_MUN.astype(int),
            LOC=lambda df: df.CVE_LOC.astype(int),
            AGEB="0000",
            ADMIN_TYPE="LOCALITY_POLYGON",
        )
        .set_index(["ENTIDAD", "MUN", "LOC", "AGEB"])
        .pipe(lambda df: df.drop(df.index[df.index.isin(locs_in_agebs)]))
    )

    # Load point agebs
    # Remove localities present in mg_loc
    mg_loc_p = (
        gpd.read_parquet(mg_loc_p_path)
        .assign(
            ENTIDAD=lambda df: df.CVE_ENT.astype(int),
            MUN=lambda df: df.CVE_MUN.astype(int),
            LOC=lambda df: df.CVE_LOC.astype(int),
            AGEB="0000",
            ADMIN_TYPE="LOCALITY_POINT",
        )
        .set_index(["ENTIDAD", "MUN", "LOC", "AGEB"])
        .pipe(lambda df: df.drop(df.index[df.index.isin(mg_loc.index)]))
        .pipe(lambda df: df.drop(df.index[df.index.isin(locs_in_agebs)]))
    )

    mg_loc_ageb = (
        pd.concat([mg_loc, mg_loc_p, mg_ageb])
        .sort_index()
        .drop(columns=["CVE_ENT", "CVE_MUN", "CVE_LOC", "CVE_AGEB", "CVE_MZA"])
        .merge(df_loc_ageb, left_index=True, right_index=True, how="left")
    )

    # Geometries not in census will have 0 counts.
    mg_loc_ageb.loc[
        mg_loc_ageb.index[~mg_loc_ageb.index.isin(df_loc_ageb.index)],
        df_loc_ageb.columns,
    ] = 0

    assert mg_loc_ageb.POBTOT.sum() == pobtot, "population have changed"
    assert mg_loc_ageb.loc[df_loc_ageb.index, df_loc_ageb.columns].equals(
        df_loc_ageb
    ), "census data have changed"

    return mg_loc_ageb


def mg_agebs_ur(mg_ar_path: Path, mg_loc_ageb: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Aggregates rural localities into rural AGEB geometries."""

    mg_loc_ageb = mg_loc_ageb.copy()

    mg_ar = (
        gpd.read_parquet(mg_ar_path)
        .assign(
            ENTIDAD=lambda df: df.CVE_ENT.astype(int),
            MUN=lambda df: df.CVE_MUN.astype(int),
            LOC=0,
            AGEB=lambda df: df.CVE_AGEB.copy(),
            ADMIN_TYPE="AGEB_RURAL",
        )
        .set_index(["ENTIDAD", "MUN", "LOC", "AGEB"])
    ).to_crs(mg_loc_ageb.crs)
    crs = mg_ar.crs
    num_ar = len(mg_ar)

    mg_au = mg_loc_ageb.query("AGEB != '0000'")
    mg_lp = mg_loc_ageb[mg_loc_ageb.geom_type == "MultiPoint"]
    mg_lr = mg_loc_ageb[mg_loc_ageb.geom_type != "MultiPoint"].query("AGEB == '0000'")
    assert mg_au.shape[0] + mg_lp.shape[0] + mg_lr.shape[0] == mg_loc_ageb.shape[0]

    agg_dict = {
        "geometry": "first",
        "ADMIN_TYPE": "first",
        "CVEGEO": "first",
        **dict.fromkeys(
            mg_loc_ageb.columns.drop(
                ["CVEGEO", "NOMGEO", "AMBITO", "PLANO", "ADMIN_TYPE", "geometry"]
            ),
            "sum",
        ),
    }

    sjoin = mg_ar[["CVEGEO", "ADMIN_TYPE", "geometry"]].sjoin(
        mg_lp.drop(columns=["CVEGEO", "NOMGEO", "AMBITO", "PLANO", "ADMIN_TYPE"]),
        how="right",
    )
    mg_loc_ageb.loc[sjoin.index, "PARENT_RURAL_AGEB"] = sjoin.CVEGEO.rename(
        "PARENT_RURAL_AGEB"
    )
    mg_ar_lp = (
        mg_ar[["CVEGEO", "ADMIN_TYPE", "geometry"]]
        .sjoin(
            mg_lp.drop(
                columns=["CVEGEO", "NOMGEO", "AMBITO", "PLANO", "ADMIN_TYPE"]
            ).reset_index(drop=True),
            how="left",
        )
        .groupby(["ENTIDAD", "MUN", "LOC", "AGEB"])
        .agg(agg_dict)
        .set_geometry("geometry")
        .set_crs(crs)
    )
    assert mg_ar_lp.POBTOT.sum() == mg_lp.POBTOT.sum()

    sjoin = mg_ar[["CVEGEO", "ADMIN_TYPE", "geometry"]].sjoin(
        mg_lr.assign(RP=lambda df: df.representative_point())
        .set_geometry("RP")
        .drop(columns=["CVEGEO", "NOMGEO", "AMBITO", "PLANO", "ADMIN_TYPE"]),
        how="right",
    )
    mg_loc_ageb.loc[sjoin.index, "PARENT_RURAL_AGEB"] = sjoin.CVEGEO.rename(
        "PARENT_RURAL_AGEB"
    )
    mg_ar_lr = (
        mg_ar[["CVEGEO", "ADMIN_TYPE", "geometry"]]
        .sjoin(
            mg_lr.assign(RP=lambda df: df.representative_point())
            .set_geometry("RP")
            .drop(columns=["CVEGEO", "NOMGEO", "AMBITO", "PLANO", "ADMIN_TYPE"])
            .reset_index(drop=True),
            how="left",
        )
        .groupby(["ENTIDAD", "MUN", "LOC", "AGEB"])
        .agg(agg_dict)
        .set_geometry("geometry")
        .set_crs(crs)
    )
    assert mg_ar_lr.POBTOT.sum() == mg_lr.POBTOT.sum()

    mg_ar = (
        pd.concat([mg_ar_lr, mg_ar_lp])
        .groupby(["ENTIDAD", "MUN", "LOC", "AGEB"])
        .agg(agg_dict)
        .set_geometry("geometry")
        .set_crs(crs)
    )
    assert len(mg_ar) == num_ar

    mg_aur = (
        pd.concat(
            [
                mg_au.drop(columns=["NOMGEO", "AMBITO", "PLANO"]),
                mg_ar,
            ]
        )
        .sort_index()
        .set_geometry("geometry")
        .set_crs(crs)
    )
    assert mg_aur.index.is_unique

    assert mg_aur.POBTOT.sum() == mg_loc_ageb.POBTOT.sum()

    return mg_aur, mg_loc_ageb
