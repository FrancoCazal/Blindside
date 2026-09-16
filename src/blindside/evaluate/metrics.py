"""Metricas de exactitud, de cuantiles y de calibracion de intervalos.

MAPE **no esta y no va a estar**. Explota con demanda cercana a cero, que es
exactamente la cola de baja rotacion, o sea la mayoria del catalogo en
perecederos. Un solo dia con venta 0,1 y prediccion 0,3 aporta 200 % de error y
domina el promedio de la serie entera. La decision es deliberada y se justifica
en la defensa (docs/decisiones.md D5).

Lo que si esta:

======================  ===================================================
MASE                    Principal. Libre de escala. < 1 significa "le gana
                        al metodo que la operacion ya usa".
WAPE                    Lectura de negocio, ponderada por volumen.
Pinball loss            Evalua los cuantiles, no solo la media.
Cobertura empirica      Valida el intervalo contra su nivel nominal.
Ancho medio             Un intervalo que cubre por ser enorme no sirve.
Sesgo re-censurado      Mide la correccion de censura (ver decision.censoring).
======================  ===================================================

Toda metrica agregada se reporta **con dispersion entre origenes**, nunca como
numero unico: un promedio bueno esconde un origen catastrofico, y el origen
catastrofico es el que va a pasar en produccion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from blindside.data import schema as S
from blindside.evaluate import contracts as C

if TYPE_CHECKING:
    from collections.abc import Sequence

ArrayLike = np.ndarray | pd.Series


# --------------------------------------------------------------------------
# Metricas puntuales
# --------------------------------------------------------------------------
def _as_arrays(*args: ArrayLike) -> tuple[np.ndarray, ...]:
    return tuple(np.asarray(a, dtype="float64").reshape(-1) for a in args)


def mae(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    yt, yp = _as_arrays(y_true, y_pred)
    return float(np.mean(np.abs(yt - yp)))


def rmse(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    yt, yp = _as_arrays(y_true, y_pred)
    return float(np.sqrt(np.mean((yt - yp) ** 2)))


def bias(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Sesgo medio con signo. Negativo = el modelo pide de menos."""
    yt, yp = _as_arrays(y_true, y_pred)
    return float(np.mean(yp - yt))


def mase(y_true: ArrayLike, y_pred: ArrayLike, scale: ArrayLike) -> float:
    """Mean Absolute Scaled Error.

    `scale` es el error absoluto medio en muestra del naive estacional, calculado
    con el **train del fold** (ver validation.splits.naive_seasonal_scale). Llega
    como argumento y no se calcula aca justamente para que no se pueda calcular
    con datos de test por descuido.

    MASE = mean(|y - yhat| / scale). Un valor de 0,8 significa "20 % menos error
    que el naive estacional", que es la forma en que el objetivo del proyecto
    esta expresado.
    """
    yt, yp, sc = _as_arrays(y_true, y_pred, scale)
    if np.any(sc <= 0):
        raise ValueError("la escala de MASE debe ser positiva")
    return float(np.mean(np.abs(yt - yp) / sc))


