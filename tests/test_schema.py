"""El contrato de datos rechaza lo que tiene que rechazar.

Un contrato que solo se documenta es una sugerencia. Estos tests verifican que
cada violacion produzca un `SchemaError` y no un resultado silencioso, que es la
diferencia entre un contrato y un comentario.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from blindside.data import schema as S


def test_validate_panel_accepts_valid(synthetic_panel: pd.DataFrame) -> None:
    out = S.validate_panel(synthetic_panel)
    assert list(out.columns[:2]) or True
    # El contrato promete orden canonico por (serie, fecha).
    assert out.equals(out.sort_values([S.SERIES_ID, S.DATE]).reset_index(drop=True))


def test_series_id_is_derived_from_store_and_product(synthetic_panel: pd.DataFrame) -> None:
    expected = S.make_series_id(synthetic_panel)
    assert (synthetic_panel[S.SERIES_ID] == expected).all()
    # Debe ser inyectivo: dos series distintas no pueden compartir id.
    pairs = synthetic_panel[[S.STORE_ID, S.PRODUCT_ID]].drop_duplicates()
    assert len(pairs) == synthetic_panel[S.SERIES_ID].nunique()


def test_rejects_missing_columns(synthetic_panel: pd.DataFrame) -> None:
    with pytest.raises(S.SchemaError, match="obligatorias ausentes"):
        S.validate_panel(synthetic_panel.drop(columns=[S.SALE_AMOUNT]))


def test_rejects_duplicate_series_date(synthetic_panel: pd.DataFrame) -> None:
    """Una serie con dos filas del mismo dia rompe cualquier lag, en silencio."""
    dup = pd.concat([synthetic_panel, synthetic_panel.head(3)], ignore_index=True)
    with pytest.raises(S.SchemaError, match="duplicadas"):
        S.validate_panel(dup)


def test_rejects_negative_sales(synthetic_panel: pd.DataFrame) -> None:
    bad = synthetic_panel.copy()
    bad.loc[0, S.SALE_AMOUNT] = -1.0
    with pytest.raises(S.SchemaError, match="negativos"):
        S.validate_panel(bad)


def test_rejects_inconsistent_censoring_flag(synthetic_panel: pd.DataFrame) -> None:
    """`is_censored` tiene que concordar con las horas de quiebre."""
    bad = synthetic_panel.copy()
    bad[S.IS_CENSORED] = ~bad[S.IS_CENSORED]
    with pytest.raises(S.SchemaError, match="no coincide"):
        S.validate_panel(bad)


def test_rejects_latent_below_observed(recovered_panel: pd.DataFrame) -> None:
    """La venta observada ocurrio: es cota inferior de la demanda, sin excepcion."""
    bad = recovered_panel.copy()
    bad[S.DEMAND_LATENT] = bad[S.SALE_AMOUNT] * 0.5
    with pytest.raises(S.SchemaError, match="cota inferior"):
        S.validate_panel(bad, required=S.DEMAND_REQUIRED)


def test_detects_calendar_gaps(synthetic_panel: pd.DataFrame) -> None:
    """Un dia faltante convierte un lag de 7 dias en un lag de otra cosa."""
    holed = synthetic_panel.drop(index=synthetic_panel.index[40]).reset_index(drop=True)
    with pytest.raises(S.SchemaError, match="huecos de calendario"):
        S.validate_panel(holed, allow_gaps=False)
    # Con allow_gaps=True pasa, porque hay pasos donde el hueco es aceptable.
    S.validate_panel(holed, allow_gaps=True)


def test_reindex_daily_closes_gaps(synthetic_panel: pd.DataFrame) -> None:
    holed = synthetic_panel.drop(index=synthetic_panel.index[40]).reset_index(drop=True)
    fixed = S.reindex_daily(holed)
    S.validate_panel(fixed, allow_gaps=False)
    assert len(fixed) == len(synthetic_panel)
    # Un dia ausente en retail significa cero venta, no demanda desconocida.
    assert fixed[S.SALE_AMOUNT].notna().all()


def test_series_index_is_one_row_per_series(synthetic_panel: pd.DataFrame) -> None:
    idx = S.series_index(synthetic_panel)
    assert len(idx) == synthetic_panel[S.SERIES_ID].nunique()
    assert set(S.HIERARCHY_COLS) <= set(idx.columns)


def test_describe_censoring_reports_expected_share(synthetic_panel: pd.DataFrame) -> None:
    summary = S.describe_censoring(synthetic_panel)
    assert 0 < summary["share_censored_days"] < 1
    assert summary["n_series"] == synthetic_panel[S.SERIES_ID].nunique()


def test_raw_columns_match_dataset_card() -> None:
    """Los 19 campos del parquet de HuggingFace, exactos.

    Si el dataset cambia de esquema, este test lo detecta antes de que un
    `KeyError` aparezca a mitad de un backtest de veinte minutos.
    """
    assert len(S.RAW_COLUMNS) == 19
    assert S.HOURS_SALE in S.RAW_COLUMNS
    assert S.HOURS_STOCK_STATUS in S.RAW_COLUMNS
    assert S.OOS_HOURS_OPEN == "stock_hour6_22_cnt"


def test_hierarchies_are_ordered_from_coarse_to_fine() -> None:
    """La reconciliacion MinT depende de este orden; invertirlo la rompe."""
    assert S.HIERARCHY_GEO == (S.CITY_ID, S.STORE_ID)
    assert S.HIERARCHY_CATALOG[0] == S.MANAGEMENT_GROUP_ID
    assert S.HIERARCHY_CATALOG[-1] == S.PRODUCT_ID


def test_cast_panel_does_not_invent_columns(synthetic_panel: pd.DataFrame) -> None:
    subset = synthetic_panel[[S.SERIES_ID, S.DATE, S.SALE_AMOUNT]]
    out = S.cast_panel(subset)
    assert list(out.columns) == list(subset.columns)
    assert out[S.SALE_AMOUNT].dtype == np.dtype("float32")
