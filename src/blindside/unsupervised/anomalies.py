"""Deteccion de anomalias sobre ventanas de demanda.

**Para que sirve y para que no, que en este dataset hay que decirlo.** El plan declara
Isolation Forest "para marcar cargas erroneas y quiebres antes de que contaminen el
entrenamiento". La mitad de eso ya esta resuelta: FreshRetailNet **anota el quiebre
hora por hora**, asi que detectar quiebres con un modelo no supervisado seria estimar
algo que viene etiquetado, y peor. Lo que **no** viene etiquetado es el resto: cargas
mal hechas, picos imposibles, saltos de nivel, dias con una unidad vendida a las 3 de
la manana. Eso es lo que esto busca.

Dicho de otro modo: la utilidad se mide contra la columna `is_censored`, y el buen
resultado es que la deteccion encuentre cosas que **no** son quiebres. Si solo
redescubre quiebres, no agrega nada. El modulo reporta ese solapamiento a proposito.

**Por que ventanas y no dias sueltos.** Un dia con demanda 8 cuando la media es 3 no
es raro de por si; lo raro es la **forma**: que suba a 8 y vuelva a 3 en un dia, o que
lleve cinco dias seguidos en 8. Isolation Forest sobre una ventana ve la trayectoria.
Un dia suelto solo permite marcar colas de la distribucion, que es lo que hace un
z-score y no necesita un bosque.

**La fuga tambien aplica aca.** Las ventanas se estandarizan **por serie y con su
propia historia**, no con estadisticos del panel completo. Y si esto se usa para
filtrar el entrenamiento, el ajuste tiene que ser por fold: un detector entrenado con
el panel entero vio los dias de test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.data import schema as S

__all__ = [
    "ANOMALY_COL",
    "DEFAULT_CONTAMINATION",
    "DEFAULT_WINDOW",
    "SCORE_COL",
    "WindowAnomalyDetector",
    "perfil_por_cluster",
    "residual_anomalies",
]

#: Largo de la ventana. Dos semanas: cubre dos ciclos semanales, asi que un pico
#: aislado se distingue de un cambio de nivel.
DEFAULT_WINDOW: int = 14

#: Fraccion de ventanas que se marcan. No es una estimacion de cuantas anomalias hay
#: -- eso no se sabe -- sino un presupuesto de revision: el 1 % mas raro.
DEFAULT_CONTAMINATION: float = 0.01

ANOMALY_COL: str = "is_anomaly"
SCORE_COL: str = "anomaly_score"


@dataclass
class WindowAnomalyDetector:
    """Isolation Forest sobre ventanas deslizantes de demanda.

    `fit` y `score` estan separados por la misma razon que en el clustering: si esto
    filtra datos de entrenamiento, el detector se ajusta con el train del fold y
    nunca con el panel completo.
    """

    window: int = DEFAULT_WINDOW
    contamination: float = DEFAULT_CONTAMINATION
    target: str = S.DEMAND_LATENT
    random_state: int = cfg.SEED
    n_estimators: int = 200

    bosque_: Any = field(default=None, init=False)
    umbral_: float | None = field(default=None, init=False)
    n_ventanas_: int = field(default=0, init=False)

    def fit(self, history: pd.DataFrame) -> WindowAnomalyDetector:
        from sklearn.ensemble import IsolationForest

        X, _ = self._ventanas(history)
        if len(X) == 0:
            raise ValueError(
                f"ninguna serie llega a {self.window} dias, asi que no hay ventana "
                "que evaluar. Bajar window o revisar el panel."
            )

        self.bosque_ = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
        ).fit(X)
        self.n_ventanas_ = int(len(X))
        # El umbral queda fijado por el ajuste, no se recalcula en cada `score`: si
        # se recalculara, marcar siempre el 1 % mas raro DEL LOTE QUE SE PASE haria
        # que el resultado dependa de con que otras filas vino.
        self.umbral_ = float(np.quantile(self.bosque_.score_samples(X), self.contamination))
        return self

    def score(self, panel: pd.DataFrame) -> pd.DataFrame:
        """Puntaje por (serie, dia) del **final** de cada ventana.

        Se atribuye al ultimo dia y no al centro porque el uso es operativo: la
        pregunta es "lo de ayer fue raro", con la ventana que termina ahi. Atribuir
        al centro necesitaria dias posteriores, que en produccion no existen.

        Puntaje mas **bajo** es mas anomalo, que es la convencion de sklearn y se
        mantiene para que no haya dos convenciones dando vueltas.
        """
        if self.bosque_ is None or self.umbral_ is None:
            raise RuntimeError("WindowAnomalyDetector: hay que llamar fit antes de score")

        X, claves = self._ventanas(panel)
        if len(X) == 0:
            return pd.DataFrame(columns=[S.SERIES_ID, S.DATE, SCORE_COL, ANOMALY_COL])

        puntajes = self.bosque_.score_samples(X)
        out = pd.DataFrame(claves, columns=[S.SERIES_ID, S.DATE])
        out[SCORE_COL] = puntajes
        out[ANOMALY_COL] = puntajes <= self.umbral_
        return out

    def _ventanas(self, panel: pd.DataFrame) -> tuple[np.ndarray, list[tuple[Any, Any]]]:
        """Ventanas normalizadas por serie, con la clave del ultimo dia de cada una.

        La normalizacion es **por serie**: se divide por la media de la propia serie,
        asi que la ventana describe forma y no nivel. Sin eso, Isolation Forest
        marcaria como anomalas todas las ventanas de los productos de alta rotacion,
        que es la variable de escala y no una rareza.
        """
        df = panel[[S.SERIES_ID, S.DATE, self.target]].copy()
        df[S.DATE] = pd.to_datetime(df[S.DATE])
        df = df.sort_values([S.SERIES_ID, S.DATE])

        bloques: list[np.ndarray] = []
        claves: list[tuple[Any, Any]] = []
        for sid, g in df.groupby(S.SERIES_ID, observed=True, sort=True):
            y = g[self.target].to_numpy(dtype="float64")
            if len(y) < self.window:
                continue
            escala = y.mean()
            yn = y / escala if escala > 0 else y

            # Ventanas deslizantes sin copiar: vista con stride.
            v = np.lib.stride_tricks.sliding_window_view(yn, self.window)
            bloques.append(v)
            fechas = g[S.DATE].to_numpy()[self.window - 1 :]
            claves.extend((sid, f) for f in fechas)

        if not bloques:
            return np.empty((0, self.window)), []
        return np.vstack(bloques), claves

    def contraste_con_censura(self, panel: pd.DataFrame) -> pd.DataFrame:
        """Cuanto de lo detectado ya estaba anotado como quiebre.

        Es la medicion que dice si esto aporta algo. Si casi todo lo marcado es
        quiebre, el detector redescubre una columna que ya existe; el valor esta en
        las anomalias que **no** son quiebre, porque esas no tienen etiqueta y son
        las que contaminan el entrenamiento en silencio.
        """
        if S.IS_CENSORED not in panel.columns:
            raise ValueError(f"el panel no trae '{S.IS_CENSORED}', no hay con que contrastar")

        marcas = self.score(panel)
        ref = panel[[S.SERIES_ID, S.DATE, S.IS_CENSORED]].copy()
        ref[S.DATE] = pd.to_datetime(ref[S.DATE])
        junto = marcas.merge(ref, on=[S.SERIES_ID, S.DATE], how="left")

        anom = junto[junto[ANOMALY_COL]]
        ya_eran = anom[S.IS_CENSORED].fillna(False).astype(bool)
        return pd.DataFrame(
            [
                {
                    "ventanas": int(len(junto)),
                    "marcadas": int(len(anom)),
                    "tasa_marcado": len(anom) / max(len(junto), 1),
                    "ya_eran_quiebre": float(ya_eran.mean()) if len(anom) else 0.0,
                    "hallazgos_nuevos": int((~ya_eran).sum()),
                    "tasa_quiebre_del_panel": float(junto[S.IS_CENSORED].fillna(False).mean()),
                }
            ]
        )


def residual_anomalies(
    result: pd.DataFrame,
    *,
    z: float = 3.0,
    y_col: str = "y_true",
    pred_col: str = "y_pred",
) -> pd.DataFrame:
    """Anomalias sobre el **residuo** del pronostico, que es lo otro que pide M4.

    Detectar sobre la serie encuentra lo que es raro en si mismo; detectar sobre el
    residuo encuentra lo que el **modelo no vio venir**, que es distinto y mas util
    operativamente: un pico de fin de semana es raro en la serie y no es noticia
    porque el modelo lo esperaba.

    El residuo se estandariza **por serie**, porque la varianza del error escala con
    el nivel: tres unidades de error en un producto de alta rotacion son normales y
    en uno de baja son enormes.
    """
    faltan = {S.SERIES_ID, y_col, pred_col} - set(result.columns)
    if faltan:
        raise ValueError(f"faltan columnas en el resultado de backtest: {sorted(faltan)}")

    df = result.copy()
    df["residuo"] = df[y_col] - df[pred_col]
    por_serie = df.groupby(S.SERIES_ID, observed=True)["residuo"]
    # ddof=0: es la dispersion observada de esta serie, no una inferencia sobre una
    # poblacion mayor. Con horizontes cortos la diferencia no es despreciable.
    desvio = por_serie.transform(lambda s: s.std(ddof=0))
    df["z_residuo"] = (df["residuo"] - por_serie.transform("mean")) / desvio.replace(0.0, np.nan)
    df[ANOMALY_COL] = df["z_residuo"].abs() >= z
    # Una serie con residuo constante no tiene sorpresas: NaN no es anomalia.
    df[ANOMALY_COL] = df[ANOMALY_COL].fillna(False)
    return df


def perfil_por_cluster(
    panel: pd.DataFrame, etiquetas: pd.Series, *, target: str = S.DEMAND_LATENT
) -> pd.DataFrame:
    """Resumen de cada grupo, para que los clusters sean interpretables.

    Un cluster sin descripcion es un numero. Esto da el nivel medio, la
    intermitencia y la tasa de quiebre por grupo, que es lo que permite decirle a
    alguien "el grupo 3 son los intermitentes de baja rotacion".
    """
    df = panel[[S.SERIES_ID, target]].copy()
    if S.IS_CENSORED in panel.columns:
        df[S.IS_CENSORED] = panel[S.IS_CENSORED].to_numpy()
    df["cluster"] = df[S.SERIES_ID].map(etiquetas)
    df = df[df["cluster"].notna()]

    g = df.groupby("cluster", observed=True)
    out = pd.DataFrame(
        {
            "n_series": g[S.SERIES_ID].nunique(),
            "demanda_media": g[target].mean(),
            "tasa_ceros": g[target].apply(lambda s: float((s <= 0).mean())),
        }
    )
    if S.IS_CENSORED in df.columns:
        out["tasa_quiebre"] = g[S.IS_CENSORED].mean()
    return out.sort_values("demanda_media", ascending=False)
