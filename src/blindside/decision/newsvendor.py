"""Newsvendor · del pronostico a la orden de compra. Seccion 8.2 del plan.

El pronostico puntual no dice cuanto pedir. La economia si. Con `Cu` el costo de
quedarse corto — margen perdido — y `Co` el de quedarse largo, la cantidad optima
es el cuantil de la demanda en la **fraccion critica**:

    q* = Cu / (Cu + Co)

Lo que hace distinto el caso de perecederos, y es el motivo por el que la cadena
de frio entra en este proyecto: `Co` **no** es costo de capital inmovilizado, es
**perdida total al vencimiento**. Un pallet de yogur que no se vendio no queda en
inventario esperando la semana que viene, se tira. Eso sube `Co` respecto de un
producto seco y empuja `q*` hacia abajo — pero como `Cu` incluye el margen perdido
mas el costo de servicio, en la practica `q*` queda igual por encima de 0,5, y la
orden queda por encima de la mediana.

Encuadre honesto, y conviene tenerlo listo para la defensa
-----------------------------------------------------------
Esto **no es un aporte original**. Que los pronosticos cuantilicos calibrados sean
equivalentes a la solucion optima del newsvendor es un resultado publicado
(https://www.mdpi.com/1911-8074/19/3/173), y conformalizar el cuantil critico
tambien esta hecho (Cao, dic-2024, https://arxiv.org/abs/2412.13159). Lo que se
reivindica es la **aplicacion**: la implementacion corriendo de punta a punta, que
es lo raro, porque la mayoria de las implementaciones reales usan un stock de
seguridad heuristico en vez de un cuantil con cobertura verificada.

Limitaciones declaradas, que estan en el README
------------------------------------------------
El modelo es de **un solo periodo**. Para perecederos con vida util mayor al
periodo de revision, el modelo correcto es de inventario perecedero multiperiodo
con despacho por antiguedad. La aproximacion vale cuando la vida util se parece al
periodo de revision, que es el caso de fresco diario. No se modela lead time, ni
multiechelon, ni restricciones de cantidad minima o multiplos de caja: la salida
es un numero continuo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)


def critical_fraction(*, cu: float, co: float) -> float:
    """q* = Cu / (Cu + Co). El cuantil que hay que pronosticar."""
    if cu <= 0 or co <= 0:
        raise ValueError(f"Cu y Co deben ser positivos, llegaron cu={cu}, co={co}")
    return cu / (cu + co)


def expected_cost(
    demand: np.ndarray | pd.Series,
    order: np.ndarray | pd.Series,
    *,
    economics: cfg.EconomicsConfig = cfg.ECONOMICS,
) -> np.ndarray:
    """Costo de cada decision, elemento por elemento.

        costo = Cu * max(demanda - orden, 0) + Co * max(orden - demanda, 0)

    El primer termino es venta perdida, el segundo merma. Se calcula
    **empiricamente** sobre las ventanas del backtest y no con la formula cerrada
    del newsvendor, porque la formula cerrada exige conocer la distribucion de la
    demanda y aca lo que hay son realizaciones. Es una diferencia que el panel
    puede preguntar: el numero sale de contar, no de suponer una normal.
    """
    d = np.asarray(demand, dtype="float64").reshape(-1)
    q = np.asarray(order, dtype="float64").reshape(-1)
    shortfall = np.maximum(d - q, 0.0)
    overage = np.maximum(q - d, 0.0)
    return economics.cu * shortfall + economics.co * overage


@dataclass(frozen=True)
class PolicyOutcome:
    """Resultado de una politica de reposicion sobre las ventanas del backtest."""

    name: str
    total_cost: float
    mean_cost: float
    expected_shortfall: float
    expected_overage: float
    #: Fraccion de la demanda efectivamente satisfecha. Es el nivel de servicio
    #: como lo entiende la operacion, ponderado por unidades y no por dias.
    fill_rate: float
    #: Fraccion de dias sin quiebre. Es la otra definicion de nivel de servicio,
    #: y da un numero distinto; se reportan las dos porque confundirlas es comun.
    cycle_service_level: float
    #: Fraccion de lo pedido que no se vendio. En perecederos es merma real.
    spoilage_rate: float
    mean_order: float
    n: int

    def as_dict(self) -> dict[str, float | str | int]:
        return {
            "policy": self.name,
            "total_cost": self.total_cost,
            "mean_cost": self.mean_cost,
            "expected_shortfall": self.expected_shortfall,
            "expected_overage": self.expected_overage,
            "fill_rate": self.fill_rate,
            "cycle_service_level": self.cycle_service_level,
            "spoilage_rate": self.spoilage_rate,
            "mean_order": self.mean_order,
            "n": self.n,
        }


def evaluate_policy(
    demand: np.ndarray | pd.Series,
    order: np.ndarray | pd.Series,
    *,
    name: str,
    economics: cfg.EconomicsConfig = cfg.ECONOMICS,
) -> PolicyOutcome:
    """Metricas economicas y de servicio de una politica.

    La demanda que se pasa tiene que ser la **latente recuperada**, no la venta
    observada. Evaluar una politica contra la venta observada la premiaria por
    pedir de menos: en un dia con quiebre la venta observada ya esta truncada por
    la propia falta de stock, asi que una orden chica pareceria suficiente. Es el
    efecto spiral-down metido en la evaluacion.
    """
    d = np.asarray(demand, dtype="float64").reshape(-1)
    q = np.asarray(order, dtype="float64").reshape(-1)
    if d.shape != q.shape:
        raise ValueError(f"demanda {d.shape} y orden {q.shape} no coinciden")

    shortfall = np.maximum(d - q, 0.0)
    overage = np.maximum(q - d, 0.0)
    costs = economics.cu * shortfall + economics.co * overage

    total_demand = d.sum()
    total_order = q.sum()
    return PolicyOutcome(
        name=name,
        total_cost=float(costs.sum()),
        mean_cost=float(costs.mean()),
        expected_shortfall=float(shortfall.mean()),
        expected_overage=float(overage.mean()),
        fill_rate=float(1 - shortfall.sum() / total_demand) if total_demand > 0 else float("nan"),
        cycle_service_level=float(np.mean(shortfall <= 1e-9)),
        spoilage_rate=float(overage.sum() / total_order) if total_order > 0 else 0.0,
        mean_order=float(q.mean()),
        n=int(d.size),
    )


def optimal_order_from_quantiles(
    quantile_preds: pd.DataFrame,
    *,
    quantiles: Sequence[float],
    economics: cfg.EconomicsConfig = cfg.ECONOMICS,
) -> pd.Series:
    """Interpola la orden en `q*` a partir de cuantiles ya predichos.

    Si `q*` esta entre los cuantiles entrenados se devuelve directo. Si no, se
    interpola linealmente. Un `q*` entrenado directamente es mejor que uno
    interpolado — la perdida cuantilica optimiza ese cuantil y no otro — asi que
    conviene incluir `q*` en `FORECAST.quantiles` cuando la economia esta fijada.
    """
    from blindside.models.base import quantile_col

    q_star = economics.critical_fraction
    ordered = sorted(quantiles)
    cols = [quantile_col(q) for q in ordered]
    missing = [c for c in cols if c not in quantile_preds.columns]
    if missing:
        raise KeyError(f"faltan columnas de cuantil {missing}")

    if q_star in ordered:
        return quantile_preds[quantile_col(q_star)].rename("reorder_qty")

    arr = quantile_preds[cols].to_numpy(dtype="float64")
    interpolated = np.array([np.interp(q_star, ordered, row) for row in arr])
    return pd.Series(
        np.clip(interpolated, 0.0, None), index=quantile_preds.index, name="reorder_qty"
    )


def _inverse_cdf_grid(
    quantile_preds: pd.DataFrame, *, quantiles: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    """Grilla `(u, y)` de la inversa de la CDF, ordenada y sin cruces.

    Los cuantiles predichos pueden salir cruzados — LightGBM entrena un booster
    por cuantil y nada los obliga a ser monotonos — asi que se ordenan por fila.
    Ordenar es la correccion estandar de quantile crossing y no cambia la
    cobertura marginal de cada nivel.
    """
    from blindside.models.base import quantile_col

    ordered = sorted(quantiles)
    cols = [quantile_col(q) for q in ordered]
    missing = [c for c in cols if c not in quantile_preds.columns]
    if missing:
        raise KeyError(f"faltan columnas de cuantil {missing}")

    y = quantile_preds[cols].to_numpy(dtype="float64")
    y = np.sort(np.clip(y, 0.0, None), axis=1)
    return np.asarray(ordered, dtype="float64"), y


def expected_cost_from_quantiles(
    quantile_preds: pd.DataFrame,
    *,
    quantiles: Sequence[float],
    order: np.ndarray | pd.Series,
    economics: cfg.EconomicsConfig = cfg.ECONOMICS,
) -> pd.DataFrame:
    """Faltante, sobrante y costo **esperados** bajo la distribucion del modelo.

    Por que esto no es lo mismo que `evaluate_policy`
    -------------------------------------------------
    `evaluate_policy` cuenta sobre realizaciones: necesita saber que demanda
    hubo. Sirve para el backtest y es lo que el README defiende, porque ahi el
    numero sale de contar y no de suponer.

    En produccion no hay realizacion: el horizonte todavia no paso. Lo que si hay
    es la distribucion predictiva que el propio modelo emite como grilla de
    cuantiles, y la esperanza del newsvendor sobre ella esta definida:

        E[(D - q)+] = integral_0^1 max(F^-1(u) - q, 0) du

    Se calcula tratando `F^-1` como lineal a tramos entre los niveles predichos.
    Es **esperanza implicada por el modelo**, no resultado medido, y hereda la
    calibracion de esos cuantiles: si el intervalo esta inflado, el sobrante
    esperado sale inflado con el. Por eso se reporta al lado de la cobertura
    empirica y no solo.

    La alternativa era devolver cero, que es lo que hacia antes, y dejar que la
    interfaz estimara el impacto asumiendo la banda uniforme. Eso ponia un
    supuesto de distribucion en la capa de presentacion, que es el peor lugar
    para tenerlo: invisible y sin test.

    El sesgo conocido, declarado
    ----------------------------
    La grilla termina en el cuantil mas alto entrenado (0,95), asi que la masa de
    arriba — el 5 % donde vive la demanda extrema — no esta descrita. La cola se
    trata como **plana** en el ultimo valor, y eso hace que el faltante esperado
    sea una **cota inferior**. Extrapolar la cola habria inventado una forma que
    nadie estimo; se prefiere un numero que se sabe corto a uno que se cree
    exacto. La masa no modelada se devuelve en la columna `tail_mass`.
    """
    levels, y = _inverse_cdf_grid(quantile_preds, quantiles=quantiles)
    q = np.asarray(order, dtype="float64").reshape(-1)
    if q.shape[0] != y.shape[0]:
        raise ValueError(f"la orden tiene {q.shape[0]} filas y los cuantiles {y.shape[0]}")

    # Grilla aumentada con las dos colas planas: u de 0 a 1 con los valores
    # extremos repetidos. Plana por arriba es lo que hace la cota inferior.
    u = np.concatenate(([0.0], levels, [1.0]))
    yy = np.concatenate((y[:, :1], y, y[:, -1:]), axis=1)

    mean = _integrate_piecewise(u, yy)
    shortfall = _integrate_excess(u, yy, q)
    # Identidad del newsvendor: (y-q)+ - (q-y)+ = y - q. Derivar el sobrante de
    # ella en vez de integrarlo aparte garantiza que los dos numeros sean
    # consistentes entre si, y el test lo verifica.
    overage = shortfall - mean + q

    cost = economics.cu * shortfall + economics.co * np.maximum(overage, 0.0)
    return pd.DataFrame(
        {
            "expected_demand": mean,
            "expected_shortfall": shortfall,
            "expected_overage": np.maximum(overage, 0.0),
            "expected_cost": cost,
            "tail_mass": np.full(q.shape[0], 1.0 - float(levels[-1])),
        },
        index=quantile_preds.index,
    )


def _integrate_piecewise(u: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Integral de `F^-1` en `u` de 0 a 1, exacta para lineal a tramos."""
    du = np.diff(u)
    mid = (y[:, :-1] + y[:, 1:]) / 2.0
    return mid @ du