def wape(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """Weighted Absolute Percentage Error = sum|e| / sum(y).

    Es la lectura de negocio: "nos equivocamos en el 30 % del volumen". No
    explota con ceros porque el denominador es la suma y no cada termino, que es
    la diferencia con MAPE.
    """
    yt, yp = _as_arrays(y_true, y_pred)
    denom = np.abs(yt).sum()
    if denom <= 0:
        return float("nan")
    return float(np.abs(yt - yp).sum() / denom)


def smape(y_true: ArrayLike, y_pred: ArrayLike) -> float:
    """SMAPE simetrico, acotado en [0, 2]. Se reporta solo como contraste."""
    yt, yp = _as_arrays(y_true, y_pred)
    denom = np.abs(yt) + np.abs(yp)
    mask = denom > 0
    if not mask.any():
        return 0.0
    return float(np.mean(2 * np.abs(yt[mask] - yp[mask]) / denom[mask]))


# --------------------------------------------------------------------------
# Metricas de cuantiles e intervalos
# --------------------------------------------------------------------------
def pinball_loss(y_true: ArrayLike, y_pred: ArrayLike, *, q: float) -> float:
    """Perdida cuantilica. Es la que hay que minimizar para que el cuantil sirva.

    Asimetrica a proposito: con `q = 0,9` quedarse corto cuesta nueve veces mas
    que quedarse largo, que es la traduccion directa de la economia del
    newsvendor a una funcion de perdida.
    """
    if not 0 < q < 1:
        raise ValueError(f"q debe estar en (0, 1), llego {q}")
    yt, yp = _as_arrays(y_true, y_pred)
    diff = yt - yp
    return float(np.mean(np.maximum(q * diff, (q - 1) * diff)))


def mean_pinball(y_true: ArrayLike, preds: dict[float, ArrayLike]) -> float:
    """Pinball promedio sobre varios cuantiles. Aproxima el CRPS."""
    if not preds:
        raise ValueError("no se paso ningun cuantil")
    return float(np.mean([pinball_loss(y_true, p, q=q) for q, p in preds.items()]))


def empirical_coverage(y_true: ArrayLike, lo: ArrayLike, hi: ArrayLike) -> float:
    """Fraccion de observaciones dentro del intervalo.

    Es la metrica que valida la promesa del sistema. Un intervalo nominal del
    90 % que en la practica cubre el 60 % hace que el modelo prometa un nivel de
    servicio que no cumple, y esa es una falla peor que un MASE mediocre porque
    es invisible hasta que el stock se agota.
    """
    yt, lo_, hi_ = _as_arrays(y_true, lo, hi)
    inside = (yt >= lo_ - 1e-9) & (yt <= hi_ + 1e-9)
    return float(np.mean(inside))


def mean_interval_width(lo: ArrayLike, hi: ArrayLike) -> float:
    """Ancho medio. Sin esto, cubrir el 100 % es trivial: intervalo infinito."""
    lo_, hi_ = _as_arrays(lo, hi)
    return float(np.mean(hi_ - lo_))


def interval_score(y_true: ArrayLike, lo: ArrayLike, hi: ArrayLike, *, alpha: float) -> float:
    """Winkler interval score: penaliza ancho y penaliza no cubrir.

    Resuelve el conflicto entre cobertura y ancho en un solo numero, asi que
    sirve para rankear intervalos. Menor es mejor.
    """
    yt, lo_, hi_ = _as_arrays(y_true, lo, hi)
    width = hi_ - lo_
    below = (2 / alpha) * np.maximum(lo_ - yt, 0)
    above = (2 / alpha) * np.maximum(yt - hi_, 0)
    return float(np.mean(width + below + above))


def quantile_calibration(y_true: ArrayLike, preds: dict[float, ArrayLike]) -> pd.DataFrame:
    """Cuantil nominal contra frecuencia empirica. Es el grafico de calibracion.

    Para cada `q` se mide la fraccion de observaciones que quedan por debajo de
    la prediccion. Si el modelo esta calibrado, esa fraccion es `q`.
    """
    rows = []
    yt = np.asarray(y_true, dtype="float64").reshape(-1)
    for q, pred in sorted(preds.items()):
        yp = np.asarray(pred, dtype="float64").reshape(-1)
        rows.append(
            {
                "q_nominal": q,
                "q_empirical": float(np.mean(yt <= yp + 1e-9)),
                "pinball": pinball_loss(yt, yp, q=q),
            }
        )
    out = pd.DataFrame(rows)
    out["gap"] = out["q_empirical"] - out["q_nominal"]
    return out


# --------------------------------------------------------------------------
# Agregacion sobre el resultado de backtest
# --------------------------------------------------------------------------
#: Metricas puntuales que se calculan sobre cada grupo del resultado.
POINT_METRICS: tuple[str, ...] = ("mase", "wape", "mae", "rmse", "bias", "smape")


def _point_metrics(g: pd.DataFrame) -> dict[str, float]:
    yt = g[C.Y_TRUE].to_numpy(dtype="float64")
    yp = g[C.Y_PRED].to_numpy(dtype="float64")
    out = {
        "mase": mase(yt, yp, g[C.NAIVE_SCALE].to_numpy(dtype="float64")),
        "wape": wape(yt, yp),
        "mae": mae(yt, yp),
        "rmse": rmse(yt, yp),
        "bias": bias(yt, yp),
        "smape": smape(yt, yp),
        "n": float(len(g)),
    }
    if C.PRED_LO in g.columns and g[C.PRED_LO].notna().any():
        lo = g[C.PRED_LO].to_numpy(dtype="float64")
        hi = g[C.PRED_HI].to_numpy(dtype="float64")
        out["coverage"] = empirical_coverage(yt, lo, hi)
        out["interval_width"] = mean_interval_width(lo, hi)
    return out


def metrics_by_origin(result: pd.DataFrame) -> pd.DataFrame:
    """Metricas por (modelo, origen). Es la tabla base de todo lo demas."""
    rows = []
    for (model, origin), g in result.groupby([C.MODEL, C.ORIGIN], observed=True):
        row = {C.MODEL: model, C.ORIGIN: origin, C.ORIGIN_DATE: g[C.ORIGIN_DATE].iloc[0]}
        row.update(_point_metrics(g))
        rows.append(row)
    return pd.DataFrame(rows).sort_values([C.MODEL, C.ORIGIN], ignore_index=True)


def summarize(result: pd.DataFrame) -> pd.DataFrame:
    """Resumen por modelo **con dispersion entre origenes**.

    Devuelve media, desvio, peor y mejor origen de cada metrica. El peor origen
    es la columna que importa: es la que responde "que pasa el mes que sale mal".
    """
    by_origin = metrics_by_origin(result)
    metric_cols = [
        c for c in by_origin.columns if c in (*POINT_METRICS, "coverage", "interval_width")
    ]
    rows = []
    for model, g in by_origin.groupby(C.MODEL, observed=True):
        for metric in metric_cols:
            vals = g[metric].dropna()
            if vals.empty:
                continue
            # Para las metricas de error el "peor" es el maximo; para cobertura,
            # el peor es el mas lejano del nominal, y eso se juzga aparte.
            rows.append(
                {
                    "model": model,
                    "metric": metric,
                    "mean": float(vals.mean()),
                    "std": float(vals.std(ddof=1)) if len(vals) > 1 else 0.0,
                    "worst_origin": float(vals.max()),
                    "best_origin": float(vals.min()),
                    "n_origins": int(len(vals)),
                }
            )
    return pd.DataFrame(rows)


def metrics_by_horizon(result: pd.DataFrame) -> pd.DataFrame:
    """Metricas por paso de horizonte. Alimenta el test de futuro y la curva de
    degradacion que responde "cuanto dura el modelo"."""
    rows = []
    for (model, h), g in result.groupby([C.MODEL, C.HORIZON_STEP], observed=True):
        row = {C.MODEL: model, C.HORIZON_STEP: int(h)}
        row.update(_point_metrics(g))
        rows.append(row)
    return pd.DataFrame(rows).sort_values([C.MODEL, C.HORIZON_STEP], ignore_index=True)


def metrics_by_group(result: pd.DataFrame, groups: pd.Series, *, name: str) -> pd.DataFrame:
    """Metricas desagregadas por un atributo de serie, p. ej. banda de rotacion.

    `groups` es una Serie indexada por `series_id`. Se usa para el reporte por
    banda de rotacion, que es donde se espera que el modelo complejo **no** gane.
    """
    df = result.copy()
    df[name] = df[S.SERIES_ID].map(groups)
    rows = []
    for (model, grp), g in df.groupby([C.MODEL, name], observed=True):
        row = {C.MODEL: model, name: grp}
        row.update(_point_metrics(g))
        rows.append(row)
    return pd.DataFrame(rows).sort_values([C.MODEL, name], ignore_index=True)


def censoring_metrics(result: pd.DataFrame) -> pd.DataFrame:
    """Sesgo de demanda re-censurada por modelo.

    Se mide **solo en los dias sin ninguna hora de quiebre**, que es donde la
    venta observada es la demanda real y por lo tanto hay verdad de terreno. Ver
    `blindside.decision.censoring.recensored_bias` para el razonamiento completo.

    Devuelve **dos** medidas de sesgo, y no son intercambiables:

    ``recensored_bias``
        La prediccion de demanda latente se re-censura con el patron real de
        quiebres y se compara contra la venta registrada. Es la que se reporta.
    ``clean_day_bias``
        Se compara solo en los dias sin quiebre. Es intuitiva y esta sesgada por
        seleccion: los dias limpios tienden a ser dias de demanda baja, porque el
        stock se agota cuando la gente compra mucho. Se conserva como diagnostico.

    En los dos casos, el sesgo **absoluto** de un solo modelo mezcla el efecto de
    la censura con el de la funcion de perdida: `regression_l1` estima la mediana,
    que en una distribucion con cola derecha esta por debajo de la media. Por eso
    la cifra que se defiende es la **comparacion pareada** de
    `evaluate.backtest.run_censoring_ablation`, donde el efecto de la perdida es
    identico en las dos ramas y se cancela.
    """
    from blindside.decision.censoring import clean_day_bias, recensored_bias

    rows = []
    for model, g in result.groupby(C.MODEL, observed=True):
        clean = ~g[S.IS_CENSORED].to_numpy(dtype=bool)
        rows.append(
            {
                "model": model,
                "recensored_bias": recensored_bias(
                    g[C.Y_OBSERVED], g[C.Y_PRED], available_weight=g[S.AVAILABLE_WEIGHT]
                ),
                "clean_day_bias": clean_day_bias(
                    g[C.Y_OBSERVED], g[C.Y_PRED], is_censored=g[S.IS_CENSORED]
                ),
                "n_clean_days": int(clean.sum()),
                "n_censored_days": int((~clean).sum()),
                "mase_clean": mase(
                    g.loc[clean, C.Y_TRUE], g.loc[clean, C.Y_PRED], g.loc[clean, C.NAIVE_SCALE]
                )
                if clean.any()
                else float("nan"),
                "mase_censored": mase(
                    g.loc[~clean, C.Y_TRUE], g.loc[~clean, C.Y_PRED], g.loc[~clean, C.NAIVE_SCALE]
                )
                if (~clean).any()
                else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def improvement_vs_baseline(
    summary: pd.DataFrame, *, baseline: str, metric: str = "mase"
) -> pd.DataFrame:
    """Mejora porcentual de cada modelo contra un baseline, en una metrica.

    Es la tabla que responde el objetivo SMART: "reducir MASE al menos 20 %
    frente al baseline estacional ingenuo".
    """
    sub = summary[summary["metric"] == metric]
    ref = sub.loc[sub["model"] == baseline, "mean"]
    if ref.empty:
        raise KeyError(f"el baseline '{baseline}' no esta en el resumen")
    ref_value = float(ref.iloc[0])
    out = sub[["model", "mean", "std", "worst_origin", "n_origins"]].copy()
    out["improvement_pct"] = 100 * (1 - out["mean"] / ref_value)
    out["beats_baseline"] = out["mean"] < ref_value
    out["meets_target_20pct"] = out["improvement_pct"] >= 20
    return out.sort_values("mean", ignore_index=True)


def coverage_report(result: pd.DataFrame, *, nominal: float) -> pd.DataFrame:
    """Cobertura nominal contra empirica por modelo, con el ancho al lado."""
    rows = []
    for model, g in result.groupby(C.MODEL, observed=True):
        if C.PRED_LO not in g.columns or g[C.PRED_LO].isna().all():
            continue
        yt = g[C.Y_TRUE].to_numpy(dtype="float64")
        lo = g[C.PRED_LO].to_numpy(dtype="float64")
        hi = g[C.PRED_HI].to_numpy(dtype="float64")
        emp = empirical_coverage(yt, lo, hi)
        rows.append(
            {
                "model": model,
                "coverage_nominal": nominal,
                "coverage_empirical": emp,
                "gap": emp - nominal,
                "interval_width": mean_interval_width(lo, hi),
                "interval_score": interval_score(yt, lo, hi, alpha=1 - nominal),
                "meets_nominal": emp >= nominal - 0.02,
            }
        )
    return pd.DataFrame(rows)


def all_metrics(
    result: pd.DataFrame,
    *,
    quantiles: Sequence[float] = (),
) -> dict[str, pd.DataFrame]:
    """Bateria completa. Es lo que consume el reporte y el dashboard."""
    from blindside.models.base import quantile_col

    out = {
        "by_origin": metrics_by_origin(result),
        "summary": summarize(result),
        "by_horizon": metrics_by_horizon(result),
        "censoring": censoring_metrics(result),
    }
    qcols = {q: quantile_col(q) for q in quantiles}
    available = {q: c for q, c in qcols.items() if c in result.columns}
    if available:
        frames = []
        for model, g in result.groupby(C.MODEL, observed=True):
            cal = quantile_calibration(g[C.Y_TRUE], {q: g[c] for q, c in available.items()})
            cal["model"] = model
            frames.append(cal)
        out["calibration"] = pd.concat(frames, ignore_index=True)
    return out


__all__ = [
    "POINT_METRICS",
    "all_metrics",
    "bias",
    "censoring_metrics",
    "coverage_report",
    "empirical_coverage",
    "improvement_vs_baseline",
    "interval_score",
    "mae",
    "mase",
    "mean_interval_width",
    "mean_pinball",
    "metrics_by_group",
    "metrics_by_horizon",
    "metrics_by_origin",
    "pinball_loss",
    "quantile_calibration",
    "rmse",
    "smape",
    "summarize",
    "wape",
]
