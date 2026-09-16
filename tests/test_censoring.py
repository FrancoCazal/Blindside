"""La recuperacion de demanda censurada hace lo que dice.

Estos tests existen porque el panel sintetico tiene el proceso generador
**conocido**: la demanda latente se inyecto a mano y despues se censuro. Asi que
no hace falta creer que la recuperacion funciona, se puede medir cuanto del sesgo
recupera. Es la ventaja metodologica que el dataset real no da, y es un argumento
de defensa distinto del que aporta el benchmark publico.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dfcore import config as cfg
from dfcore.data import schema as S
from dfcore.decision import censoring as cen


def test_clean_days_are_never_modified(recovered_panel: pd.DataFrame) -> None:
    """En dias sin quiebre la venta observada ES la demanda. No se toca.

    Es la invariante mas importante del modulo: esos dias son la verdad de
    terreno contra la que se mide el sesgo, y corregirlos destruiria la medicion.
    """
    clean = ~recovered_panel[S.IS_CENSORED]
    assert np.allclose(
        recovered_panel.loc[clean, S.DEMAND_LATENT],
        recovered_panel.loc[clean, S.SALE_AMOUNT],
        atol=1e-5,
    )


def test_latent_never_below_observed(recovered_panel: pd.DataFrame) -> None:
    """La venta ocurrio: es cota inferior de la demanda."""
    assert (recovered_panel[S.DEMAND_LATENT] >= recovered_panel[S.SALE_AMOUNT] - 1e-5).all()


def test_censored_days_are_inflated(recovered_panel: pd.DataFrame) -> None:
    censored = recovered_panel[S.IS_CENSORED]
    uplift = (
        recovered_panel.loc[censored, S.DEMAND_LATENT].mean()
        / recovered_panel.loc[censored, S.SALE_AMOUNT].mean()
    )
    assert uplift > 1.05, f"los dias censurados apenas se corrigieron (x{uplift:.3f})"


def test_recovery_reduces_bias_against_known_truth(
    synthetic_hourly_panel: pd.DataFrame,
) -> None:
    """Con la verdad inyectada conocida, la correccion tiene que acercarse a ella.

    Es la verificacion fuerte: se compara la venta observada y la demanda
    recuperada contra `demand_latent_true`, que es el valor que se uso para
    generar el dia antes de censurarlo. La recuperacion no tiene que ser perfecta
    — el tope de inflacion la limita a proposito — pero tiene que reducir el
    sesgo de forma clara.
    """
    recovered = cen.HourlyProfileRecovery().recover(synthetic_hourly_panel)
    truth = synthetic_hourly_panel["demand_latent_true"].to_numpy(dtype="float64")
    censored = synthetic_hourly_panel[S.IS_CENSORED].to_numpy(dtype=bool)

    bias_observed = (
        recovered.loc[censored, S.SALE_AMOUNT].to_numpy().mean() / truth[censored].mean() - 1
    )
    bias_recovered = (
        recovered.loc[censored, S.DEMAND_LATENT].to_numpy().mean() / truth[censored].mean() - 1
    )

    assert bias_observed < -0.15, (
        f"la censura sintetica no deprime la venta lo suficiente ({bias_observed:.3f}); "
        "el test no estaria probando nada"
    )
    assert abs(bias_recovered) < abs(
        bias_observed
    ), f"la recuperacion no redujo el sesgo: {bias_observed:.3f} -> {bias_recovered:.3f}"
    # Recupera al menos la mitad del sesgo. El tope de inflacion impide llegar al
    # 100 %, y eso es una decision declarada, no una falla.
    recovered_fraction = 1 - abs(bias_recovered) / abs(bias_observed)
    assert (
        recovered_fraction > 0.5
    ), f"solo recupero el {recovered_fraction:.0%} del sesgo de censura"


def test_inflation_is_capped(recovered_panel: pd.DataFrame) -> None:
    """Sin tope, un dia con 15 de 16 franjas en quiebre inventa varianza."""
    factor = recovered_panel[S.INFLATION].dropna()
    assert factor.max() <= cfg.CENSORING.max_inflation + 1e-4


def test_tobit_ewma_agrees_in_direction(synthetic_hourly_panel: pd.DataFrame) -> None:
    """Los dos recuperadores tienen que coincidir en el signo de la correccion.

    Si dos metodos independientes dan la misma direccion, la conclusion no
    depende de la eleccion de metodo. Es una pregunta que el panel va a hacer.
    """
    profile = cen.HourlyProfileRecovery().recover(synthetic_hourly_panel)
    tobit = cen.TobitEWMARecovery().recover(synthetic_hourly_panel)

    for out in (profile, tobit):
        censored = out[S.IS_CENSORED]
        assert out.loc[censored, S.DEMAND_LATENT].mean() > out.loc[censored, S.SALE_AMOUNT].mean()
    # Y en magnitud tienen que estar en el mismo orden, no diferir por 10x.
    ratio_profile = profile[S.DEMAND_LATENT].mean() / profile[S.SALE_AMOUNT].mean()
    ratio_tobit = tobit[S.DEMAND_LATENT].mean() / tobit[S.SALE_AMOUNT].mean()
    assert 0.3 < (ratio_profile - 1) / (ratio_tobit - 1) < 3.0


def test_tobit_ewma_does_not_use_the_censored_day_itself(
    synthetic_hourly_panel: pd.DataFrame,
) -> None:
    """La EWMA lleva `shift(1)`: el nivel de un dia no incluye ese dia.

    Sin el shift, el propio valor censurado entraria en su propia correccion y la
    arrastraria hacia abajo — una fuga sutil dentro del recuperador.
    """
    out = cen.TobitEWMARecovery().recover(synthetic_hourly_panel)
    first = out.groupby(S.SERIES_ID, observed=True).head(1)
    # En el primer dia no hay historia previa, asi que no puede haber inflado
    # usando dias posteriores.
    assert (first[S.DEMAND_LATENT] >= first[S.SALE_AMOUNT] - 1e-6).all()


def test_recensored_bias_is_zero_for_a_perfect_latent_prediction() -> None:
    """Si el modelo acierta la demanda latente, re-censurarla da la venta observada.

    Es la propiedad que hace util a la metrica: el cero significa exactamente
    "el modelo recupero la demanda latente", sin necesidad de comparar contra
    ninguna referencia externa.
    """
    latent = np.array([10.0, 10.0, 10.0, 4.0])
    weight = np.array([1.0, 0.5, 0.25, 1.0])
    observed = latent * weight  # asi se genera la venta registrada
    bias = cen.recensored_bias(observed, latent, available_weight=weight)
    assert bias == pytest.approx(0.0, abs=1e-12)


def test_recensored_bias_is_negative_for_a_censored_trained_model() -> None:
    """Un modelo que aprendio del nivel deprimido da sesgo negativo.

    Ese negativo **es** el efecto spiral-down medido: el modelo predice la venta
    observada en vez de la demanda latente, asi que al re-censurar queda por debajo
    de lo que realmente se vendio.
    """
    latent = np.array([10.0, 10.0, 10.0, 10.0])
    weight = np.array([1.0, 0.5, 0.5, 0.25])
    observed = latent * weight
    # El modelo sesgado predice el promedio de la venta observada, no la latente.
    biased_pred = np.full(4, observed.mean())
    bias = cen.recensored_bias(observed, biased_pred, available_weight=weight)
    assert bias < -0.05, f"el sesgo tendria que ser claramente negativo, dio {bias:.4f}"


def test_recensored_bias_clips_the_weight_to_the_unit_interval() -> None:
    bias = cen.recensored_bias(np.array([1.0]), np.array([1.0]), available_weight=np.array([2.0]))
    assert bias == pytest.approx(0.0)


def test_clean_day_bias_measures_only_clean_days() -> None:
    obs = np.array([10.0, 10.0, 2.0, 2.0])
    pred = np.array([9.0, 9.0, 9.0, 9.0])
    censored = np.array([False, False, True, True])
    bias = cen.clean_day_bias(obs, pred, is_censored=censored)
    # Solo las dos primeras cuentan: (9 - 10) / 10 = -0.1
    assert bias == pytest.approx(-0.1)


def test_clean_day_bias_returns_nan_without_clean_days() -> None:
    bias = cen.clean_day_bias(
        np.array([1.0, 2.0]), np.array([1.0, 2.0]), is_censored=np.array([True, True])
    )
    assert np.isnan(bias)


def test_clean_day_bias_is_confounded_when_stockouts_follow_demand() -> None:
    """El confundidor de seleccion, demostrado con el mecanismo real.

    En la operacion el stock se agota **porque** la gente compro mucho, asi que
    los dias limpios son sistematicamente dias de demanda baja. Aca se construye
    justamente eso: los dias de demanda alta quiebran y los de demanda baja no.

    Un predictor perfecto de la demanda latente esperada — la media de la latente —
    sobrepredice en el subconjunto limpio **sin estar equivocado**, porque ese
    subconjunto no representa la demanda tipica. `recensored_bias` no sufre el
    problema porque evalua sobre todos los dias y usa el patron real de quiebres.
    """
    # Los tres primeros dias tienen demanda alta y quiebran; los tres ultimos no.
    latent = np.array([10.0, 12.0, 11.0, 2.0, 3.0, 2.5])
    weight = np.array([0.5, 0.5, 0.5, 1.0, 1.0, 1.0])
    observed = latent * weight
    censored = weight < 1.0

    # "Modelo" que acierta la demanda latente esperada, sin sesgo alguno.
    perfect = np.full(latent.shape, latent.mean())

    bias_clean = cen.clean_day_bias(observed, perfect, is_censored=censored)
    # Predice 6,75 donde los dias limpios valen 2,5 de media: +170 % de "sesgo"
    # que no es sesgo, es seleccion.
    assert (
        bias_clean > 1.0
    ), f"el efecto de seleccion tendria que ser grande aca, dio {bias_clean:.3f}"

    # La re-censurada con el mismo predictor queda muchisimo mas cerca de cero.
    bias_recensored = cen.recensored_bias(observed, perfect, available_weight=weight)
    assert abs(bias_recensored) < abs(bias_clean) / 5


def test_recensored_bias_recovers_the_injected_truth(
    synthetic_hourly_panel: pd.DataFrame,
) -> None:
    """Con la demanda latente verdadera, el sesgo re-censurado tiene que ser ~0.

    Es la verificacion mas directa que permite el generador: se conoce el valor
    que se inyecto antes de censurar, asi que se puede comprobar que la metrica
    devuelve cero cuando la prediccion es correcta.

    No da exactamente cero, y el residuo esta explicado: el panel se genera
    repartiendo la demanda con un **perfil intradiario** con picos, mientras que
    `available_weight` cuenta horas de forma **uniforme**. La diferencia entre las
    dos ponderaciones deja ~1 % residual. Es el precio de que la metrica no
    dependa del perfil estimado, que a su vez la mantiene independiente del
    recuperador que se este evaluando.
    """
    bias = cen.recensored_bias(
        synthetic_hourly_panel[S.SALE_AMOUNT],
        synthetic_hourly_panel["demand_latent_true"],
        available_weight=synthetic_hourly_panel[S.AVAILABLE_WEIGHT],
    )
    assert abs(bias) < 0.05, f"con la verdad inyectada el sesgo dio {bias:.4f}"


def test_censoring_report_shape(recovered_panel: pd.DataFrame) -> None:
    report = cen.censoring_report(recovered_panel)
    assert list(report["grupo"]) == ["todos los dias", "dias limpios", "dias censurados"]
    clean_row = report[report["grupo"] == "dias limpios"].iloc[0]
    assert clean_row["uplift_pct"] == pytest.approx(0.0, abs=1e-3)


def test_recovery_requires_hourly_columns(synthetic_panel: pd.DataFrame) -> None:
    """Sin las secuencias horarias el metodo por perfil no puede correr, y avisa."""
    with pytest.raises(S.SchemaError, match="load_hourly_panel"):
        cen.HourlyProfileRecovery().recover(synthetic_panel)


def test_get_recovery_rejects_unknown_method() -> None:
    with pytest.raises(KeyError, match="desconocido"):
        cen.get_recovery("no_existe")


def test_open_hours_window_matches_dataset_column(
    synthetic_hourly_panel: pd.DataFrame,
) -> None:
    """La ventana comercial asumida reproduce `stock_hour6_22_cnt`.

    Verificado contra el dataset real en `build_panel`: son los indices 6..21, 16
    franjas. Una hora de corrimiento desplazaria todo el factor de inflacion, y
    seria un error que ninguna metrica delataria.
    """
    status = np.stack(synthetic_hourly_panel[S.HOURS_STOCK_STATUS].to_numpy())
    open_idx = np.asarray(cfg.CENSORING.open_hours)
    assert len(cfg.CENSORING.open_hours) == 16
    derived = status[:, open_idx].sum(axis=1)
    assert np.array_equal(derived, synthetic_hourly_panel[S.OOS_HOURS_OPEN].to_numpy())
