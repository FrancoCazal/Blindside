"""Los ocho items del checklist antifugas de la seccion 5.2, como tests.

Este archivo es la prueba de la afirmacion central del proyecto. Un README que
dice "evite leakage" no demuestra nada; un test que **falla si hay fuga** si. La
defensa muestra `pytest -m leakage` corriendo.

Cada test incluye ademas un caso negativo: se inyecta la fuga a proposito y se
verifica que el assert la detecte. Un test antifugas que pasa siempre, incluso con
fuga presente, es peor que no tener test, porque da confianza falsa.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dfcore import config as cfg
from dfcore.data import schema as S
from dfcore.evaluate import contracts as C
from dfcore.evaluate import metrics as M
from dfcore.evaluate.backtest import _future_index, run_backtest
from dfcore.features import build as fb
from dfcore.models.base import check_future_index
from dfcore.models.baselines import SeasonalNaiveForecaster
from dfcore.validation import leakage as lk
from dfcore.validation.splits import RollingOriginSplitter, naive_seasonal_scale

pytestmark = pytest.mark.leakage


def _lgbm_fit_predict(features: list[str]):
    """Fabrica un `fit_predict` de LightGBM para los tests de permutacion y corrimiento.

    Entrena directo sobre la matriz supervisada en vez de pasar por
    `LightGBMForecaster`, porque estos tests necesitan **manipular el target** del
    train, y el contrato del `Forecaster` recibe el panel y arma la matriz por su
    cuenta. Es la unica parte del proyecto que trabaja a ese nivel.
    """

    def fit_predict(tr: pd.DataFrame, te: pd.DataFrame) -> np.ndarray:
        import lightgbm as lgb

        from dfcore.models.gbdt import LightGBMForecaster
        from dfcore.models.tabular import prepare_categoricals

        params = {**LightGBMForecaster().params, "verbosity": -1}
        dtrain = lgb.Dataset(
            prepare_categoricals(tr[features], fb.CATEGORICAL_FEATURES),
            label=tr[fb.Y].to_numpy(dtype="float64"),
        )
        booster = lgb.train(params, dtrain, num_boost_round=120)
        return booster.predict(prepare_categoricals(te[features], fb.CATEGORICAL_FEATURES))

    return fit_predict


# --- 1 · ninguna feature posterior a t ----------------------------------
def test_no_future_columns(supervised_matrix: pd.DataFrame) -> None:
    lk.assert_no_future_columns(supervised_matrix)


def test_no_future_columns_detects_injected_leak(supervised_matrix: pd.DataFrame) -> None:
    """Caso negativo: una feature que depende del dia objetivo debe ser detectada.

    El nombre de la columna inyectada evita el sufijo `_target` a proposito: si lo
    tuviera, la filtraria el guardia estructural de `feature_columns` y este test
    no probaria el chequeo de variacion dentro del grupo, que es lo que quiere
    verificar. Dos barreras distintas, dos tests distintos.
    """
    leaky = supervised_matrix.copy()
    # El error clasico: rezago calculado respecto de la fecha objetivo. Para un
    # objetivo en T+7 esto vale y[T+6], seis dias dentro del futuro.
    leaky["lag1_desde_objetivo"] = leaky[fb.Y].shift(1).fillna(0.0)
    assert "lag1_desde_objetivo" in fb.feature_columns(leaky)
    with pytest.raises(lk.LeakageError, match="cambian dentro de un mismo"):
        lk.assert_no_future_columns(leaky)


def test_target_suffix_columns_are_never_features(supervised_matrix: pd.DataFrame) -> None:
    """Guardia estructural: nada que termine en `_target` entra a la matriz.

    Ese sufijo lo pone pandas al unir el estado del origen con la verdad del dia
    objetivo cuando hay choque de nombres, asi que una columna `algo_target` es
    por definicion del dia objetivo. Descartarlas por patron hace que agregar una
    columna nueva al panel no pueda abrir una fuga por olvido de declararla.
    """
    leaky = supervised_matrix.copy()
    leaky["is_censored_target"] = True
    leaky["cualquier_cosa_target"] = leaky[fb.Y]
    features = fb.feature_columns(leaky)
    assert not [c for c in features if c.endswith("_target")]


# --- 2 · lags por grupo y ordenados ------------------------------------
def test_lags_are_grouped(recovered_panel: pd.DataFrame) -> None:
    state = fb.add_origin_features(recovered_panel, target=S.DEMAND_LATENT)
    lk.assert_lags_are_grouped(state, target=S.DEMAND_LATENT, lag=1)


def test_lags_are_grouped_detects_ungrouped_shift(recovered_panel: pd.DataFrame) -> None:
    """Caso negativo: `shift` sin agrupar hace que una serie lea el final de otra."""
    broken = recovered_panel.sort_values([S.SERIES_ID, S.DATE]).copy()
    broken["latent_lag_1"] = broken[S.DEMAND_LATENT].shift(1)  # sin groupby
    with pytest.raises(lk.LeakageError, match="sin agrupar"):
        lk.assert_lags_are_grouped(broken, target=S.DEMAND_LATENT, lag=1)


# --- 3 · sin agregados globales ----------------------------------------
def test_no_global_aggregates(recovered_panel: pd.DataFrame) -> None:
    """Detecta el patron de pegar un promedio del panel completo como feature.

    Se reproduce la fuga tal como ocurre: la columna se calcula sobre todo el
    panel y queda presente en el panel y en el train, asi que la fila de train
    contiene el promedio de dias que todavia no pasaron.
    """
    full = recovered_panel.copy()
    full["mean_all_time"] = recovered_panel[S.DEMAND_LATENT].mean()
    split = full[S.DATE].quantile(0.7)
    train = full[full[S.DATE] <= split]

    with pytest.raises(lk.LeakageError, match="agregado global"):
        lk.assert_no_global_aggregates(train, full, columns=["mean_all_time"])


def test_no_global_aggregates_accepts_within_fold_features(
    recovered_panel: pd.DataFrame,
) -> None:
    """Un rolling calculado por fila no es un agregado global y debe pasar."""
    state = fb.add_origin_features(recovered_panel, target=S.DEMAND_LATENT)
    split = state[S.DATE].quantile(0.7)
    train = state[state[S.DATE] <= split]
    lk.assert_no_global_aggregates(train, state, columns=["latent_roll_mean_28"])


# --- 4 · sin target encoding del futuro --------------------------------
def test_no_target_leakage(supervised_matrix: pd.DataFrame) -> None:
    lk.assert_no_target_leakage(supervised_matrix)


def test_no_target_leakage_detects_copied_target(supervised_matrix: pd.DataFrame) -> None:
    leaky = supervised_matrix.copy()
    leaky["sneaky_encoding"] = leaky[fb.Y] * 1.0001
    with pytest.raises(lk.LeakageError, match="identicas al target"):
        lk.assert_no_target_leakage(leaky)


# --- 5 · el pipeline se ajusta solo con el train del fold --------------
def test_pipeline_fitted_on_train_only(recovered_panel: pd.DataFrame) -> None:
    """El escalador del Pipeline debe conocer la media del train, no la del panel.

    Es el item que separa M2 bien hecho de M2 mal hecho: escalar antes de partir
    contamina el escalador con el test y no se nota en ninguna metrica.
    """
    from dfcore.models.linear import RidgeForecaster

    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-15]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]

    model = RidgeForecaster(max_train_origins=4, origin_stride=3)
    model.fit(history, target=S.DEMAND_LATENT)

    state_train = fb.add_origin_features(history, target=S.DEMAND_LATENT)
    state_full = fb.add_origin_features(recovered_panel, target=S.DEMAND_LATENT)
    origins = pd.DatetimeIndex(sorted(state_train[S.DATE].unique()))[-14:-1:3]
    sup_train = fb.build_supervised(state_train, origins, horizon=7, target=S.DEMAND_LATENT)
    sup_full = fb.build_supervised(state_full, origins, horizon=7, target=S.DEMAND_LATENT)

    lk.assert_pipeline_fitted_on_train(
        model.pipeline, sup_train, sup_full, column="latent_roll_mean_28"
    )


# --- 6 · test de shuffle -----------------------------------------------
def test_shuffle_collapses_metric(recovered_panel: pd.DataFrame) -> None:
    """Al permutar el target, el error tiene que empeorar de forma clara.

    Si no empeora, la senal no venia de las features sino de una fuga. Es el test
    que se muestra en vivo.
    """

    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origins = dates[-24:-10:3]
    state = fb.add_origin_features(recovered_panel, target=S.DEMAND_LATENT)
    supervised = fb.build_supervised(state, origins, horizon=7, target=S.DEMAND_LATENT)

    split = supervised[fb.ORIGIN_DATE].quantile(0.7)
    train = supervised[supervised[fb.ORIGIN_DATE] <= split]
    test = supervised[supervised[fb.ORIGIN_DATE] > split]
    features = fb.feature_columns(supervised)

    result = lk.shuffle_test(_lgbm_fit_predict(features), train, test, metric=M.mae, seed=cfg.SEED)

    assert result.degraded_enough, (
        f"al permutar el target el error solo empeoro {result.ratio:.2f}x; "
        "con features honestas tiene que degradarse de forma clara"
    )
    assert result.no_better_than_constant, (
        f"el modelo con target permutado ({result.metric_shuffled:.4f}) le gana a "
        f"predecir la media del train ({result.metric_constant:.4f}); quedo senal "
        "despues de destruir la relacion con el target, o sea que viene de otro lado"
    )
    # El modelo honesto si tiene que superar al predictor constante: si no, no
    # hay nada que proteger de fugas.
    assert result.metric_real < result.metric_constant


# --- 7 · test de alineacion del target ---------------------------------
def test_shifting_the_target_makes_it_worse(recovered_panel: pd.DataFrame) -> None:
    """Correr el target un dia en cualquier direccion tiene que empeorar.

    Reemplaza al test ingenuo de "el error crece con el horizonte", que en esta
    serie no prueba nada: con estacionalidad semanal y `m = 7`, el objetivo en
    `T+7` cae el mismo dia de la semana que `T`, asi que se le parece **mas** que
    el de `T+1` y el error de `h = 7` puede ser legitimamente el mas bajo. Medir
    monotonia ahi mide el calendario, no la alineacion de indices.

    Este test ataca la alineacion de frente: si hubiera un corrimiento de un dia
    en el pipeline, desplazar el target lo compensaria y la metrica **mejoraria**.
    """

    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origins = dates[-30:-10:3]
    state = fb.add_origin_features(recovered_panel, target=S.DEMAND_LATENT)
    supervised = fb.build_supervised(state, origins, horizon=7, target=S.DEMAND_LATENT)

    split = supervised[fb.ORIGIN_DATE].quantile(0.7)
    train = supervised[supervised[fb.ORIGIN_DATE] <= split]
    test = supervised[supervised[fb.ORIGIN_DATE] > split]
    features = fb.feature_columns(supervised)

    result = lk.target_shift_test(_lgbm_fit_predict(features), train, test, metric=M.mae)
    assert (
        result.passed
    ), f"desplazar el target mejora la metrica, hay un corrimiento de indices: {result!r}"


def test_horizon_degradation_curve_is_reported(recovered_panel: pd.DataFrame) -> None:
    """La curva por horizonte se calcula y es lo que responde cuanto dura el modelo.

    Se verifica que exista y sea finita, no que sea monotona: la monotonia no se
    sostiene con estacionalidad semanal (ver el test de arriba).
    """
    forecast = cfg.ForecastConfig(
        horizon=7, season_length=7, n_origins=8, step=3, min_train_days=42
    )
    result = run_backtest(recovered_panel, [SeasonalNaiveForecaster()], forecast=forecast)
    by_h = M.metrics_by_horizon(result).set_index(C.HORIZON_STEP)["mase"]
    assert len(by_h) == 7
    assert np.isfinite(by_h.to_numpy()).all()


# --- 8 · test de fold --------------------------------------------------
def test_folds_are_disjoint(
    recovered_panel: pd.DataFrame, small_forecast_config: cfg.ForecastConfig
) -> None:
    splitter = RollingOriginSplitter(
        horizon=small_forecast_config.horizon,
        n_origins=small_forecast_config.n_origins,
        step=small_forecast_config.step,
        min_train_days=small_forecast_config.min_train_days,
    )
    folds = splitter.folds(recovered_panel)
    assert len(folds) == small_forecast_config.n_origins
    lk.assert_all_folds_disjoint(folds, recovered_panel)


def test_fold_detects_overlap(recovered_panel: pd.DataFrame) -> None:
    """Caso negativo: un fold cuyo test empieza antes del origen debe fallar."""
    from dfcore.validation.splits import Fold

    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    bad = Fold(index=0, origin=dates[-3], horizon=7)  # el test se sale del panel
    with pytest.raises(lk.LeakageError):
        lk.assert_fold_disjoint(bad, recovered_panel)


# --- Barreras estructurales del contrato --------------------------------
def test_future_index_carries_no_target(
    recovered_panel: pd.DataFrame, small_forecast_config: cfg.ForecastConfig
) -> None:
    """El indice de futuro no puede traer ninguna columna de verdad.

    Es la barrera estructural: si el modelo nunca recibe el target del futuro, no
    puede filtrarlo ni queriendo.
    """
    splitter = RollingOriginSplitter(
        horizon=small_forecast_config.horizon,
        n_origins=small_forecast_config.n_origins,
        step=small_forecast_config.step,
        min_train_days=small_forecast_config.min_train_days,
    )
    for fold in splitter.folds(recovered_panel):
        future = _future_index(recovered_panel, fold)
        check_future_index(future)  # no debe lanzar
        assert (future[S.DATE] > fold.origin).all()
        assert (future[S.DATE] <= fold.test_end).all()


def test_forecaster_rejects_prediction_inside_train(recovered_panel: pd.DataFrame) -> None:
    """Predecir una fecha que el modelo ya vio en train debe fallar, no pasar."""
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-10]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]
    model = SeasonalNaiveForecaster().fit(history, target=S.DEMAND_LATENT)

    bad_future = pd.DataFrame(
        {
            S.SERIES_ID: history[S.SERIES_ID].iloc[:3].to_numpy(),
            S.DATE: [origin, origin, origin],  # dentro del train
            "h": [1, 1, 1],
        }
    )
    with pytest.raises(S.SchemaError, match="caen en el train"):
        model.predict(bad_future)


def test_forecaster_rejects_forbidden_columns() -> None:
    future = pd.DataFrame(
        {
            S.SERIES_ID: ["1_1"],
            S.DATE: [pd.Timestamp("2024-06-01")],
            "h": [1],
            S.DEMAND_LATENT: [3.0],  # prohibido
        }
    )
    with pytest.raises(S.SchemaError, match="columnas prohibidas"):
        check_future_index(future)


def test_mase_scale_comes_from_train_only(recovered_panel: pd.DataFrame) -> None:
    """El denominador de MASE calculado con el train difiere del global.

    Si coincidieran, seria senal de que la escala se calculo con la serie
    completa. La verificacion es indirecta a proposito: no hay forma de detectar
    la contaminacion mirando solo el numero final, y eso es justamente el riesgo.
    """
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-15]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]

    from_train = naive_seasonal_scale(history, target=S.DEMAND_LATENT)
    from_full = naive_seasonal_scale(recovered_panel, target=S.DEMAND_LATENT)

    assert set(from_train.index) == set(from_full.index)
    assert (from_train > 0).all()
    differing = (
        ~np.isclose(from_train.to_numpy(), from_full.reindex(from_train.index).to_numpy())
    ).sum()
    assert differing > 0, (
        "la escala del train coincide exactamente con la del panel completo en "
        "todas las series; sospechoso"
    )


def test_backtest_result_rejects_prediction_before_origin() -> None:
    """`validate_result` debe rechazar una prediccion dentro de su propio train."""
    bad = pd.DataFrame(
        {
            C.MODEL: ["m"],
            C.ORIGIN: [0],
            C.ORIGIN_DATE: [pd.Timestamp("2024-06-10")],
            S.SERIES_ID: ["1_1"],
            S.DATE: [pd.Timestamp("2024-06-09")],  # antes del origen
            C.HORIZON_STEP: [-1],
            C.Y_TRUE: [1.0],
            C.Y_PRED: [1.0],
            C.Y_OBSERVED: [1.0],
            S.IS_CENSORED: [False],
            S.AVAILABLE_WEIGHT: [1.0],
            C.NAIVE_SCALE: [1.0],
        }
    )
    with pytest.raises(S.SchemaError, match="dentro de su propio train"):
        C.validate_result(bad)


def test_backtest_result_rejects_scale_varying_within_fold() -> None:
    """Una escala que varia dentro de (origen, serie) delata contaminacion."""
    base = {
        C.MODEL: "m",
        C.ORIGIN: 0,
        C.ORIGIN_DATE: pd.Timestamp("2024-06-01"),
        S.SERIES_ID: "1_1",
        C.Y_TRUE: 1.0,
        C.Y_PRED: 1.0,
        C.Y_OBSERVED: 1.0,
        S.IS_CENSORED: False,
        S.AVAILABLE_WEIGHT: 1.0,
    }
    bad = pd.DataFrame(
        [
            {**base, S.DATE: pd.Timestamp("2024-06-02"), C.HORIZON_STEP: 1, C.NAIVE_SCALE: 1.0},
            {**base, S.DATE: pd.Timestamp("2024-06-03"), C.HORIZON_STEP: 2, C.NAIVE_SCALE: 2.0},
        ]
    )
    with pytest.raises(S.SchemaError, match="varia dentro de"):
        C.validate_result(bad)
