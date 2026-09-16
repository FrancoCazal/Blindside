"""Simulador de politica de reposicion · seccion 8.4 del plan.

Compara la politica actual contra la del modelo sobre las ventanas del backtest y
produce el costo esperado de cada una. Es la base del ROI y lo que alimenta la
pantalla de reposicion del dashboard.

Que es cada politica
--------------------
``actual``
    Repone el **promedio movil reciente**, sin margen. Es lo que hace una planilla,
    y esta documentado que los decisores humanos ademas subestiman la demanda
    cuando las ventas perdidas no son observables (Tong, Feiler y Larrick 2018,
    https://journals.sagepub.com/doi/10.1111/poms.12823). O sea que la politica
    actual real es probablemente **peor** que esta simulacion, no mejor.
``modelo``
    Repone el cuantil `q*` de la demanda latente. La prediccion **es** la orden.
``estatica``
    Repone el cuantil `q*` de la distribucion de demanda **de cada serie**, con
    conocimiento perfecto de esa distribucion pero **sin** informacion del dia.
    Es la mejor politica de stock de seguridad fijo que existe: la que armaria
    alguien que conoce perfectamente cada producto pero no pronostica.
``perfecta``
    Repone exactamente la demanda que va a ocurrir. Costo cero. Es la cota
    superior trivial y sirve para normalizar.

Por que la descomposicion en esas cuatro
-----------------------------------------
Un "ahorro del 12 %" suelto no se puede interpretar. La comparacion contra la
politica estatica responde la pregunta que importa: **cuanto del ahorro viene de
pronosticar dia a dia y cuanto viene simplemente de fijar bien el nivel**. Si el
modelo apenas le gana a la estatica, la conclusion honesta es que el valor esta en
la economia del cuantil y no en el pronostico, y eso hay que decirlo.

Nota sobre un error facil de cometer: la politica estatica **no** es una cota
superior del modelo, aunque use informacion del futuro. Usa la distribucion de
cada serie pero no puede seguir la variacion diaria, asi que un buen pronostico le
gana sin contradiccion. La unica cota superior real es la politica perfecta.

Dos decisiones metodologicas que hay que declarar
-------------------------------------------------
**La evaluacion usa demanda latente, no venta observada.** Evaluar una politica
contra la venta observada la premiaria por pedir de menos: en un dia con quiebre
la venta ya esta truncada por la propia falta de stock, asi que una orden chica
parece suficiente. Es el efecto spiral-down metido en la evaluacion.

**El ahorro va en porcentaje.** `sale_amount` viene multiplicado por un
coeficiente no divulgado, asi que cualquier cifra monetaria derivada del dataset
primario seria un numero sin origen. Ver docs/roi.md.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from dfcore import config as cfg
from dfcore.data import schema as S
from dfcore.decision.newsvendor import PolicyOutcome, compare_policies, evaluate_policy

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

CURRENT_POLICY = "actual_promedio_movil"
MODEL_POLICY = "modelo_qstar"
STATIC_POLICY = "estatica_qstar_por_serie"
PERFECT_POLICY = "perfecta_sin_error"


def static_order(
    demand: np.ndarray | pd.Series,
    groups: np.ndarray | pd.Series,
    *,
    economics: cfg.EconomicsConfig = cfg.ECONOMICS,
) -> np.ndarray:
    """Cuantil `q*` de la distribucion de demanda de cada serie. Constante por serie.

    Es la **mejor politica de stock de seguridad fijo** que existe: usa conocimiento
    perfecto de la distribucion de cada producto pero ninguna informacion del dia.
    La comparacion contra ella separa el valor del pronostico del valor de la
    economia del cuantil.

    Usa el futuro para calcular el cuantil, asi que no es implementable tal cual.
    Y **no es una cota superior del modelo**: no puede seguir la variacion diaria,
    asi que un buen pronostico le gana sin que haya nada raro.
    """
    d = pd.Series(np.asarray(demand, dtype="float64").reshape(-1))
    g = pd.Series(np.asarray(groups).reshape(-1))
    q_star = economics.critical_fraction
    per_group = d.groupby(g).transform(lambda s: s.quantile(q_star))
    return per_group.to_numpy(dtype="float64")


def perfect_order(demand: np.ndarray | pd.Series) -> np.ndarray:
    """Repone exactamente la demanda. Costo cero. La cota superior trivial."""
    return np.asarray(demand, dtype="float64").reshape(-1).copy()


def simulate(
    result: pd.DataFrame,
    *,
    model_quantile_col: str,
    current_model: str,
    model_name: str,
    economics: cfg.EconomicsConfig = cfg.ECONOMICS,
) -> pd.DataFrame:
    """Compara las tres politicas sobre el resultado de backtest.

    `result` es el DataFrame del contrato de backtest, que ya trae la verdad de
    terreno y las predicciones de todos los modelos. `model_quantile_col` es la
    columna de cuantil `q*` del modelo — la orden.
    """
    from dfcore.evaluate import contracts as C

    current = result[result[C.MODEL] == current_model]
    model = result[result[C.MODEL] == model_name]
    for name, sub in ((current_model, current), (model_name, model)):
        if sub.empty:
            raise KeyError(f"el modelo '{name}' no esta en el resultado de backtest")
    if model_quantile_col not in model.columns:
        raise KeyError(
            f"'{model_quantile_col}' no esta en el resultado; correr el backtest con "
            "un modelo cuantilico y los cuantiles pedidos"
        )

    outcomes: list[PolicyOutcome] = [
        # Politica actual: pide el pronostico puntual, sin margen.
        evaluate_policy(
            current[C.Y_TRUE], current[C.Y_PRED], name=CURRENT_POLICY, economics=economics
        ),
        evaluate_policy(
            model[C.Y_TRUE],
            model[model_quantile_col],
            name=MODEL_POLICY,
            economics=economics,
        ),
        evaluate_policy(
            model[C.Y_TRUE],
            static_order(model[C.Y_TRUE], model[S.SERIES_ID], economics=economics),
            name=STATIC_POLICY,
            economics=economics,
        ),
        evaluate_policy(
            model[C.Y_TRUE],
            perfect_order(model[C.Y_TRUE]),
            name=PERFECT_POLICY,
            economics=economics,
        ),
    ]
    table = compare_policies(outcomes, reference=CURRENT_POLICY)

    saving = table.set_index("policy")["saving_pct"]
    achieved = float(saving.get(MODEL_POLICY, np.nan))
    static = float(saving.get(STATIC_POLICY, np.nan))
    # La politica perfecta tiene costo cero, asi que ahorra el 100 % respecto de
    # cualquier referencia con costo positivo. `captured_fraction` es entonces la
    # fraccion del costo actual que el modelo elimina, que es lo que un
    # responsable de compras entiende directo.
    table.attrs["captured_fraction"] = achieved / 100.0
    # Y esta es la lectura que de verdad informa: cuanto del ahorro viene de
    # pronosticar dia a dia en vez de solo fijar bien el nivel de cada producto.
    table.attrs["gain_over_static_pp"] = achieved - static
    log.info(
        "politica: el modelo ahorra %.2f %% del costo actual; la mejor politica "
        "estatica ahorra %.2f %%, asi que el pronostico diario aporta %.2f puntos",
        achieved,
        static,
        table.attrs["gain_over_static_pp"],
    )
    return table


def simulate_by_band(
    result: pd.DataFrame,
    bands: pd.Series,
    *,
    model_quantile_col: str,
    current_model: str,
    model_name: str,
    economics: cfg.EconomicsConfig = cfg.ECONOMICS,
) -> pd.DataFrame:
    """Lo mismo, desagregado por banda de rotacion.

    Es donde se espera que el modelo **no** gane: en intermitencia extrema esta
    publicado que los modelos complejos pierden en exactitud pura aunque puedan
    ganar en desempeno de inventario. Reportarlo desagregado es lo que vuelve
    creible el numero agregado.
    """
    from dfcore.evaluate import contracts as C

    df = result.copy()
    df["rotation_band"] = df[S.SERIES_ID].map(bands)
    frames = []
    for band, sub in df.groupby("rotation_band", observed=True):
        if sub[sub[C.MODEL] == model_name].empty:
            continue
        table = simulate(
            sub,
            model_quantile_col=model_quantile_col,
            current_model=current_model,
            model_name=model_name,
            economics=economics,
        )
        table["rotation_band"] = band
        frames.append(table)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def roi_relative(table: pd.DataFrame) -> dict[str, float]:
    """Indicadores relativos del ROI, sin convertir a moneda.

    Es la capa 1 de docs/roi.md: lo que se mide, sin supuestos. Los nombres
    coinciden con los indicadores que publica CADRE sobre este mismo dataset, para
    que la comparacion sea directa.
    """
    idx = table.set_index("policy")
    current = idx.loc[CURRENT_POLICY]
    model = idx.loc[MODEL_POLICY]
    return {
        "cost_saving_pct": float(model["saving_pct"]),
        "fill_rate_current": float(current["fill_rate"]),
        "fill_rate_model": float(model["fill_rate"]),
        "fill_rate_gain_pp": float(100 * (model["fill_rate"] - current["fill_rate"])),
        "service_level_current": float(current["cycle_service_level"]),
        "service_level_model": float(model["cycle_service_level"]),
        "spoilage_current": float(current["spoilage_rate"]),
        "spoilage_model": float(model["spoilage_rate"]),
        "spoilage_reduction_pp": float(100 * (current["spoilage_rate"] - model["spoilage_rate"])),
        "captured_fraction_of_current_cost": float(table.attrs.get("captured_fraction", np.nan)),
        # Cuanto del ahorro es atribuible al pronostico diario y no a fijar bien
        # el nivel. Es la cifra que separa "el modelo aporta" de "la economia
        # aporta y el modelo es incidental".
        "gain_over_best_static_pp": float(table.attrs.get("gain_over_static_pp", np.nan)),
    }


def roi_monetary(
    relative: dict[str, float],
    *,
    annual_revenue: float,
    gross_margin: float,
    base_spoilage_rate: float,
    capture_fraction: float,
) -> dict[str, float]:
    """Capa 2 de docs/roi.md: traduccion **parametrica** a moneda.

    Los cuatro argumentos son supuestos **declarados, no observados**, y estan asi
    en la firma para que no haya forma de calcular esto sin nombrarlos. No se
    atribuyen a ninguna empresa concreta: el dataset primario esta normalizado, y
    los guaranies del caso Focal Point salen del generador sintetico.

    `capture_fraction` es el supuesto mas fragil y el que domina la sensibilidad.
    Nunca es 1,0: entre la mejora del pronostico y la mejora realizada hay
    ejecucion, restricciones de proveedor y decisiones humanas.
    """
    if not 0 < capture_fraction <= 1:
        raise ValueError("capture_fraction tiene que estar en (0, 1]")

    spoilage_saving = annual_revenue * (relative["spoilage_reduction_pp"] / 100) * capture_fraction
    lost_sales_recovered = (
        annual_revenue * (relative["fill_rate_gain_pp"] / 100) * gross_margin * capture_fraction
    )
    return {
        "annual_revenue": annual_revenue,
        "gross_margin": gross_margin,
        "base_spoilage_rate": base_spoilage_rate,
        "capture_fraction": capture_fraction,
        "saving_from_spoilage": spoilage_saving,
        "saving_from_lost_sales": lost_sales_recovered,
        "total_annual_saving": spoilage_saving + lost_sales_recovered,
        "as_pct_of_revenue": 100 * (spoilage_saving + lost_sales_recovered) / annual_revenue,
    }


def sensitivity_grid(
    relative: dict[str, float],
    *,
    annual_revenue: float,
    gross_margin: float,
    base_spoilage_rate: float,
    capture_fractions: Sequence[float] = (0.3, 0.5, 0.7, 1.0),
) -> pd.DataFrame:
    """Rango de ROI barriendo la fraccion capturada.

    Un rango con supuestos visibles convence mas que un numero unico sin origen, y
    el caso de `capture_fraction = 0.3` es el pesimista que el plan pide reportar.
    """
    rows = []
    for frac in capture_fractions:
        row = roi_monetary(
            relative,
            annual_revenue=annual_revenue,
            gross_margin=gross_margin,
            base_spoilage_rate=base_spoilage_rate,
            capture_fraction=frac,
        )
        rows.append(row)
    out = pd.DataFrame(rows)
    out["scenario"] = [
        "pesimista" if f <= 0.3 else "base" if f <= 0.5 else "optimista" if f < 1 else "techo"
        for f in capture_fractions
    ]
    return out


__all__ = [
    "CURRENT_POLICY",
    "MODEL_POLICY",
    "PERFECT_POLICY",
    "STATIC_POLICY",
    "perfect_order",
    "roi_monetary",
    "roi_relative",
    "roi_relative",
    "sensitivity_grid",
    "simulate",
    "simulate_by_band",
    "static_order",
]
