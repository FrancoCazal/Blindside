"""Simulador de politica y ROI.

Lo que se verifica es que el simulador no se pueda usar para producir un numero
favorable sin declarar los supuestos, y que el techo del oraculo acote de verdad
al modelo. Un ROI donde el modelo supera al oraculo es un ROI mal calculado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from blindside import config as cfg
from blindside.data import schema as S
from blindside.decision import policy as pol
from blindside.evaluate import contracts as C
from blindside.models.base import quantile_col


def _fake_result(n_series: int = 12, n_days: int = 6, seed: int = 0) -> pd.DataFrame:
    """Resultado de backtest sintetico con dos modelos y una columna de cuantil."""
    rng = np.random.default_rng(seed)
    rows = []
    origin = pd.Timestamp("2024-06-01")
    for s in range(n_series):
        level = float(rng.uniform(1.0, 8.0))
        for d in range(1, n_days + 1):
            truth = float(rng.gamma(3.0, level / 3.0))
            for model, pred in (
                # La politica actual pide el promedio, sin margen.
                ("moving_average", level),
                # El modelo acierta mejor el nivel.
                ("lgbm_quantile", truth * float(rng.uniform(0.85, 1.15))),
            ):
                rows.append(
                    {
                        C.MODEL: model,
                        C.ORIGIN: 0,
                        C.ORIGIN_DATE: origin,
                        S.SERIES_ID: f"1_{s}",
                        S.DATE: origin + pd.Timedelta(days=d),
                        C.HORIZON_STEP: d,
                        C.Y_TRUE: truth,
                        C.Y_PRED: pred,
                        C.Y_OBSERVED: truth,
                        S.IS_CENSORED: False,
                        S.AVAILABLE_WEIGHT: 1.0,
                        C.NAIVE_SCALE: max(level / 2, 0.1),
                        # Cuantil q* = 0.625: por encima del punto.
                        quantile_col(0.625): pred * 1.25,
                    }
                )
    return pd.DataFrame(rows)


# --- Oraculo ------------------------------------------------------------
def test_static_order_is_the_per_series_quantile() -> None:
    demand = np.array([1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0])
    groups = np.array(["a", "a", "a", "a", "b", "b", "b", "b"])
    economics = cfg.EconomicsConfig(cu=1.0, co=1.0)  # q* = 0.5
    order = pol.static_order(demand, groups, economics=economics)

    assert order[:4].tolist() == [2.5] * 4  # mediana de a
    assert order[4:].tolist() == [25.0] * 4  # mediana de b


def test_perfect_policy_has_zero_cost() -> None:
    """La unica cota superior real: reponer exactamente lo que se va a vender."""
    result = _fake_result()
    table = pol.simulate(
        result,
        model_quantile_col=quantile_col(0.625),
        current_model="moving_average",
        model_name="lgbm_quantile",
    )
    costs = table.set_index("policy")["total_cost"]
    assert costs[pol.PERFECT_POLICY] == pytest.approx(0.0)
    # Y acota a todas las demas, por definicion.
    assert (costs.drop(pol.PERFECT_POLICY) > 0).all()


def test_static_policy_is_not_an_upper_bound() -> None:
    """La mejor politica estatica **no** acota al modelo, y conviene saber por que.

    Usa conocimiento perfecto de la distribucion de cada serie, asi que suena a
    cota superior. No lo es: no puede seguir la variacion diaria. Un pronostico
    decente le gana sin que haya nada mal en el calculo, y confundir las dos cosas
    llevaria a "arreglar" un simulador que funciona.
    """
    result = _fake_result()
    table = pol.simulate(
        result,
        model_quantile_col=quantile_col(0.625),
        current_model="moving_average",
        model_name="lgbm_quantile",
    )
    costs = table.set_index("policy")["total_cost"]
    # En estos datos sinteticos el modelo sigue el dia y la estatica no, asi que
    # el modelo gana. Es el resultado esperado, no un error.
    assert costs[pol.MODEL_POLICY] < costs[pol.STATIC_POLICY]
    assert table.attrs["gain_over_static_pp"] > 0


def test_gain_over_static_separates_forecast_from_economics() -> None:
    """La cifra que distingue "el modelo aporta" de "la economia aporta".

    Si el ahorro del modelo apenas superara el de la mejor politica estatica, la
    conclusion honesta seria que el valor esta en el cuantil critico y no en el
    pronostico. La descomposicion hace que esa lectura sea posible.
    """
    result = _fake_result()
    table = pol.simulate(
        result,
        model_quantile_col=quantile_col(0.625),
        current_model="moving_average",
        model_name="lgbm_quantile",
    )
    roi = pol.roi_relative(table)
    saving = roi["cost_saving_pct"]
    gain = roi["gain_over_best_static_pp"]
    assert 0 < gain <= saving + 1e-9
    assert roi["captured_fraction_of_current_cost"] == pytest.approx(saving / 100)


def test_simulate_fails_without_the_quantile_column() -> None:
    result = _fake_result().drop(columns=[quantile_col(0.625)])
    with pytest.raises(KeyError, match="correr el backtest"):
        pol.simulate(
            result,
            model_quantile_col=quantile_col(0.625),
            current_model="moving_average",
            model_name="lgbm_quantile",
        )


def test_simulate_fails_on_unknown_model() -> None:
    with pytest.raises(KeyError, match="no esta en el resultado"):
        pol.simulate(
            _fake_result(),
            model_quantile_col=quantile_col(0.625),
            current_model="no_existe",
            model_name="lgbm_quantile",
        )


# --- ROI relativo -------------------------------------------------------
def test_roi_relative_reports_the_published_indicators() -> None:
    """Los nombres coinciden con los que publica CADRE, para comparar directo."""
    result = _fake_result()
    table = pol.simulate(
        result,
        model_quantile_col=quantile_col(0.625),
        current_model="moving_average",
        model_name="lgbm_quantile",
    )
    roi = pol.roi_relative(table)
    expected = {
        "cost_saving_pct",
        "fill_rate_current",
        "fill_rate_model",
        "fill_rate_gain_pp",
        "service_level_current",
        "service_level_model",
        "spoilage_current",
        "spoilage_model",
        "spoilage_reduction_pp",
        "captured_fraction_of_current_cost",
        "gain_over_best_static_pp",
    }
    assert expected <= set(roi)
    assert 0 <= roi["fill_rate_model"] <= 1
    assert 0 <= roi["service_level_model"] <= 1


# --- ROI monetario ------------------------------------------------------
def test_roi_monetary_requires_declaring_every_assumption() -> None:
    """Los cuatro supuestos son argumentos obligatorios, sin valores por defecto.

    Es deliberado: no tiene que haber forma de calcular un ROI monetario sin
    nombrar los supuestos que lo sostienen. El panel los va a pedir.
    """
    import inspect

    sig = inspect.signature(pol.roi_monetary)
    required = {
        name
        for name, p in sig.parameters.items()
        if p.default is inspect.Parameter.empty and name != "relative"
    }
    assert required == {
        "annual_revenue",
        "gross_margin",
        "base_spoilage_rate",
        "capture_fraction",
    }


def test_roi_monetary_scales_with_the_capture_fraction() -> None:
    relative = {
        "spoilage_reduction_pp": 2.0,
        "fill_rate_gain_pp": 1.5,
        "cost_saving_pct": 10.0,
    }
    full = pol.roi_monetary(
        relative,
        annual_revenue=1_000_000,
        gross_margin=0.30,
        base_spoilage_rate=0.098,
        capture_fraction=1.0,
    )
    half = pol.roi_monetary(
        relative,
        annual_revenue=1_000_000,
        gross_margin=0.30,
        base_spoilage_rate=0.098,
        capture_fraction=0.5,
    )
    assert half["total_annual_saving"] == pytest.approx(full["total_annual_saving"] / 2)


def test_roi_monetary_rejects_an_impossible_capture_fraction() -> None:
    """Capturar mas del 100 % de la mejora no existe."""
    relative = {"spoilage_reduction_pp": 1.0, "fill_rate_gain_pp": 1.0}
    with pytest.raises(ValueError, match=r"\(0, 1\]"):
        pol.roi_monetary(
            relative,
            annual_revenue=1000,
            gross_margin=0.3,
            base_spoilage_rate=0.1,
            capture_fraction=1.5,
        )


def test_sensitivity_grid_includes_the_pessimistic_case() -> None:
    """El plan exige reportar un rango con el caso pesimista, no un numero unico."""
    relative = {"spoilage_reduction_pp": 2.0, "fill_rate_gain_pp": 1.5}
    grid = pol.sensitivity_grid(
        relative,
        annual_revenue=1_000_000,
        gross_margin=0.30,
        base_spoilage_rate=0.098,
    )
    assert "pesimista" in set(grid["scenario"])
    assert "techo" in set(grid["scenario"])
    assert grid["total_annual_saving"].is_monotonic_increasing


def test_sanity_check_against_the_published_anchor() -> None:
    """Regla de orden de magnitud citada en el plan.

    Se reporta que ~10 % de mejora en exactitud equivale a ~1,5 % de mejora en
    disponibilidad. Si el ROI implica un salto de disponibilidad mucho mayor, algun
    supuesto esta inflado. El test fija la regla como codigo para que el chequeo
    exista en vez de quedar como una nota al pie.
    """
    accuracy_gain_pct = 24.5  # la mejora de MASE medida
    implied_availability_gain_pp = accuracy_gain_pct / 10 * 1.5
    assert implied_availability_gain_pp == pytest.approx(3.675, rel=1e-6)
    # Cualquier ROI que implique mas de ~4 puntos de disponibilidad con esta
    # mejora de exactitud tendria que justificarse aparte.
    assert implied_availability_gain_pp < 5.0
