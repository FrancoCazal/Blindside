"""Atribucion por feature, local y global.

**Que vive aca y que no.** El calculo de TreeSHAP lo hace el modelo, en
`contributions()`, porque depende del booster y es parte de lo que el modelo sabe
hacer de si mismo. Lo que vive aca es la capa de **atribucion**: encontrar el modelo
explicable debajo de los envoltorios, rankear los aportes, y agregarlos sobre muchas
filas. Esa logica estaba dentro del endpoint `/explain` y no tenia test propio ni
forma de usarse desde un notebook.

**Por que TreeSHAP y no la importancia por ganancia.** El modelo ya expone
`importances()` por ganancia, y la ganancia esta sesgada hacia features de alta
cardinalidad: un identificador de producto parece importantisimo porque permite
partir el arbol de muchas formas, no porque informe. La media de los valores
absolutos de SHAP no tiene ese sesgo y esta en las unidades del target, asi que se
puede leer como "cuanto mueve esta feature la prediccion, en promedio".

**Que NO prueba una atribucion.** SHAP atribuye sobre el **modelo**, no sobre el
mundo. Que `discount` tenga aporte alto dice que el modelo se apoya en esa columna,
no que el descuento cause la demanda. Con features correlacionadas -- y los rezagos
de una serie lo estan mucho -- el credito se reparte entre ellas de una forma que
depende del conjunto de fondo, asi que dos features casi redundantes pueden aparecer
las dos con la mitad del aporte.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np
import pandas as pd

__all__ = [
    "Aporte",
    "AtribucionLocal",
    "ModeloExplicable",
    "NoExplicableError",
    "atribucion_global",
    "atribuir",
    "modelo_explicable",
]


class NoExplicableError(TypeError):
    """El modelo no puede emitir contribuciones por feature.

    Es un `TypeError` porque el problema es el **tipo** de modelo cargado y no un
    estado transitorio: reintentar no lo arregla, hay que cargar un modelo de arbol.
    """


@runtime_checkable
class ModeloExplicable(Protocol):
    """Lo minimo que hace falta para atribuir.

    Se declara como Protocol y no como clase base para no forzar herencia: un
    modelo es explicable si sabe armar su matriz de diseno y emitir aportes, sin
    importar de que cuelgue.
    """

    def design_matrix(self, future: pd.DataFrame) -> pd.DataFrame: ...

    def contributions(self, X: pd.DataFrame) -> tuple[pd.DataFrame, float]: ...


@dataclass(frozen=True)
class Aporte:
    """El aporte de una feature a una prediccion concreta."""

    feature: str
    valor: float | None
    """El valor que tomo la feature. `None` si es nulo, que LightGBM admite."""
    contribucion: float
    """Cuanto movio la prediccion respecto del valor base, en unidades del target."""


@dataclass(frozen=True)
class AtribucionLocal:
    """La descomposicion de una prediccion.

    Vale la identidad `valor_base + sum(todas las contribuciones) = prediccion`.
    `aportes` puede estar recortado a los `top_k` mas grandes, asi que la suma de
    **esa lista** no cierra; para eso esta `resto`.
    """

    valor_base: float
    """Lo que el modelo predice sin mirar ninguna feature."""
    aportes: list[Aporte]
    """Los mas influyentes por valor absoluto, de mayor a menor."""
    resto: float
    """La suma de los aportes que quedaron fuera del recorte."""
    n_features: int

    @property
    def prediccion_reconstruida(self) -> float:
        """La prediccion que implica la descomposicion.

        Sirve como chequeo: si no coincide con lo que el modelo predice, la
        atribucion se calculo sobre otra fila o sobre otro cuantil.
        """
        return self.valor_base + sum(a.contribucion for a in self.aportes) + self.resto


def modelo_explicable(model: Any) -> ModeloExplicable:
    """Devuelve el modelo que sabe atribuir, desenvolviendo lo que haga falta.

    El artefacto servido es un conformal envolviendo un LightGBM, y el que sabe de
    features es el de adentro. Desenvuelve en cadena por si aparece mas de una capa.

    Levanta `NoExplicableError` con el nombre del modelo si nadie en la cadena
    puede atribuir, porque el mensaje util es "cargaste un Ridge" y no un
    `AttributeError` sobre un metodo que falta.
    """
    visto: list[str] = []
    actual = model
    for _ in range(8):  # cota, no deberia haber cadenas asi de largas
        visto.append(str(getattr(actual, "name", type(actual).__name__)))
        if isinstance(actual, ModeloExplicable):
            return actual
        siguiente = getattr(actual, "base", None)
        if siguiente is None or siguiente is actual:
            break
        actual = siguiente

    raise NoExplicableError(
        f"el modelo '{visto[0]}' no produce contribuciones por feature"
        + (f" (se reviso la cadena {' -> '.join(visto)})" if len(visto) > 1 else "")
        + ". Solo los modelos de arbol las emiten; cargar un LightGBM."
    )


def atribuir(
    model: Any,
    future: pd.DataFrame,
    *,
    top_k: int = 10,
    quantile: float | None = None,
) -> AtribucionLocal:
    """Descompone la prediccion de **una** fila de futuro.

    `future` tiene que traer exactamente una fila: la atribucion local explica una
    prediccion concreta, y aceptar varias invitaria a promediarlas sin decirlo.
    Para eso esta `atribucion_global`.

    `quantile` elige que booster explicar. Por defecto el modelo cuantilico explica
    el cuantil **critico** y no la mediana, porque la cifra que se muestra es la
    cantidad a pedir.
    """
    if len(future) != 1:
        raise ValueError(
            f"atribuir explica una prediccion, y recibio {len(future)} filas. "
            "Filtrar a una, o usar atribucion_global."
        )
    if top_k < 1:
        raise ValueError(f"top_k tiene que ser >= 1, y es {top_k}")

    interno = modelo_explicable(model)
    X = interno.design_matrix(future)
    aportes_df, valor_base = _contribuciones(interno, X, quantile)

    fila = aportes_df.iloc[0]
    valores = X.iloc[0]
    orden = fila.abs().sort_values(ascending=False)
    elegidas = orden.head(top_k).index

    aportes = [
        Aporte(
            feature=str(f),
            valor=_float_o_none(valores.get(f)),
            contribucion=float(fila[f]),
        )
        for f in elegidas
    ]
    resto = float(fila.drop(index=elegidas).sum()) if len(fila) > len(elegidas) else 0.0

    return AtribucionLocal(
        valor_base=float(valor_base),
        aportes=aportes,
        resto=resto,
        n_features=int(len(fila)),
    )


def atribucion_global(
    model: Any,
    future: pd.DataFrame,
    *,
    top_k: int | None = None,
    quantile: float | None = None,
) -> pd.DataFrame:
    """Importancia por media de |SHAP| sobre las filas que se le pasen.

    Es la alternativa sin sesgo a la importancia por ganancia, y ademas viene en
    unidades del target. Devuelve un DataFrame ordenado con `aporte_medio` (la
    media de los valores absolutos) y `aporte_neto` (la media con signo, que dice
    si la feature empuja para arriba o para abajo en promedio).

    Las dos columnas juntas son mas informativas que cualquiera sola: una feature
    con `aporte_medio` alto y `aporte_neto` cerca de cero es la que **discrimina**
    -- sube unas series y baja otras -- mientras que una con los dos altos corre el
    nivel de todo el panel para el mismo lado.
    """
    if future.empty:
        raise ValueError("atribucion_global necesita al menos una fila de futuro")

    interno = modelo_explicable(model)
    X = interno.design_matrix(future)
    aportes_df, _ = _contribuciones(interno, X, quantile)

    tabla = pd.DataFrame(
        {
            "aporte_medio": aportes_df.abs().mean(),
            "aporte_neto": aportes_df.mean(),
        }
    ).sort_values("aporte_medio", ascending=False)
    tabla.index.name = "feature"

    return tabla.head(top_k) if top_k is not None else tabla


def _contribuciones(
    interno: ModeloExplicable, X: pd.DataFrame, quantile: float | None
) -> tuple[pd.DataFrame, float]:
    """Llama a `contributions` pasando el cuantil solo si el modelo lo acepta.

    El puntual no tiene boosters por cuantil, asi que pasarle `quantile` seria un
    `TypeError`. Pedir un cuantil a un modelo que no los tiene es un error del que
    llama y se dice, en vez de ignorarlo en silencio.
    """
    if quantile is None:
        return interno.contributions(X)
    try:
        return interno.contributions(X, quantile=quantile)  # type: ignore[call-arg]
    except TypeError as exc:
        nombre = getattr(interno, "name", type(interno).__name__)
        raise NoExplicableError(
            f"se pidio el cuantil {quantile} pero '{nombre}' no tiene boosters por "
            "cuantil; es un modelo puntual y solo puede explicar su propia salida."
        ) from exc


def _float_o_none(v: Any) -> float | None:
    """LightGBM admite nulos como rama, asi que el valor de una feature puede faltar."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(f) else f