def _integrate_excess(u: np.ndarray, y: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Integral de `max(F^-1(u) - q, 0)`, partiendo el tramo en el cruce.

    Integrar por trapecio sin partir el tramo donde `F^-1` cruza `q` sobreestima
    el faltante, porque el trapecio no ve el codo. El error es chico pero es
    sistematico y siempre en la misma direccion, asi que se parte.
    """
    ya, yb = y[:, :-1], y[:, 1:]
    du = np.diff(u)[None, :]
    qq = q[:, None]
    ea, eb = ya - qq, yb - qq

    both_above = (ea >= 0) & (eb >= 0)
    both_below = (ea <= 0) & (eb <= 0)

    # Tramo entero por encima: trapecio comun.
    area = np.where(both_above, (ea + eb) / 2.0 * du, 0.0)

    # Tramo que cruza: triangulo desde el cruce hasta el extremo que quedo arriba.
    # La fraccion del tramo por encima es el excedente positivo sobre el salto
    # total, y la altura media del triangulo es la mitad de ese excedente.
    crossing = ~both_above & ~both_below
    if crossing.any():
        jump = eb - ea
        with np.errstate(divide="ignore", invalid="ignore"):
            frac_up = np.where(jump != 0, np.maximum(ea, eb) / jump, 0.0)
        frac_up = np.abs(np.clip(frac_up, -1.0, 1.0))
        tri = frac_up * du * np.maximum(ea, eb) / 2.0
        area = np.where(crossing, tri, area)

    return area.sum(axis=1)


def compare_policies(outcomes: Sequence[PolicyOutcome], *, reference: str) -> pd.DataFrame:
    """Tabla comparativa con el ahorro **en porcentaje**, no en moneda.

    El porcentaje no es timidez: en el dataset primario `sale_amount` viene
    multiplicado por un coeficiente no divulgado, asi que cualquier cifra
    monetaria derivada de ahi seria un numero sin origen. Los guaranies salen del
    caso Focal Point, con supuestos declarados. Ver docs/roi.md.
    """
    table = pd.DataFrame([o.as_dict() for o in outcomes])
    ref = table.loc[table["policy"] == reference, "total_cost"]
    if ref.empty:
        raise KeyError(f"la politica de referencia '{reference}' no esta en la tabla")
    ref_cost = float(ref.iloc[0])
    table["cost_delta_pct"] = 100 * (table["total_cost"] / ref_cost - 1)
    table["saving_pct"] = -table["cost_delta_pct"]
    return table.sort_values("total_cost", ignore_index=True)


def sensitivity_to_economics(
    demand: np.ndarray | pd.Series,
    quantile_preds: pd.DataFrame,
    *,
    quantiles: Sequence[float],
    co_over_cu: Sequence[float] = (0.3, 0.6, 1.0, 1.5),
    cu: float = 1.0,
) -> pd.DataFrame:
    """Como cambia la decision al mover la economia.

    Es el analisis de sensibilidad que el plan pide para el ROI (seccion 11). El
    cociente `Co/Cu` es el unico parametro que importa — `q*` depende solo de el —
    asi que se barre ese y no las dos magnitudes por separado. Un rango con
    supuestos visibles convence mas que un numero unico sin origen.
    """
    rows = []
    for ratio in co_over_cu:
        economics = cfg.EconomicsConfig(cu=cu, co=cu * ratio)
        order = optimal_order_from_quantiles(
            quantile_preds, quantiles=quantiles, economics=economics
        )
        outcome = evaluate_policy(demand, order, name=f"co/cu={ratio:.2f}", economics=economics)
        row = outcome.as_dict()
        row["co_over_cu"] = ratio
        row["critical_fraction"] = economics.critical_fraction
        rows.append(row)
    return pd.DataFrame(rows)


def newsvendor_report(
    result: pd.DataFrame,
    *,
    quantiles: Sequence[float],
    economics: cfg.EconomicsConfig = cfg.ECONOMICS,
    model_policy: str,
    current_policy: str,
) -> pd.DataFrame:
    """Compara la politica del modelo contra la actual sobre el backtest.

    `current_policy` es el nombre del modelo que representa lo que la operacion
    hace hoy — `moving_average`, promedio de las ultimas tres semanas. Es la
    referencia economica del ROI, y no un baseline mas.

    La politica actual pide **el pronostico puntual**, sin margen: es lo que hace
    una planilla. La del modelo pide el cuantil `q*`. La diferencia de costo entre
    las dos es el ahorro atribuible a decidir con la economia en vez de con el
    promedio.
    """
    from blindside.evaluate import contracts as C

    outcomes = []
    for name, sub in (
        (current_policy, result[result[C.MODEL] == current_policy]),
        (model_policy, result[result[C.MODEL] == model_policy]),
    ):
        if sub.empty:
            raise KeyError(f"el modelo '{name}' no esta en el resultado de backtest")
        demand = sub[C.Y_TRUE]
        if name == model_policy:
            order = optimal_order_from_quantiles(sub, quantiles=quantiles, economics=economics)
        else:
            # Sin margen de seguridad, a proposito: es lo que hace la planilla.
            order = sub[C.Y_PRED]
        outcomes.append(evaluate_policy(demand, order, name=name, economics=economics))
    return compare_policies(outcomes, reference=current_policy)


def reorder_table(
    future: pd.DataFrame,
    order: pd.Series,
    *,
    economics: cfg.EconomicsConfig = cfg.ECONOMICS,
) -> pd.DataFrame:
    """Tabla de reposicion sugerida, ordenada por impacto. Alimenta el dashboard.

    El impacto se expresa en **unidades**, no en moneda, por la normalizacion del
    dataset. Ordenar por cantidad y no alfabeticamente es lo que hace la tabla
    accionable: el responsable de compras mira las primeras veinte lineas.
    """
    keep = (S.SERIES_ID, S.DATE, "h", S.STORE_ID, S.PRODUCT_ID)
    out = future[[c for c in keep if c in future.columns]].copy()
    out["reorder_qty"] = order.to_numpy()
    out["critical_fraction"] = economics.critical_fraction
    return out.sort_values("reorder_qty", ascending=False, ignore_index=True)


__all__ = [
    "PolicyOutcome",
    "compare_policies",
    "critical_fraction",
    "evaluate_policy",
    "expected_cost",
    "newsvendor_report",
    "optimal_order_from_quantiles",
    "reorder_table",
    "sensitivity_to_economics",
]
