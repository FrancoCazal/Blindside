"""Capa de decision: conformal y newsvendor.

Lo que se verifica no es que el codigo corra, sino que las **propiedades** que se
van a afirmar en la defensa se cumplan: que el intervalo cubra su nivel nominal,
que la orden salga del cuantil critico y no de la media, y que la politica del
modelo le gane economicamente a la politica actual.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from blindside import config as cfg
from blindside.data import schema as S
from blindside.decision import newsvendor as nv
from blindside.decision.conformal import ConformalForecaster
from blindside.evaluate import contracts as C
from blindside.evaluate import metrics as M
from blindside.evaluate.backtest import run_backtest
from blindside.models.base import quantile_col
from blindside.models.baselines import SeasonalNaiveForecaster


# --- Fraccion critica ---------------------------------------------------
def test_critical_fraction_by_hand() -> None:
    assert nv.critical_fraction(cu=1.0, co=1.0) == pytest.approx(0.5)
    assert nv.critical_fraction(cu=1.0, co=0.6) == pytest.approx(0.625)
    # Quedarse corto nueve veces mas caro que quedarse largo -> pedir el q90.
    assert nv.critical_fraction(cu=9.0, co=1.0) == pytest.approx(0.9)


def test_critical_fraction_rejects_non_positive_costs() -> None:
    with pytest.raises(ValueError, match="positivos"):
        nv.critical_fraction(cu=0.0, co=1.0)


def test_perishable_overage_cost_pushes_the_quantile_down() -> None:
    """Si el sobrante se tira, `Co` sube y `q*` baja. Es el efecto de la cadena de frio.

    En un producto seco el sobrante es capital inmovilizado y `Co` es chico, asi
    que conviene pedir mas. En perecederos el sobrante es perdida total, asi que
    el optimo se corre hacia abajo. La cadena de frio entra al proyecto por aca:
    como restriccion que deforma la economia, no como sistema a controlar.
    """
    dry_goods = nv.critical_fraction(cu=1.0, co=0.15)  # solo costo de capital
    perishable = nv.critical_fraction(cu=1.0, co=0.60)  # perdida total
    assert perishable < dry_goods
    # Aun asi el optimo queda por encima de la mediana: el quiebre duele mas.
    assert perishable > 0.5


# --- Costo esperado -----------------------------------------------------
def test_expected_cost_penalizes_both_directions() -> None:
    economics = cfg.EconomicsConfig(cu=1.0, co=0.6)
    demand = np.array([10.0, 10.0, 10.0])
    order = np.array([10.0, 8.0, 12.0])
    costs = nv.expected_cost(demand, order, economics=economics)
    assert costs[0] == pytest.approx(0.0)  # exacto
    assert costs[1] == pytest.approx(2.0)  # falta 2 -> Cu * 2
    assert costs[2] == pytest.approx(1.2)  # sobra 2 -> Co * 2


def test_the_optimal_constant_order_is_the_critical_quantile() -> None:
    """Verificacion del resultado teorico central del newsvendor.

    Se barre la orden sobre una demanda simulada y se comprueba que el minimo de
    costo cae en el cuantil `q*` de esa demanda. Si esto no se cumpliera, toda la
    capa de decision estaria apoyada en una formula equivocada, asi que vale la
    pena verificarlo en vez de confiar.
    """
    rng = np.random.default_rng(cfg.SEED)
    demand = rng.gamma(shape=3.0, scale=2.0, size=40000)
    economics = cfg.EconomicsConfig(cu=1.0, co=0.6)
    q_star = economics.critical_fraction

    candidates = np.quantile(demand, np.linspace(0.3, 0.9, 61))
    costs = [
        nv.expected_cost(demand, np.full(demand.shape, q), economics=economics).mean()
        for q in candidates
    ]
    best_order = candidates[int(np.argmin(costs))]
    theoretical = float(np.quantile(demand, q_star))

    assert best_order == pytest.approx(theoretical, rel=0.05), (
        f"el optimo empirico ({best_order:.3f}) no coincide con el cuantil q*={q_star} "
        f"({theoretical:.3f})"
    )


# --- Metricas de politica ----------------------------------------------
def test_policy_outcome_metrics_by_hand() -> None:
    economics = cfg.EconomicsConfig(cu=1.0, co=0.6)
    demand = np.array([10.0, 10.0, 10.0, 10.0])
    order = np.array([10.0, 10.0, 5.0, 20.0])
    out = nv.evaluate_policy(demand, order, name="p", economics=economics)

    assert out.n == 4
    assert out.expected_shortfall == pytest.approx(5 / 4)
    assert out.expected_overage == pytest.approx(10 / 4)
    # Dos dias de cuatro sin quiebre... en realidad tres: 10, 10 y 20 cubren.
    assert out.cycle_service_level == pytest.approx(3 / 4)
    assert out.fill_rate == pytest.approx(1 - 5 / 40)
    assert out.spoilage_rate == pytest.approx(10 / 45)


def test_fill_rate_and_cycle_service_level_differ() -> None:
    """Dos definiciones de nivel de servicio que dan numeros distintos.

    Confundirlas es comun y cambia la conclusion: una serie puede tener 50 % de
    dias sin quiebre y 95 % de unidades satisfechas si los quiebres son chicos.
    Se reportan las dos por eso.
    """
    demand = np.array([100.0, 1.0])
    order = np.array([100.0, 0.0])
    out = nv.evaluate_policy(demand, order, name="p")
    assert out.cycle_service_level == pytest.approx(0.5)
    assert out.fill_rate == pytest.approx(100 / 101)
    assert out.fill_rate > out.cycle_service_level


def test_compare_policies_expresses_saving_as_percentage() -> None:
    """El ahorro va en porcentaje, no en moneda: el dataset esta normalizado."""
    a = nv.evaluate_policy(np.array([10.0]), np.array([10.0]), name="modelo")
    b = nv.evaluate_policy(np.array([10.0]), np.array([5.0]), name="actual")
    table = nv.compare_policies([a, b], reference="actual")
    modelo = table[table["policy"] == "modelo"].iloc[0]
    assert modelo["saving_pct"] == pytest.approx(100.0)  # costo cero vs 5
    assert "cost_delta_pct" in table.columns


def test_compare_policies_rejects_unknown_reference() -> None:
    a = nv.evaluate_policy(np.array([1.0]), np.array([1.0]), name="a")
    with pytest.raises(KeyError, match="referencia"):
        nv.compare_policies([a], reference="no_existe")


def test_sensitivity_sweeps_the_only_parameter_that_matters() -> None:
    """`q*` depende solo del cociente `Co/Cu`, asi que se barre ese."""
    rng = np.random.default_rng(0)
    n = 500
    quantiles = (0.1, 0.5, 0.9)
    preds = pd.DataFrame(
        {
            quantile_col(0.1): np.full(n, 1.0),
            quantile_col(0.5): np.full(n, 2.0),
            quantile_col(0.9): np.full(n, 4.0),
        }
    )
    demand = rng.gamma(2.0, 1.0, size=n)
    table = nv.sensitivity_to_economics(demand, preds, quantiles=quantiles)

    assert len(table) == 4
    # Mas costo de sobrante -> q* menor -> orden menor. Monotono por definicion.
    assert table.sort_values("co_over_cu")["critical_fraction"].is_monotonic_decreasing
    assert table.sort_values("co_over_cu")["mean_order"].is_monotonic_decreasing


# --- Orden desde cuantiles ---------------------------------------------
def test_order_uses_the_exact_quantile_when_available() -> None:
    preds = pd.DataFrame({quantile_col(0.5): [1.0, 2.0], quantile_col(0.625): [1.5, 3.0]})
    order = nv.optimal_order_from_quantiles(
        preds, quantiles=(0.5, 0.625), economics=cfg.EconomicsConfig(cu=1.0, co=0.6)
    )
    assert order.tolist() == [1.5, 3.0]


def test_order_interpolates_when_the_quantile_is_missing() -> None:
    """Interpolar es aceptable y hay que decir que es una aproximacion."""
    preds = pd.DataFrame({quantile_col(0.5): [0.0], quantile_col(0.9): [4.0]})
    order = nv.optimal_order_from_quantiles(
        preds, quantiles=(0.5, 0.9), economics=cfg.EconomicsConfig(cu=1.0, co=0.6)
    )
    # q* = 0.625 esta a un tercio del camino entre 0.5 y 0.9.
    assert order.iloc[0] == pytest.approx(4.0 * (0.625 - 0.5) / 0.4)


def test_order_from_quantiles_requires_the_columns() -> None:
    with pytest.raises(KeyError, match="faltan columnas"):
        nv.optimal_order_from_quantiles(pd.DataFrame({"otra": [1.0]}), quantiles=(0.5,))


# --- Conformal ----------------------------------------------------------
def test_conformal_reaches_its_nominal_coverage(recovered_panel: pd.DataFrame) -> None:
    """La promesa central del conformal, medida y no afirmada.

    Un intervalo nominal del 90 % que en la practica cubre el 60 % hace que el
    sistema prometa un nivel de servicio que no cumple, y es una falla invisible
    hasta que el stock se agota.
    """
    forecast = cfg.ForecastConfig(
        horizon=7, season_length=7, n_origins=4, step=3, min_train_days=42, coverage=0.90
    )
    model = ConformalForecaster(
        SeasonalNaiveForecaster(), alpha=1 - forecast.coverage, horizon=forecast.horizon
    )
    result = _backtest_with_intervals(recovered_panel, model, forecast)

    coverage = M.empirical_coverage(result[C.Y_TRUE], result[C.PRED_LO], result[C.PRED_HI])
    assert coverage >= forecast.coverage - 0.05, (
        f"cobertura empirica {coverage:.1%} contra un nominal de " f"{forecast.coverage:.0%}"
    )
    # Y no puede cubrir por ser enorme: el ancho tiene que ser finito y acotado.
    width = M.mean_interval_width(result[C.PRED_LO], result[C.PRED_HI])
    assert 0 < width < 20 * result[C.Y_TRUE].mean()


def test_conformal_interval_widens_with_the_horizon(recovered_panel: pd.DataFrame) -> None:
    """Predecir a 7 dias es mas incierto que a 1, y el intervalo lo tiene que decir.

    Es la razon de calcular un cuantil de residuos **por paso de horizonte**. Con
    un cuantil unico el intervalo cubriria el 90 % en promedio y fallaria
    sistematicamente en los pasos lejanos, que son los que deciden la compra.
    """
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]

    model = ConformalForecaster(SeasonalNaiveForecaster(), alpha=0.1, horizon=7)
    model.fit(history, target=S.DEMAND_LATENT)

    widths = model.half_width_
    assert set(widths) == set(range(1, 8))
    assert widths[7] > widths[1], f"el intervalo no se ensancha con el horizonte: {widths}"


def test_conformal_lower_bound_is_never_negative(recovered_panel: pd.DataFrame) -> None:
    """La demanda no es negativa; un limite inferior negativo es ruido."""
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]
    future = _future_from(recovered_panel, origin)

    model = ConformalForecaster(SeasonalNaiveForecaster(), alpha=0.1, horizon=7)
    model.fit(history, target=S.DEMAND_LATENT)
    interval = model.predict_interval(future)

    assert (interval["pred_lo"] >= 0).all()
    assert (interval["pred_hi"] >= interval["pred_lo"]).all()


def test_adaptive_conformal_gives_volatile_series_wider_intervals(
    recovered_panel: pd.DataFrame,
) -> None:
    """La variante adaptativa ataca la limitacion real del conformal.

    El conformal garantiza cobertura **marginal**, no condicional: puede cubrir el
    90 % global y el 60 % en las series volatiles. Normalizar el residuo por la
    dispersion de cada serie reparte el ancho donde hace falta.
    """
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]
    future = _future_from(recovered_panel, origin)

    model = ConformalForecaster(SeasonalNaiveForecaster(), alpha=0.1, horizon=7, adaptive=True)
    model.fit(history, target=S.DEMAND_LATENT)
    interval = model.predict_interval(future)

    width = (
        (interval["pred_hi"] - interval["pred_lo"]).groupby(future[S.SERIES_ID].to_numpy()).mean()
    )
    assert model.dispersion_ is not None
    dispersion = model.dispersion_.reindex(width.index)

    # El ancho tiene que correlacionar con la dispersion de la serie.
    corr = np.corrcoef(width.to_numpy(), dispersion.to_numpy())[0, 1]
    assert corr > 0.8, f"el ancho adaptativo no sigue la dispersion (corr={corr:.2f})"


def test_conformal_calibration_split_is_temporal(recovered_panel: pd.DataFrame) -> None:
    """Calibrar con una particion aleatoria seria la misma fuga que todo el resto.

    Se verifica indirectamente: el modelo base final tiene que estar entrenado
    hasta el ultimo dia del train, no hasta el corte de calibracion.
    """
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]

    model = ConformalForecaster(SeasonalNaiveForecaster(), alpha=0.1, horizon=7)
    model.fit(history, target=S.DEMAND_LATENT)

    assert model.last_train_date == origin
    assert model.base.last_train_date == origin


def test_conformal_needs_enough_history_to_calibrate(recovered_panel: pd.DataFrame) -> None:
    cutoff = recovered_panel[S.DATE].min() + pd.Timedelta(days=10)
    short = recovered_panel[recovered_panel[S.DATE] <= cutoff]
    model = ConformalForecaster(SeasonalNaiveForecaster(), alpha=0.1, horizon=7)
    with pytest.raises(ValueError, match="dias de train para"):
        model.fit(short, target=S.DEMAND_LATENT)


def test_conformal_rejects_invalid_alpha() -> None:
    with pytest.raises(ValueError, match=r"\(0, 1\)"):
        ConformalForecaster(SeasonalNaiveForecaster(), alpha=1.5)


# --- Politica de punta a punta -----------------------------------------
def test_pinball_at_the_critical_fraction_is_the_newsvendor_cost() -> None:
    """Identidad exacta: pinball en `q*` **es** el costo del newsvendor, reescalado.

    Es el nucleo teorico de toda la capa de decision, y se puede verificar de
    forma cerrada. Con `q* = Cu / (Cu + Co)`:

        pinball_q*(d, p) = q* max(d-p, 0) + (1-q*) max(p-d, 0)
                         = [Cu max(d-p, 0) + Co max(p-d, 0)] / (Cu + Co)
                         = costo(d, p) / (Cu + Co)

    O sea que entrenar con perdida cuantilica en `q*` **es** minimizar el costo de
    reposicion, no una aproximacion conveniente. Es la forma concreta del
    resultado publicado de equivalencia entre cuantiles calibrados y newsvendor
    optimo (https://www.mdpi.com/1911-8074/19/3/173).
    """
    rng = np.random.default_rng(cfg.SEED)
    demand = rng.gamma(3.0, 2.0, size=5000)
    pred = rng.gamma(3.0, 2.0, size=5000)

    for cu, co in ((1.0, 0.6), (9.0, 1.0), (1.0, 3.0)):
        economics = cfg.EconomicsConfig(cu=cu, co=co)
        q_star = economics.critical_fraction
        cost = nv.expected_cost(demand, pred, economics=economics).mean()
        pinball = M.pinball_loss(demand, pred, q=q_star)
        assert pinball == pytest.approx(cost / (cu + co), rel=1e-9)


@pytest.mark.slow
def test_quantile_trained_model_beats_the_point_model_economically(
    recovered_panel: pd.DataFrame,
) -> None:
    """El resultado economico del proyecto, con el modelo que corresponde.

    Se compara el **mismo** LightGBM entrenado con dos perdidas: `regression_l1`,
    que estima la mediana y es el pronostico puntual de la planilla, contra
    perdida cuantilica en `q*`, que es la orden. La comparacion es limpia porque
    lo unico que cambia es la funcion de perdida.

    Tiene que ganar el cuantilico, y no por casualidad: por el test de arriba, la
    perdida cuantilica en `q*` **es** el costo de reposicion, asi que el modelo
    entrenado con ella esta optimizando directamente la metrica con la que se lo
    evalua.

    Nota de por que este test y no uno sobre el intervalo conformal: derivar
    cuantiles interpolando entre tres anclas de un intervalo conformal es un
    estimador pobre de la distribucion condicional, y ahi la orden en `q*` puede
    salir mas caro que el punto. El conformal entrega **un** intervalo a un nivel,
    no una distribucion; para cuantiles hay que entrenar cuantiles.
    """
    from blindside.models.gbdt import LightGBMForecaster, LightGBMQuantileForecaster

    economics = cfg.EconomicsConfig(cu=1.0, co=0.6)
    q_star = economics.critical_fraction

    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]
    future = _future_from(recovered_panel, origin)

    point = LightGBMForecaster(n_estimators=200, max_train_origins=10).fit(
        history, target=S.DEMAND_LATENT
    )
    quantile = LightGBMQuantileForecaster(
        quantiles=(q_star,), n_estimators=200, max_train_origins=10
    ).fit(history, target=S.DEMAND_LATENT)

    truth = (
        recovered_panel.set_index([S.SERIES_ID, S.DATE])[S.DEMAND_LATENT]
        .reindex(pd.MultiIndex.from_arrays([future[S.SERIES_ID], future[S.DATE]]))
        .to_numpy(dtype="float64")
    )

    order_point = point.predict(future).to_numpy()
    order_quantile = quantile.predict_quantile(future, [q_star])[quantile_col(q_star)].to_numpy()

    out_point = nv.evaluate_policy(truth, order_point, name="puntual_mediana", economics=economics)
    out_quantile = nv.evaluate_policy(
        truth, order_quantile, name="cuantilico_qstar", economics=economics
    )
    table = nv.compare_policies([out_point, out_quantile], reference="puntual_mediana")
    saving = float(table.loc[table["policy"] == "cuantilico_qstar", "saving_pct"].iloc[0])

    assert saving > 0, (
        f"el modelo cuantilico en q*={q_star:.3f} no ahorro nada ({saving:.2f} %) "
        "frente al puntual; con Cu != Co tendria que ganar por construccion"
    )
    # Y como q* > 0.5, la orden es mayor y el nivel de servicio sube.
    assert out_quantile.fill_rate > out_point.fill_rate


def test_conformal_policy_raises_the_service_level(recovered_panel: pd.DataFrame) -> None:
    """Pedir por encima de la mediana sube el nivel de servicio, mecanicamente.

    Se afirma solo eso y no el ahorro de costo, a proposito: los cuantiles
    derivados de un intervalo conformal por interpolacion son una aproximacion
    grosera de la distribucion condicional, y el ahorro depende de cuan buena sea
    esa aproximacion. El ahorro economico se verifica con el modelo cuantilico,
    que es el que corresponde.
    """
    forecast = cfg.ForecastConfig(
        horizon=7, season_length=7, n_origins=4, step=3, min_train_days=42
    )
    economics = cfg.EconomicsConfig(cu=1.0, co=0.6)
    model = ConformalForecaster(SeasonalNaiveForecaster(), alpha=0.1, horizon=forecast.horizon)
    result = _backtest_with_intervals(recovered_panel, model, forecast)

    quantiles = (0.5, economics.critical_fraction, 0.9)
    anchors = np.array([0.05, 0.5, 0.95])
    stacked = np.stack(
        [
            result[C.PRED_LO].to_numpy(),
            result[C.Y_PRED].to_numpy(),
            result[C.PRED_HI].to_numpy(),
        ],
        axis=1,
    )
    qframe = pd.DataFrame(
        {
            quantile_col(q): np.array([np.interp(q, anchors, row) for row in stacked])
            for q in quantiles
        },
        index=result.index,
    )
    order = nv.optimal_order_from_quantiles(qframe, quantiles=quantiles, economics=economics)

    out_q = nv.evaluate_policy(result[C.Y_TRUE], order, name="q*", economics=economics)
    out_point = nv.evaluate_policy(
        result[C.Y_TRUE], result[C.Y_PRED], name="puntual", economics=economics
    )
    assert out_q.fill_rate > out_point.fill_rate
    assert out_q.mean_order > out_point.mean_order


def test_reorder_table_is_sorted_by_impact() -> None:
    future = pd.DataFrame(
        {
            S.SERIES_ID: ["1_1", "1_2", "1_3"],
            S.DATE: [pd.Timestamp("2024-06-01")] * 3,
            "h": [1, 1, 1],
        }
    )
    order = pd.Series([1.0, 9.0, 5.0])
    table = nv.reorder_table(future, order)
    assert table["reorder_qty"].tolist() == [9.0, 5.0, 1.0]
    assert table["critical_fraction"].nunique() == 1


# --- Helpers ------------------------------------------------------------
def _future_from(panel: pd.DataFrame, origin: pd.Timestamp) -> pd.DataFrame:
    future = panel[panel[S.DATE] > origin][[S.SERIES_ID, S.DATE]].copy()
    future["h"] = (future[S.DATE] - origin).dt.days.astype("int16")
    return future[future["h"] <= 7].reset_index(drop=True)


def _backtest_with_intervals(
    panel: pd.DataFrame, model: ConformalForecaster, forecast: cfg.ForecastConfig
) -> pd.DataFrame:
    """Backtest de un modelo conformal, con sus limites de intervalo.

    Antes este helper reentrenaba el modelo fold por fold para pedirle
    `predict_interval`, porque el arnes general devolvia el contrato sin
    intervalos. Ya no: `run_fold` guarda `pred_lo` y `pred_hi` cuando el modelo
    los produce, asi que esto es una llamada directa y una pasada de
    entrenamiento menos. Se conserva el nombre para no tocar los tests que lo
    usan.
    """
    return run_backtest(panel, [model], forecast=forecast)


# --- Esperanza del newsvendor sobre la distribucion predictiva -----------
# Estos tests existen porque la alternativa era que el faltante y el sobrante los
# estimara la interfaz asumiendo la banda uniforme. Un supuesto de distribucion en
# la capa de presentacion no tiene forma de fallar en CI.


def _grilla_uniforme(alto: float = 10.0) -> tuple[pd.DataFrame, tuple[float, ...]]:
    """Uniforme(0, alto) descrita por 99 cuantiles.

    La grilla va de 0,01 a 0,99 y no mas fina porque `quantile_col` redondea a dos
    digitos: con mas niveles los nombres de columna colisionan y el test mediria
    una grilla distinta de la que cree.
    """
    niveles = tuple(round(k / 100, 2) for k in range(1, 100))
    fila = {quantile_col(q): alto * q for q in niveles}
    return pd.DataFrame([fila]), niveles


def test_esperanza_coincide_con_el_uniforme_analitico() -> None:
    """E[(D-q)+] = (alto-q)^2 / (2*alto) para la uniforme. Es el caso con cierre."""
    df, niveles = _grilla_uniforme(10.0)
    for orden in (2.0, 5.0, 8.0):
        r = nv.expected_cost_from_quantiles(
            df, quantiles=niveles, order=np.array([orden]), economics=cfg.EconomicsConfig(1.0, 1.0)
        )
        esperado = (10.0 - orden) ** 2 / 20.0
        # La tolerancia es el sesgo de las colas planas, que es conocido y esta
        # declarado en el docstring: la grilla no describe fuera de [0,01, 0,99].
        assert r["expected_shortfall"].iloc[0] == pytest.approx(esperado, abs=2e-3)
    assert r["expected_demand"].iloc[0] == pytest.approx(5.0, abs=1e-9)


def test_la_identidad_del_newsvendor_se_cumple_exacta() -> None:
    """(D-q)+ menos (q-D)+ es D-q, asi que en esperanza tambien.

    El sobrante se **deriva** de esa identidad en vez de integrarse aparte, para
    que los dos numeros no puedan contradecirse. Este test es lo que lo fija.
    """
    niveles = (0.05, 0.5, 0.625, 0.9, 0.95)
    df = pd.DataFrame(
        [dict(zip([quantile_col(q) for q in niveles], [0.2, 1.0, 1.3, 2.4, 3.1], strict=False))]
    )
    orden = np.array([1.3])
    r = nv.expected_cost_from_quantiles(df, quantiles=niveles, order=orden)
    izq = float(r["expected_shortfall"].iloc[0] - r["expected_overage"].iloc[0])
    der = float(r["expected_demand"].iloc[0] - orden[0])
    assert izq == pytest.approx(der, abs=1e-12)


def test_la_esperanza_coincide_con_monte_carlo() -> None:
    """Contra simulacion de la misma inversa lineal a tramos, que es la definicion."""
    niveles = (0.05, 0.5, 0.625, 0.9, 0.95)
    valores = [0.2, 1.0, 1.3, 2.4, 3.1]
    df = pd.DataFrame([dict(zip([quantile_col(q) for q in niveles], valores, strict=False))])
    orden = 1.3
    r = nv.expected_cost_from_quantiles(df, quantiles=niveles, order=np.array([orden]))

    u = np.concatenate(([0.0], niveles, [1.0]))
    y = np.array([valores[0], *valores, valores[-1]])
    muestra = np.interp(np.random.default_rng(0).uniform(size=400_000), u, y)
    assert r["expected_shortfall"].iloc[0] == pytest.approx(
        np.maximum(muestra - orden, 0).mean(), abs=5e-3
    )
    assert r["expected_overage"].iloc[0] == pytest.approx(
        np.maximum(orden - muestra, 0).mean(), abs=5e-3
    )


def test_pedir_mas_baja_el_faltante_y_sube_el_sobrante() -> None:
    """Monotonia. Si esto se rompe, el signo de la integral se dio vuelta."""
    df, niveles = _grilla_uniforme(10.0)
    df = pd.concat([df] * 3, ignore_index=True)
    r = nv.expected_cost_from_quantiles(df, quantiles=niveles, order=np.array([2.0, 5.0, 8.0]))
    assert r["expected_shortfall"].is_monotonic_decreasing
    assert r["expected_overage"].is_monotonic_increasing


def test_el_costo_esperado_es_minimo_en_q_estrella() -> None:
    """La razon de ser del cuantil critico, verificada sobre la propia integral.

    Es el test que conecta las dos mitades del proyecto: si el minimo del costo
    esperado no cayera en q*, la capa de decision estaria resolviendo otro problema
    que el que dice resolver.
    """
    df, niveles = _grilla_uniforme(10.0)
    eco = cfg.EconomicsConfig(cu=1.0, co=0.6)
    q_star = nv.critical_fraction(cu=1.0, co=0.6)

    candidatos = np.linspace(0.0, 10.0, 501)
    grilla = pd.concat([df] * len(candidatos), ignore_index=True)
    costos = nv.expected_cost_from_quantiles(
        grilla, quantiles=niveles, order=candidatos, economics=eco
    )["expected_cost"].to_numpy()

    # El optimo de la uniforme(0, 10) es 10 * q*.
    assert candidatos[int(np.argmin(costos))] == pytest.approx(10.0 * q_star, abs=0.05)


def test_los_cuantiles_cruzados_se_ordenan() -> None:
    """LightGBM entrena un booster por cuantil y nada los obliga a ser monotonos."""
    niveles = (0.05, 0.5, 0.95)
    # q05 por encima de q50: cruce inyectado a proposito.
    df = pd.DataFrame(
        [dict(zip([quantile_col(q) for q in niveles], [2.0, 1.0, 3.0], strict=False))]
    )
    r = nv.expected_cost_from_quantiles(df, quantiles=niveles, order=np.array([1.5]))
    assert r["expected_overage"].iloc[0] >= 0.0
    assert r["expected_shortfall"].iloc[0] >= 0.0


def test_la_masa_de_cola_no_descrita_se_declara() -> None:
    """Es lo que hace del faltante una cota inferior, asi que tiene que viajar."""
    niveles = (0.05, 0.5, 0.9)
    df = pd.DataFrame(
        [dict(zip([quantile_col(q) for q in niveles], [0.2, 1.0, 2.4], strict=False))]
    )
    r = nv.expected_cost_from_quantiles(df, quantiles=niveles, order=np.array([1.0]))
    assert r["tail_mass"].iloc[0] == pytest.approx(0.10)


# --- El conformal no puede descartar los cuantiles del modelo que envuelve ---


class _BaseCuantilico(SeasonalNaiveForecaster):
    """Base de prueba que dice tener cuantiles y devuelve valores reconocibles."""

    supports_quantiles = True
    quantiles = (0.05, 0.5, 0.625, 0.9, 0.95)

    def predict_quantile(self, future: pd.DataFrame, quantiles) -> pd.DataFrame:  # noqa: ANN001
        # Valores marcados: si el conformal los reemplaza por su banda, el test lo ve.
        return pd.DataFrame(
            {quantile_col(q): np.full(len(future), 100.0 + q) for q in sorted(quantiles)},
            index=future.index,
        )


def test_el_conformal_usa_los_cuantiles_del_base_y_no_su_banda(
    recovered_panel: pd.DataFrame,
) -> None:
    """Regresion de un desajuste train/serve que ninguna metrica detectaba.

    El artefacto servido es un conformal envolviendo un LightGBM cuantilico. Su
    `predict_quantile` interpolaba entre los limites del intervalo y **descartaba
    los boosters entrenados con perdida cuantilica**. Medido sobre 25 series, la
    orden salia 21,5 % mas alta que la del booster de q*, siempre hacia arriba
    porque la banda esta sobre-inflada. La interfaz mostraba ese numero como si
    fuera la salida del cuantil critico, que es lo que el README afirma.
    """
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]
    futuro = _future_from(recovered_panel, origin)

    modelo = ConformalForecaster(_BaseCuantilico(), alpha=0.1, horizon=7)
    modelo.fit(history, target=S.DEMAND_LATENT)

    salida = modelo.predict_quantile(futuro, (0.05, 0.5, 0.625, 0.9, 0.95))
    assert salida[quantile_col(0.625)].iloc[0] == pytest.approx(100.625)
    # Y la propiedad tiene que reportar los cuantiles del base, no los del config:
    # con el default de config la API interpolaba q* entre 0,5 y 0,9.
    assert modelo.quantiles == (0.05, 0.5, 0.625, 0.9, 0.95)


def test_el_conformal_sigue_interpolando_si_el_base_es_puntual(
    recovered_panel: pd.DataFrame,
) -> None:
    """El camino viejo no se elimina: para un base puntual es lo unico que hay."""
    dates = pd.DatetimeIndex(sorted(recovered_panel[S.DATE].unique()))
    origin = dates[-8]
    history = recovered_panel[recovered_panel[S.DATE] <= origin]
    futuro = _future_from(recovered_panel, origin)

    modelo = ConformalForecaster(SeasonalNaiveForecaster(), alpha=0.1, horizon=7)
    modelo.fit(history, target=S.DEMAND_LATENT)

    salida = modelo.predict_quantile(futuro, (0.05, 0.5, 0.95))
    intervalo = modelo.predict_interval(futuro)
    assert salida[quantile_col(0.5)].iloc[0] == pytest.approx(intervalo["y_pred"].iloc[0])
    assert salida[quantile_col(0.95)].iloc[0] == pytest.approx(intervalo["pred_hi"].iloc[0])
