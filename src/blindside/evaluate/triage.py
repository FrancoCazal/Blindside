"""Triage de cartera: donde mirar primero, y por que motivo.

**El problema que resuelve.** La interfaz operativa responde "cuanto pido de esta
serie". Lo que no responde nadie es "de las 3.066, cuales miro primero". Un promedio
de MASE 0,82 no dice donde el modelo falla, y una tabla ordenada por cantidad a pedir
solo dice donde hay volumen.

**Por que NO hay un score unico de criticidad, y esto esta medido.** Los ejes de
criticidad son **ortogonales**: el solapamiento entre el top 50 por volumen y el top
50 por error normalizado es de **0 series de 50**. Promediarlos en un indice daria un
numero que no significa nada y, peor, perderia la informacion que sirve, que es **por
que** una serie entro a la lista: el remedio para "el modelo no le acierta" no es el
mismo que para "viene quebrada tres dias".

Por eso esto devuelve **grupos con motivo**, no un ranking.

**Y por que no un top 10.** Medido sobre el panel, el costo esta **repartido**: el top
10 % de las series concentra 26,5 % del costo de newsvendor y el top 20 % el 41,4 %.
Un Pareto fuerte seria 70-80 % en el top 20 %. Con esta forma, un "top 10 productos
criticos" es un corte arbitrario: la serie 11 se parece a la 10. Los grupos por motivo
si tienen un corte defendible, porque cada umbral responde a una pregunta distinta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "GRUPOS",
    "MOTIVO_COL",
    "UMBRALES",
    "Grupo",
    "Umbrales",
    "resumen_por_grupo",
    "series_signals",
    "triage",
]

MOTIVO_COL: str = "motivos"

#: Ventana reciente para las señales de estado. 28 dias: cuatro ciclos semanales, que
#: es el minimo para que una tasa por dia de semana no salga de una sola observacion.
VENTANA_DIAS: int = 28


@dataclass(frozen=True)
class Umbrales:
    """Cortes de cada grupo. Cada uno esta medido, no elegido por gusto.

    El antecedente que justifica medirlos: la primera version de la alerta de la
    interfaz usaba `censored_days_last_28 >= 14`, y la mediana del panel es 12 de 28,
    asi que marcaba el 35,6 % del catalogo. Una alerta que marca un tercio del
    catalogo no es una alerta.
    """

    mase_no_confiable: float = 1.0
    """MASE > 1 es **peor que el naive estacional**. El corte no es arbitrario: es el
    punto donde el modelo deja de justificar su existencia para esa serie. Aisla el
    13,2 % del catalogo (404 series)."""

    frac_estimada_escasa: float = 0.30
    """Fraccion de la demanda reciente que es **estimada** y no observada. El p90 del
    panel es 0,28, asi que 0,30 aisla el 6,6 % (201 series)."""

    racha_vigente_dias: int = 5
    """Dias consecutivos de quiebre que terminan en el ultimo dia. Aisla el 3,5 %
    (108 series). Con 3 dias marcaria el 21,9 %, porque la variable es discreta y hay
    muchos empates."""

    cuantil_volumen: float = 0.90
    """El volumen no tiene un corte natural, asi que se usa un cuantil y se declara.
    Por construccion marca el 10 %."""


UMBRALES = Umbrales()


@dataclass(frozen=True)
class Grupo:
    """Un motivo por el que una serie pide atencion."""

    clave: str
    etiqueta: str
    que_significa: str
    que_hacer: str


#: Los cuatro grupos, en orden de cuanto costo concentran. Los textos de `etiqueta`,
#: `que_significa` y `que_hacer` son **visibles en la interfaz**, asi que van con tildes;
#: los comentarios y docstrings del paquete siguen la convencion sin tildes del repo.
GRUPOS: tuple[Grupo, ...] = (
    Grupo(
        clave="no_confiable",
        etiqueta="Modelo no confiable",
        que_significa=(
            "El modelo le pierde al naive estacional en esta serie. El MASE global de "
            "0,82 no aplica acá."
        ),
        que_hacer=(
            "No usar la cantidad sugerida sin revisarla. La media móvil de 21 días es "
            "mejor referencia para estas series hasta entender por qué fallan."
        ),
    ),
    Grupo(
        clave="alto_volumen",
        etiqueta="Alto volumen",
        que_significa=(
            "Está en el decil de más demanda, así que un error cuesta en absoluto "
            "aunque el error relativo sea chico."
        ),
        que_hacer="Revisar primero por impacto, aunque el modelo acierte.",
    ),
    Grupo(
        clave="senal_escasa",
        etiqueta="Señal escasa",
        que_significa=(
            "Buena parte de la demanda reciente es **estimada** y no observada, porque "
            "la serie estuvo mucho en quiebre."
        ),
        que_hacer=(
            "El pronóstico se apoya en la corrección de censura más que en venta real. "
            "Tratar el intervalo como más ancho de lo que dice."
        ),
    ),
    Grupo(
        clave="quebrado_ahora",
        etiqueta="Quebrado ahora",
        que_significa="Viene con quiebre en los últimos días, sin cortar.",
        que_hacer=(
            "Es lo único de la lista que es urgente hoy y no analítico: hay demanda "
            "que se está perdiendo mientras se lee esto."
        ),
    ),
)


def series_signals(
    panel: pd.DataFrame,
    result: pd.DataFrame | None = None,
    *,
    target: str = S.DEMAND_LATENT,
    model: str | None = None,
    ventana_dias: int = VENTANA_DIAS,
) -> pd.DataFrame:
    """Una fila por serie con los ejes de criticidad, indexada por `series_id`.

    `result` es un resultado de backtest. Si viene, se agrega el error **normalizado**
    por serie; si no, esa columna queda ausente y `triage` no puede formar el grupo de
    modelo no confiable.

    **El error va normalizado y no en MAE**, y la diferencia importa: el MAE por serie
    correlaciona **0,86** con el nivel de demanda, asi que rankear por MAE es rankear
    por volumen con otro nombre. Dividido por el denominador de MASE, la correlacion
    baja a 0,36 y el solapamiento del top 50 con el de volumen pasa de 23 a **0**.
    """
    fin = pd.to_datetime(panel[S.DATE]).max()
    reciente = panel[pd.to_datetime(panel[S.DATE]) > fin - pd.Timedelta(days=ventana_dias)]
    g = reciente.groupby(S.SERIES_ID, observed=True)

    obs = S.SALE_AMOUNT if S.SALE_AMOUNT in panel.columns else target
    señales = pd.DataFrame(
        {
            "demanda_media": g[target].mean(),
            "frac_estimada": g.apply(_frac_estimada, target=target, obs=obs, include_groups=False),
            "racha_vigente": g[S.IS_CENSORED].apply(_racha_vigente)
            if S.IS_CENSORED in panel.columns
            else 0,
            "tasa_quiebre": g[S.IS_CENSORED].mean() if S.IS_CENSORED in panel.columns else 0.0,
        }
    )
    señales["dias"] = g[target].size()

    if result is not None and not result.empty:
        señales["mase_serie"] = _mase_por_serie(panel, result, target=target, model=model)

    return señales.fillna(0.0)


def _frac_estimada(d: pd.DataFrame, *, target: str, obs: str) -> float:
    """Que fraccion de la demanda reciente la puso la correccion y no la caja.

    Se prefiere esto a "dias con quiebre" porque pondera por **masa de demanda**: diez
    dias con una hora de quiebre cada uno no es lo mismo que dos dias enteros caidos, y
    contando dias los dos dan lo mismo.
    """
    if target not in d.columns or obs not in d.columns or target == obs:
        return 0.0
    estimada = (d[target] - d[obs]).clip(lower=0).sum()
    total = d[target].sum()
    return float(estimada / total) if total > 0 else 0.0


def _racha_vigente(s: pd.Series) -> int:
    """Dias consecutivos de quiebre que **terminan** en el ultimo dia.

    Es distinto de la racha maxima historica, y la diferencia es grande: en este panel
    la racha maxima llega a 95 dias pero la **vigente** maxima es de 6. Un umbral
    pensado para la historica nunca se dispararia.
    """
    x = np.asarray(s, dtype=bool)
    n = 0
    for v in x[::-1]:
        if not v:
            break
        n += 1
    return int(n)


def _mase_por_serie(
    panel: pd.DataFrame,
    result: pd.DataFrame,
    *,
    target: str,
    model: str | None,
) -> pd.Series:
    """MASE por serie del modelo elegido, con el denominador en muestra del panel."""
    if model is None:
        preferidos = [m for m in result["model"].unique() if "cqr" in str(m)]
        model = preferidos[0] if preferidos else str(result["model"].iloc[0])
    sub = result[result["model"] == model]
    if sub.empty:
        return pd.Series(dtype="float64")

    sl = cfg.FORECAST.season_length
    ordenado = panel.sort_values([S.SERIES_ID, S.DATE])
    denom = ordenado.groupby(S.SERIES_ID, observed=True)[target].apply(
        lambda s: _mae_naive_estacional(s.to_numpy(dtype="float64"), sl)
    )

    ae = (sub["y_true"] - sub["y_pred"]).abs()
    mae = ae.groupby(sub[S.SERIES_ID]).mean()
    return (mae / denom.reindex(mae.index)).replace([np.inf, -np.inf], np.nan)


def _mae_naive_estacional(y: np.ndarray, season_length: int) -> float:
    if len(y) <= season_length:
        return float("nan")
    return float(np.abs(y[season_length:] - y[:-season_length]).mean())


def triage(
    señales: pd.DataFrame,
    *,
    umbrales: Umbrales = UMBRALES,
    grupos: Sequence[Grupo] = GRUPOS,
) -> pd.DataFrame:
    """Marca una columna booleana por grupo, mas `motivos` con los que aplican.

    Una serie puede estar en **varios** grupos o en ninguno. Que la mayoria no este en
    ninguno es el resultado buscado: sobre el panel completo los cuatro grupos juntos
    aislan el 26 % del catalogo, y el resto no necesita atencion especial.
    """
    out = señales.copy()
    disponibles = {g.clave for g in grupos}

    if "mase_serie" in out.columns and "no_confiable" in disponibles:
        out["no_confiable"] = out["mase_serie"] > umbrales.mase_no_confiable
    if "demanda_media" in out.columns and "alto_volumen" in disponibles:
        corte = out["demanda_media"].quantile(umbrales.cuantil_volumen)
        out["alto_volumen"] = out["demanda_media"] >= corte
    if "frac_estimada" in out.columns and "senal_escasa" in disponibles:
        out["senal_escasa"] = out["frac_estimada"] > umbrales.frac_estimada_escasa
    if "racha_vigente" in out.columns and "quebrado_ahora" in disponibles:
        out["quebrado_ahora"] = out["racha_vigente"] >= umbrales.racha_vigente_dias

    presentes = [g for g in grupos if g.clave in out.columns]
    if presentes:
        etiquetas = {g.clave: g.etiqueta for g in presentes}
        out[MOTIVO_COL] = [
            ", ".join(etiquetas[g.clave] for g in presentes if bool(fila[g.clave]))
            for _, fila in out.iterrows()
        ]
        out["n_motivos"] = sum(out[g.clave].astype(int) for g in presentes)
    else:
        out[MOTIVO_COL] = ""
        out["n_motivos"] = 0

    return out


def resumen_por_grupo(
    marcado: pd.DataFrame, *, grupos: Sequence[Grupo] = GRUPOS, peso: str = "demanda_media"
) -> pd.DataFrame:
    """Cuantas series y cuanto volumen cae en cada grupo, con su solapamiento.

    El volumen va porque "404 series" y "22 % del volumen" son dos cosas distintas y
    las dos hacen falta para priorizar.
    """
    total_peso = float(marcado[peso].sum()) if peso in marcado.columns else 0.0
    filas = []
    for g in grupos:
        if g.clave not in marcado.columns:
            continue
        m = marcado[g.clave].astype(bool)
        filas.append(
            {
                "grupo": g.etiqueta,
                "clave": g.clave,
                "series": int(m.sum()),
                "share_series": float(m.mean()),
                "share_volumen": (
                    float(marcado.loc[m, peso].sum() / total_peso) if total_peso > 0 else 0.0
                ),
                "solo_este_motivo": int((m & (marcado["n_motivos"] == 1)).sum()),
            }
        )
    return pd.DataFrame(filas).sort_values("share_volumen", ascending=False)
