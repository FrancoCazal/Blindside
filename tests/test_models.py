"""Los modelos respetan el contrato y los baselines calculan lo que prometen.

Los baselines se verifican contra su definicion aritmetica, no contra su propia
salida. Un baseline mal implementado corrompe el denominador de MASE y con el
todos los resultados del proyecto, asi que vale la pena chequearlos a mano.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dfcore.data import schema as S
from dfcore.models import baselines as B
from dfcore.models.base import Forecaster, NotFittedError, quantile_col


def _tiny_panel(values: dict[str, list[float]]) -> pd.DataFrame:
    """Panel minimo con las columnas del contrato, para verificar aritmetica."""
    rows = []
    for sid, series in values.items():
        store, product = sid.split("_")
        for i, v in enumerate(series):
            rows.append(
                {
                    S.SERIES_ID: sid,
                    S.DATE: pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
                    S.STORE_ID: int(store),
                    S.PRODUCT_ID: int(product),
                    S.DEMAND_LATENT: float(v),
                }
            )
    return pd.DataFrame(rows)


def _future(sid: str, origin: pd.Timestamp, horizon: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            S.SERIES_ID: [sid] * horizon,
            S.DATE: [origin + pd.Timedelta(days=h) for h in range(1, horizon + 1)],
            "h": list(range(1, horizon + 1)),
        }
    )


# --- Aritmetica de los baselines ----------------------------------------
def test_naive_repeats_last_value() -> None:
    panel = _tiny_panel({"1_1": [1, 2, 3, 4, 5]})
    model = B.NaiveForecaster().fit(panel, target=S.DEMAND_LATENT)
    preds = model.predict(_future("1_1", pd.Timestamp("2024-01-05"), 3))
    assert preds.tolist() == [5.0, 5.0, 5.0]


def test_seasonal_naive_repeats_the_same_weekday() -> None:
    """h=1 toma el valor de hace 7 dias; h=8 recicla el mismo ciclo."""
    panel = _tiny_panel({"1_1": [10, 20, 30, 40, 50, 60, 70, 11, 21, 31, 41, 51, 61, 71]})
    model = B.SeasonalNaiveForecaster(season_length=7).fit(panel, target=S.DEMAND_LATENT)
    origin = pd.Timestamp("2024-01-14")
    preds = model.predict(_future("1_1", origin, 8))
    assert preds.tolist()[:7] == [11.0, 21.0, 31.0, 41.0, 51.0, 61.0, 71.0]
    assert preds.tolist()[7] == 11.0  # el ciclo se recicla


def test_moving_average_uses_the_window() -> None:
    panel = _tiny_panel({"1_1": [0, 0, 0, 3, 6, 9]})
    model = B.MovingAverageForecaster(window=3).fit(panel, target=S.DEMAND_LATENT)
    preds = model.predict(_future("1_1", pd.Timestamp("2024-01-06"), 2))
    assert preds.tolist() == [6.0, 6.0]  # media de 3, 6, 9


def test_seasonal_moving_average_averages_the_same_weekday() -> None:
    panel = _tiny_panel({"1_1": [10, 0, 0, 0, 0, 0, 0, 20, 0, 0, 0, 0, 0, 0]})
    model = B.SeasonalMovingAverageForecaster(season_length=7, n_cycles=2).fit(
        panel, target=S.DEMAND_LATENT
    )
    preds = model.predict(_future("1_1", pd.Timestamp("2024-01-14"), 1))
    # El dia siguiente al ultimo corresponde a las posiciones 10 y 20.
    assert preds.iloc[0] == pytest.approx(15.0)


def test_croston_estimates_the_demand_rate() -> None:
    """Demanda de 4 unidades cada 4 dias tiene que dar una tasa cercana a 1.

    Con SBA la tasa se multiplica por (1 - alpha/2), asi que queda algo por
    debajo de 1. Eso es la correccion de sesgo, no un error.
    """
    panel = _tiny_panel({"1_1": [0, 0, 0, 4] * 6})
    model = B.CrostonForecaster(alpha=0.1).fit(panel, target=S.DEMAND_LATENT)
    preds = model.predict(_future("1_1", pd.Timestamp("2024-01-25"), 3))
    assert preds.nunique() == 1  # Croston da una tasa constante
    assert 0.8 < preds.iloc[0] < 1.0


def test_croston_handles_an_all_zero_series() -> None:
    panel = _tiny_panel({"1_1": [0.0] * 20})
    model = B.CrostonForecaster().fit(panel, target=S.DEMAND_LATENT)
    preds = model.predict(_future("1_1", pd.Timestamp("2024-01-21"), 3))
    assert (preds == 0).all()


def test_baselines_do_not_mix_series() -> None:
    """Cada serie tiene que pronosticarse con su propia historia."""
    panel = _tiny_panel({"1_1": [1] * 10, "2_2": [100] * 10})
    model = B.NaiveForecaster().fit(panel, target=S.DEMAND_LATENT)
    origin = pd.Timestamp("2024-01-10")
    future = pd.concat([_future("1_1", origin, 2), _future("2_2", origin, 2)], ignore_index=True)
    preds = model.predict(future)
    assert preds.tolist() == [1.0, 1.0, 100.0, 100.0]


def test_prediction_order_is_preserved_when_series_interleave() -> None:
    """El agrupado interno no puede reordenar la salida respecto de `future`."""
    panel = _tiny_panel({"1_1": [1] * 10, "2_2": [100] * 10})
    model = B.NaiveForecaster().fit(panel, target=S.DEMAND_LATENT)
    origin = pd.Timestamp("2024-01-10")
    future = pd.DataFrame(
        {
            S.SERIES_ID: ["1_1", "2_2", "1_1", "2_2"],
            S.DATE: [origin + pd.Timedelta(days=d) for d in (1, 1, 2, 2)],
            "h": [1, 1, 2, 2],
        }
    )
    preds = model.predict(future)
    assert preds.tolist() == [1.0, 100.0, 1.0, 100.0]


def test_unseen_series_falls_back_instead_of_crashing() -> None:
    """Un producto nuevo (arranque en frio) no puede tirar un KeyError."""
    panel = _tiny_panel({"1_1": [4.0] * 10})
    model = B.NaiveForecaster().fit(panel, target=S.DEMAND_LATENT)
    preds = model.predict(_future("9_9", pd.Timestamp("2024-01-10"), 2))
    assert preds.notna().all()
    assert (preds >= 0).all()


# --- Contrato de Forecaster --------------------------------------------
def test_predict_before_fit_raises() -> None:
    model = B.NaiveForecaster()
    with pytest.raises(NotFittedError):
        model.predict(_future("1_1", pd.Timestamp("2024-01-01"), 1))


def test_fit_rejects_missing_target() -> None:
    panel = _tiny_panel({"1_1": [1.0] * 5})
    with pytest.raises(S.SchemaError, match="no esta en history"):
        B.NaiveForecaster().fit(panel, target="columna_inexistente")


def test_predictions_are_never_negative() -> None:
    """Una orden de reposicion negativa no existe. El recorte es del contrato."""

    class Negative(B.SeriesLevelForecaster):
        name = "negative"

        def _fit_series(self, y):
            return None

        def _predict_series(self, state, steps):
            return np.full(steps.shape[0], -5.0)

    panel = _tiny_panel({"1_1": [1.0] * 5})
    model = Negative().fit(panel, target=S.DEMAND_LATENT)
    preds = model.predict(_future("1_1", pd.Timestamp("2024-01-05"), 3))
    assert (preds == 0).all()


def test_wrong_prediction_length_is_caught() -> None:
    class Short(B.SeriesLevelForecaster):
        name = "short"

        def _fit_series(self, y):
            return None

        def _predict_series(self, state, steps):
            return np.zeros(1)  # devuelve menos de lo pedido

    panel = _tiny_panel({"1_1": [1.0] * 5})
    model = Short().fit(panel, target=S.DEMAND_LATENT)
    with pytest.raises(ValueError, match="valores para 3 pasos"):
        model.predict(_future("1_1", pd.Timestamp("2024-01-05"), 3))


def test_save_and_load_roundtrip(tmp_path, recovered_panel: pd.DataFrame) -> None:
    model = B.SeasonalNaiveForecaster().fit(recovered_panel, target=S.DEMAND_LATENT)
    path = model.save(tmp_path / "m.joblib")
    loaded = Forecaster.load(path)
    assert loaded.name == model.name
    assert loaded.last_train_date == model.last_train_date


def test_save_before_fit_raises(tmp_path) -> None:
    with pytest.raises(NotFittedError):
        B.NaiveForecaster().save(tmp_path / "m.joblib")


def test_all_registered_baselines_run(recovered_panel: pd.DataFrame) -> None:
    """Los cinco baselines de la metodologia tienen que correr sobre el panel."""
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]
    future = recovered_panel[recovered_panel[S.DATE] > origin][[S.SERIES_ID, S.DATE]].copy()
    future["h"] = (future[S.DATE] - origin).dt.days.astype("int16")

    assert len(B.BASELINE_REGISTRY) == 5
    for model in B.make_baselines():
        preds = model.fit(history, target=S.DEMAND_LATENT).predict(future)
        assert len(preds) == len(future)
        assert preds.notna().all(), f"{model.name} produjo nulos"
        assert (preds >= 0).all(), f"{model.name} produjo negativos"


# --- Modelos tabulares ------------------------------------------------
@pytest.mark.slow
def test_lightgbm_beats_the_seasonal_naive(recovered_panel: pd.DataFrame) -> None:
    """El modelo global tiene que superar al baseline en el panel sintetico.

    El panel tiene estacionalidad semanal inyectada, asi que si LightGBM no le
    gana al naive estacional teniendo esa senal disponible, el problema esta en
    el ensamblado de features, no en el modelo.
    """
    from dfcore import config as cfg
    from dfcore.evaluate import metrics as M
    from dfcore.evaluate.backtest import run_backtest
    from dfcore.models.gbdt import LightGBMForecaster

    forecast = cfg.ForecastConfig(
        horizon=7, season_length=7, n_origins=3, step=3, min_train_days=42
    )
    result = run_backtest(
        recovered_panel,
        [B.SeasonalNaiveForecaster(), LightGBMForecaster(n_estimators=200)],
        forecast=forecast,
    )
    summary = M.summarize(result)
    mase = summary[summary["metric"] == "mase"].set_index("model")["mean"]
    assert mase["lgbm_global"] < mase["seasonal_naive"], (
        f"LightGBM ({mase['lgbm_global']:.3f}) no le gano al naive estacional "
        f"({mase['seasonal_naive']:.3f})"
    )


@pytest.mark.slow
def test_quantile_model_produces_monotone_quantiles(recovered_panel: pd.DataFrame) -> None:
    """Los cuantiles no pueden cruzarse: un q90 debajo del q50 no es un intervalo."""
    from dfcore.models.gbdt import LightGBMQuantileForecaster

    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]
    future = recovered_panel[recovered_panel[S.DATE] > origin][[S.SERIES_ID, S.DATE]].copy()
    future["h"] = (future[S.DATE] - origin).dt.days.astype("int16")

    quantiles = (0.1, 0.5, 0.9)
    model = LightGBMQuantileForecaster(
        quantiles=quantiles, n_estimators=120, max_train_origins=6
    ).fit(history, target=S.DEMAND_LATENT)
    preds = model.predict_quantile(future, quantiles)

    cols = [quantile_col(q) for q in quantiles]
    arr = preds[cols].to_numpy()
    assert (np.diff(arr, axis=1) >= -1e-9).all(), "hay cuantiles cruzados"
    assert (arr >= 0).all()


@pytest.mark.slow
def test_reorder_quantity_uses_the_critical_fraction(recovered_panel: pd.DataFrame) -> None:
    """La cantidad a reponer tiene que salir del cuantil critico, no de la media.

    Con Cu = 1 y Co = 0,6 la fraccion critica es 0,625, asi que la orden tiene
    que quedar por encima de la mediana: en perecederos el sobre-stock duele,
    pero el quiebre duele mas.
    """
    from dfcore import config as cfg
    from dfcore.models.gbdt import LightGBMQuantileForecaster

    economics = cfg.EconomicsConfig(cu=1.0, co=0.6)
    assert economics.critical_fraction == pytest.approx(0.625)

    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]
    future = recovered_panel[recovered_panel[S.DATE] > origin][[S.SERIES_ID, S.DATE]].copy()
    future["h"] = (future[S.DATE] - origin).dt.days.astype("int16")

    model = LightGBMQuantileForecaster(
        quantiles=(0.5, 0.625, 0.9), n_estimators=120, max_train_origins=6
    ).fit(history, target=S.DEMAND_LATENT)
    qty = model.reorder_quantity(future, economics=economics)
    median = model.predict_quantile(future, [0.5])[quantile_col(0.5)]

    assert (qty >= 0).all()
    assert qty.mean() > median.mean(), (
        "la orden en q* = 0,625 quedo por debajo de la mediana; la asimetria de "
        "la perdida cuantilica no se esta aplicando"
    )
