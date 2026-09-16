"""Las metricas calculan lo que dicen calcular.

Se verifican contra valores computados a mano, no contra otra implementacion.
Comparar dos implementaciones propias solo demuestra que son consistentes entre
si, no que sean correctas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from blindside.evaluate import metrics as M


def test_mae_and_rmse_by_hand() -> None:
    y = np.array([1.0, 2.0, 3.0])
    p = np.array([1.0, 4.0, 3.0])
    assert M.mae(y, p) == pytest.approx(2 / 3)
    assert M.rmse(y, p) == pytest.approx(np.sqrt(4 / 3))


def test_bias_sign_is_prediction_minus_truth() -> None:
    """Un sesgo negativo tiene que significar "el modelo pide de menos"."""
    assert M.bias([10.0], [8.0]) == pytest.approx(-2.0)
    assert M.bias([10.0], [12.0]) == pytest.approx(2.0)


def test_mase_of_one_means_equal_to_scale() -> None:
    y = np.array([10.0, 10.0])
    p = np.array([12.0, 8.0])
    scale = np.array([2.0, 2.0])
    assert M.mase(y, p, scale) == pytest.approx(1.0)


def test_mase_below_one_means_beats_the_naive() -> None:
    y = np.array([10.0, 10.0])
    p = np.array([11.0, 9.0])
    assert M.mase(y, p, np.array([2.0, 2.0])) == pytest.approx(0.5)


def test_mase_rejects_zero_scale() -> None:
    """Una escala cero volveria MASE infinito; hay que fallar, no propagar inf."""
    with pytest.raises(ValueError, match="positiva"):
        M.mase([1.0], [2.0], [0.0])


def test_wape_survives_zeros_where_mape_would_explode() -> None:
    """El motivo de excluir MAPE, hecho test.

    Con demanda 0,1 y prediccion 0,3 MAPE aporta 200 % y domina el promedio.
    WAPE usa la suma en el denominador y se mantiene interpretable.
    """
    y = np.array([0.0, 0.1, 100.0])
    p = np.array([0.0, 0.3, 105.0])
    result = M.wape(y, p)
    assert 0 < result < 0.1  # el error real es chico respecto del volumen
    assert np.isfinite(result)


def test_wape_is_nan_when_there_is_no_volume() -> None:
    assert np.isnan(M.wape([0.0, 0.0], [1.0, 1.0]))


def test_pinball_is_asymmetric_in_the_right_direction() -> None:
    """Con q = 0,9 quedarse corto tiene que costar mucho mas que quedarse largo.

    Es la traduccion de la economia del newsvendor a funcion de perdida: si la
    asimetria estuviera invertida, el modelo aprenderia a pedir de menos.
    """
    truth = np.array([10.0])
    under = M.pinball_loss(truth, np.array([8.0]), q=0.9)  # se queda corto
    over = M.pinball_loss(truth, np.array([12.0]), q=0.9)  # se queda largo
    assert under > over
    assert under == pytest.approx(0.9 * 2)
    assert over == pytest.approx(0.1 * 2)


def test_pinball_at_median_is_half_mae() -> None:
    y = np.array([1.0, 2.0, 3.0])
    p = np.array([2.0, 2.0, 2.0])
    assert M.pinball_loss(y, p, q=0.5) == pytest.approx(M.mae(y, p) / 2)


def test_pinball_rejects_invalid_quantile() -> None:
    with pytest.raises(ValueError, match=r"\(0, 1\)"):
        M.pinball_loss([1.0], [1.0], q=1.0)


def test_empirical_coverage_counts_inclusion() -> None:
    y = np.array([1.0, 5.0, 10.0])
    lo = np.array([0.0, 0.0, 0.0])
    hi = np.array([2.0, 2.0, 20.0])
    assert M.empirical_coverage(y, lo, hi) == pytest.approx(2 / 3)


def test_interval_width_penalizes_the_trivial_wide_interval() -> None:
    """Cubrir el 100 % es trivial con un intervalo infinito; el ancho lo delata."""
    y = np.array([1.0, 2.0])
    narrow_lo, narrow_hi = np.array([0.5, 1.5]), np.array([1.5, 2.5])
    wide_lo, wide_hi = np.array([-100.0, -100.0]), np.array([100.0, 100.0])
    assert M.empirical_coverage(y, wide_lo, wide_hi) == 1.0
    assert M.mean_interval_width(wide_lo, wide_hi) > M.mean_interval_width(narrow_lo, narrow_hi)
    assert M.interval_score(y, wide_lo, wide_hi, alpha=0.1) > M.interval_score(
        y, narrow_lo, narrow_hi, alpha=0.1
    )


def test_quantile_calibration_detects_a_calibrated_model() -> None:
    """Con predicciones en los cuantiles verdaderos, el gap tiene que ser chico."""
    rng = np.random.default_rng(0)
    y = rng.normal(10, 2, size=20000)
    preds = {q: np.full(y.shape, 10 + 2 * _z(q)) for q in (0.1, 0.5, 0.9)}
    cal = M.quantile_calibration(y, preds)
    assert cal["gap"].abs().max() < 0.02


def _z(q: float) -> float:
    from statistics import NormalDist

    return NormalDist().inv_cdf(q)


def test_summarize_reports_dispersion(recovered_panel: pd.DataFrame, small_forecast_config) -> None:
    """El resumen tiene que traer desvio y peor origen, no solo la media.

    La metodologia prohibe el numero unico: un promedio bueno esconde un origen
    catastrofico, y el origen catastrofico es el que pasa en produccion.
    """
    from blindside.evaluate.backtest import run_backtest
    from blindside.models.baselines import NaiveForecaster, SeasonalNaiveForecaster

    result = run_backtest(
        recovered_panel,
        [NaiveForecaster(), SeasonalNaiveForecaster()],
        forecast=small_forecast_config,
    )
    summary = M.summarize(result)
    assert {"mean", "std", "worst_origin", "best_origin", "n_origins"} <= set(summary.columns)
    mase = summary[summary["metric"] == "mase"]
    assert len(mase) == 2
    assert (mase["n_origins"] == small_forecast_config.n_origins).all()
    assert (mase["worst_origin"] >= mase["mean"]).all()
    assert (mase["best_origin"] <= mase["mean"]).all()


def test_improvement_vs_baseline_computes_the_smart_objective(
    recovered_panel: pd.DataFrame, small_forecast_config
) -> None:
    """La tabla que responde "20 % menos MASE que el naive estacional"."""
    from blindside.evaluate.backtest import run_backtest
    from blindside.models.baselines import (
        REFERENCE_BASELINE,
        NaiveForecaster,
        SeasonalNaiveForecaster,
    )

    result = run_backtest(
        recovered_panel,
        [NaiveForecaster(), SeasonalNaiveForecaster()],
        forecast=small_forecast_config,
    )
    table = M.improvement_vs_baseline(
        M.summarize(result), baseline=REFERENCE_BASELINE, metric="mase"
    )
    ref = table[table["model"] == REFERENCE_BASELINE].iloc[0]
    assert ref["improvement_pct"] == pytest.approx(0.0)
    assert not ref["meets_target_20pct"]
    assert {"improvement_pct", "beats_baseline", "meets_target_20pct"} <= set(table.columns)


def test_improvement_vs_baseline_rejects_unknown_baseline() -> None:
    summary = pd.DataFrame(
        [
            {
                "model": "a",
                "metric": "mase",
                "mean": 1.0,
                "std": 0.0,
                "worst_origin": 1.0,
                "best_origin": 1.0,
                "n_origins": 1,
            }
        ]
    )
    with pytest.raises(KeyError, match="no esta en el resumen"):
        M.improvement_vs_baseline(summary, baseline="inexistente")


def test_mape_is_not_exported() -> None:
    """MAPE queda fuera a proposito. Si alguien lo agrega, este test lo recuerda."""
    assert not hasattr(M, "mape")
    assert "mape" not in M.__all__
    assert "mape" not in M.POINT_METRICS
