"""Features y validacion temporal.

El foco esta en la convencion del modulo de lags — "la fila `t` usa `y[t]` y
anteriores" — porque es la que sostiene todo el diseno antifugas. Si esa
convencion se rompe, los tests de `test_leakage.py` pierden sentido.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dfcore.data import schema as S
from dfcore.features import build as fb
from dfcore.features import calendar as cal
from dfcore.features import lags as lg
from dfcore.validation.splits import Fold, RollingOriginSplitter, rotation_bands


# --- Calendario ---------------------------------------------------------
def test_calendar_features_are_all_present(recovered_panel: pd.DataFrame) -> None:
    out = cal.add_calendar_features(recovered_panel)
    assert set(cal.CALENDAR_FEATURES) <= set(out.columns)


def test_cyclic_encoding_makes_sunday_and_monday_neighbours() -> None:
    """Domingo (6) y lunes (0) son vecinos, no extremos opuestos.

    Es el motivo de codificar el dia de la semana con seno y coseno ademas del
    entero: un modelo lineal con solo el entero trataria el salto 6 -> 0 como el
    mas grande de la semana cuando es el mas chico.
    """
    df = pd.DataFrame({S.DATE: pd.date_range("2024-01-01", periods=8, freq="D")})
    out = cal.add_calendar_features(df)
    coords = out[["dow_sin", "dow_cos"]].to_numpy()
    dow = out["dow"].to_numpy()

    sunday = coords[dow == 6][0]
    monday = coords[dow == 0][0]
    wednesday = coords[dow == 2][0]
    assert np.linalg.norm(sunday - monday) < np.linalg.norm(sunday - wednesday)


def test_trend_feature_is_anchored_on_a_fixed_epoch() -> None:
    """La misma fecha tiene que dar el mismo valor de tendencia en cualquier frame.

    Anclar la tendencia en `df[date].min()` es un bug silencioso: el frame de
    entrenamiento abarca decenas de dias y el de inferencia solo el horizonte, asi
    que la feature significa cosas distintas a cada lado del `fit`. Un arbol lo
    tolera, un modelo lineal extrapola sobre la escala equivocada y explota.
    """
    early = pd.DataFrame({S.DATE: pd.date_range("2024-04-01", periods=30, freq="D")})
    late = pd.DataFrame({S.DATE: pd.date_range("2024-06-20", periods=7, freq="D")})

    a = cal.add_calendar_features(early)
    b = cal.add_calendar_features(late)

    # El 2024-06-20 aparece solo en el segundo frame; su valor no puede depender
    # de que ese frame empiece ahi.
    expected = (pd.Timestamp("2024-06-20") - cal.TREND_EPOCH).days
    assert b.loc[0, "days_since_start"] == expected
    # Y el primer frame no arranca en cero.
    assert a.loc[0, "days_since_start"] == (pd.Timestamp("2024-04-01") - cal.TREND_EPOCH).days
    assert a.loc[0, "days_since_start"] != 0


def test_trend_is_consistent_between_training_and_inference(
    recovered_panel: pd.DataFrame,
) -> None:
    """El rango de la tendencia en inferencia tiene que continuar el del train.

    Es la version de punta a punta del test de arriba: se compara lo que ve el
    modelo al entrenar contra lo que ve al predecir, atravesando el ensamblado
    supervisado y el estado de origen congelado.
    """
    from dfcore.evaluate.backtest import _future_index
    from dfcore.models.linear import RidgeForecaster
    from dfcore.validation.splits import Fold

    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]

    model = RidgeForecaster(max_train_origins=6).fit(history, target=S.DEMAND_LATENT)
    future = _future_index(recovered_panel, Fold(index=0, origin=origin, horizon=7))
    x_infer = model._assemble(future)

    state = fb.add_origin_features(history, target=S.DEMAND_LATENT)
    origins = pd.DatetimeIndex(sorted(state[S.DATE].unique()))[-14:-1:2]
    sup = fb.build_supervised(state, origins, horizon=7, target=S.DEMAND_LATENT)

    train_max = int(sup["days_since_start"].max())
    infer_min = int(x_infer["days_since_start"].min())
    # La inferencia arranca dentro del rango de train o inmediatamente despues,
    # nunca decenas de dias antes.
    assert infer_min >= train_max - 7, (
        f"la tendencia en inferencia ({infer_min}) no continua la del train "
        f"({train_max}): la feature esta anclada a cada frame"
    )


def test_easter_dates_are_correct() -> None:
    """Fechas de Pascua verificadas: el algoritmo de Butcher no se testea solo."""
    assert cal._easter(2024) == pd.Timestamp("2024-03-31")
    assert cal._easter(2025) == pd.Timestamp("2025-04-20")
    assert cal._easter(2026) == pd.Timestamp("2026-04-05")


def test_paraguayan_holidays_include_fixed_and_movable() -> None:
    hol = cal.paraguayan_holidays([2026])
    assert pd.Timestamp("2026-05-14") in hol  # Independencia
    assert pd.Timestamp("2026-04-03") in hol  # Viernes Santo 2026
    assert pd.Timestamp("2026-04-02") in hol  # Jueves Santo 2026


def test_holiday_proximity_is_signed() -> None:
    """El pico de compra en perecederos es el dia previo, no el feriado.

    Por eso importa el signo: una bandera binaria de un dia no distingue "manana
    es feriado" de "ayer fue feriado", y el comportamiento de compra es opuesto.
    """
    df = pd.DataFrame({S.DATE: pd.date_range("2026-05-12", periods=5, freq="D")})
    out = cal.add_holiday_proximity(df, pd.DatetimeIndex([pd.Timestamp("2026-05-14")]))
    assert out["days_to_holiday"].tolist() == [-2, -1, 0, 1, 2]
    assert out["is_holiday"].tolist() == [0, 0, 1, 0, 0]


# --- Convencion de lags -------------------------------------------------
def test_lag_zero_is_the_current_day(recovered_panel: pd.DataFrame) -> None:
    """`lag_0` es `y[t]`. Es legitimo: al cerrar el dia t ese valor se conoce."""
    out = lg.add_lag_features(recovered_panel, target=S.DEMAND_LATENT, lags=(0, 1))
    assert np.allclose(out["latent_lag_0"], out[S.DEMAND_LATENT], atol=1e-5)


def test_lag_one_is_the_previous_day_within_the_series(recovered_panel: pd.DataFrame) -> None:
    out = lg.add_lag_features(recovered_panel, target=S.DEMAND_LATENT, lags=(1,))
    one = out[out[S.SERIES_ID] == out[S.SERIES_ID].iloc[0]].sort_values(S.DATE)
    assert np.isnan(one["latent_lag_1"].iloc[0])
    assert np.allclose(
        one["latent_lag_1"].to_numpy()[1:], one[S.DEMAND_LATENT].to_numpy()[:-1], atol=1e-5
    )


def test_rolling_window_closes_at_t() -> None:
    """La media movil de 3 en `t` cubre `t-2..t`, con `t` incluido."""
    df = pd.DataFrame(
        {
            S.SERIES_ID: ["1_1"] * 5,
            S.DATE: pd.date_range("2024-01-01", periods=5, freq="D"),
            S.DEMAND_LATENT: [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )
    out = lg.add_rolling_features(df, target=S.DEMAND_LATENT, windows=(3,))
    # En t=3 (valor 4) la ventana es 2, 3, 4 -> media 3.
    assert out["latent_roll_mean_3"].iloc[3] == pytest.approx(3.0)


def test_seasonal_feature_averages_the_same_weekday() -> None:
    df = pd.DataFrame(
        {
            S.SERIES_ID: ["1_1"] * 15,
            S.DATE: pd.date_range("2024-01-01", periods=15, freq="D"),
            S.DEMAND_LATENT: [10.0] + [0.0] * 6 + [20.0] + [0.0] * 6 + [99.0],
        }
    )
    out = lg.add_seasonal_features(df, target=S.DEMAND_LATENT, season_length=7, n_cycles=2)
    # En la posicion 14, los mismos dias de semana previos son 7 y 0 -> 20 y 10.
    assert out["latent_dow_mean_2"].iloc[14] == pytest.approx(15.0)


def test_days_since_sale_counts_correctly() -> None:
    df = pd.DataFrame(
        {
            S.SERIES_ID: ["1_1"] * 6,
            S.DATE: pd.date_range("2024-01-01", periods=6, freq="D"),
            S.DEMAND_LATENT: [5.0, 0.0, 0.0, 3.0, 0.0, 0.0],
        }
    )
    out = lg.add_intermittency_features(df, target=S.DEMAND_LATENT, windows=(3,))
    assert out["days_since_sale"].tolist() == [0.0, 1.0, 2.0, 0.0, 1.0, 2.0]


def test_censoring_history_is_a_feature(recovered_panel: pd.DataFrame) -> None:
    """Que una serie venga quebrando seguido es informacion real sobre su demanda."""
    out = lg.add_censoring_history(recovered_panel, windows=(7,))
    assert "censored_share_7" in out.columns
    share = out["censored_share_7"].dropna()
    assert ((share >= 0) & (share <= 1)).all()


# --- Ensamblado supervisado --------------------------------------------
def test_supervised_matrix_shape(supervised_matrix: pd.DataFrame) -> None:
    n_series = supervised_matrix[S.SERIES_ID].nunique()
    n_origins = supervised_matrix[fb.ORIGIN_DATE].nunique()
    assert len(supervised_matrix) == n_series * n_origins * 7


def test_target_date_is_origin_plus_h(supervised_matrix: pd.DataFrame) -> None:
    delta = (supervised_matrix[S.DATE] - supervised_matrix[fb.ORIGIN_DATE]).dt.days
    assert (delta == supervised_matrix[fb.H]).all()
    assert supervised_matrix[fb.H].min() == 1
    assert supervised_matrix[fb.H].max() == 7


def test_feature_columns_exclude_labels_and_keys(supervised_matrix: pd.DataFrame) -> None:
    features = fb.feature_columns(supervised_matrix)
    for banned in (fb.Y, fb.Y_OBSERVED, S.SERIES_ID, S.DATE, fb.ORIGIN_DATE, S.IS_CENSORED):
        assert banned not in features
    assert fb.H in features  # el paso de horizonte SI es feature
    assert "dow" in features


def test_known_future_covariates_come_from_the_target_date(
    recovered_panel: pd.DataFrame,
) -> None:
    """Descuento y feriado del dia objetivo son legitimos: se planifican antes.

    El clima **no** entra asi, porque a 7 dias no se conoce. Solo aparece
    rezagado y anclado en el origen.
    """
    state = fb.add_origin_features(recovered_panel, target=S.DEMAND_LATENT)
    origins = pd.DatetimeIndex(sorted(state[S.DATE].unique()))[-15:-9]
    sup = fb.build_supervised(state, origins, horizon=7, target=S.DEMAND_LATENT)

    features = fb.feature_columns(sup)
    assert S.DISCOUNT in features
    # El clima crudo del dia objetivo no puede estar; solo sus rezagos.
    for weather in S.WEATHER_COLS:
        assert weather not in features, f"{weather} del dia objetivo es fuga"
        assert f"{weather}_lag_0" in features


def test_inference_matrix_does_not_need_the_target(recovered_panel: pd.DataFrame) -> None:
    """En inferencia real todavia no hay verdad; el ensamblado tiene que aceptarlo."""
    state = fb.add_origin_features(recovered_panel, target=S.DEMAND_LATENT)
    last = pd.DatetimeIndex(sorted(state[S.DATE].unique()))[-1:]
    sup = fb.build_supervised(state, last, horizon=7, target=S.DEMAND_LATENT, include_target=False)
    assert fb.Y not in sup.columns
    assert len(sup) == state[S.SERIES_ID].nunique() * 7


def test_make_origins_leaves_room_for_the_horizon(recovered_panel: pd.DataFrame) -> None:
    """El objetivo mas lejano del ultimo origen tiene que caer dentro del panel.

    Un fold cuyo ultimo dia de test se sale del panel queda incompleto en
    silencio: el `merge` con la verdad simplemente descarta esa fila y el fold
    evalua 6 dias donde declara 7.
    """
    origins = fb.make_origins(recovered_panel, horizon=7, min_train_days=42)
    last_date = recovered_panel[S.DATE].max()
    assert (origins.max() + pd.Timedelta(days=7)) == last_date
    assert origins.min() == pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))[41]


# --- Splits -------------------------------------------------------------
def test_splitter_produces_the_requested_origins(recovered_panel: pd.DataFrame) -> None:
    splitter = RollingOriginSplitter(horizon=7, n_origins=8, step=3, min_train_days=42)
    folds = splitter.folds(recovered_panel)
    assert len(folds) == 8
    origins = [f.origin for f in folds]
    assert origins == sorted(origins)  # cronologico
    gaps = {(b - a).days for a, b in zip(origins[:-1], origins[1:], strict=True)}
    assert gaps == {3}


def test_last_origin_leaves_exactly_the_horizon(recovered_panel: pd.DataFrame) -> None:
    splitter = RollingOriginSplitter(horizon=7, n_origins=8, step=3, min_train_days=42)
    folds = splitter.folds(recovered_panel)
    assert folds[-1].test_end == recovered_panel[S.DATE].max()


def test_splitter_fails_loudly_when_history_is_short(recovered_panel: pd.DataFrame) -> None:
    """Correr con 3 origenes donde la metodologia declara 8 es una discrepancia
    que un panel encuentra. Mejor fallar y decir cuantos entran."""
    splitter = RollingOriginSplitter(horizon=28, n_origins=8, step=7, min_train_days=42)
    with pytest.raises(ValueError, match="solo admite"):
        splitter.folds(recovered_panel)


def test_max_origins_matches_the_formula() -> None:
    splitter = RollingOriginSplitter(horizon=7, n_origins=8, step=3, min_train_days=42)
    # (97 - 42 - 7) // 3 + 1 = 17
    assert splitter.max_origins(97) == 17
    assert splitter.max_origins(40) == 0


def test_fold_masks_are_complementary(recovered_panel: pd.DataFrame) -> None:
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    fold = Fold(index=0, origin=dates[-15], horizon=7)
    train = fold.train_mask(recovered_panel[S.DATE])
    test = fold.test_mask(recovered_panel[S.DATE])
    assert not (train & test).any()
    assert fold.gap_days == 7
    assert (fold.test_end - fold.train_end).days == 7


def test_rotation_bands_use_only_the_early_window(recovered_panel: pd.DataFrame) -> None:
    """Las bandas se definen con el train del primer origen, no con todo el panel.

    Elegir los grupos del reporte sabiendo el resultado del test seria una fuga
    de otro tipo: no contamina el modelo, contamina la conclusion.
    """
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    early = recovered_panel[recovered_panel[S.DATE] <= dates[41]]
    bands = rotation_bands(early, target=S.DEMAND_LATENT)
    assert set(bands.unique()) <= {"baja", "media", "alta"}
    assert len(bands) == recovered_panel[S.SERIES_ID].nunique()
