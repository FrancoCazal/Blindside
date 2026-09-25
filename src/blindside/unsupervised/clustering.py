"""Clustering de perfiles de demanda, para arranque en frio.

**El problema que resuelve.** Un producto nuevo en una tienda no tiene historia, asi
que todos sus rezagos llegan nulos y el modelo global lo trata como una serie
cualquiera sin senal. La idea de M4 es darle una pertenencia: si se parece a un grupo
de series que ya existen, hereda su forma.

**La parte delicada es la fuga, y es la razon de como esta escrito esto.** Un cluster
calculado sobre la serie completa mira el futuro: si el 15 de julio una serie cambia
de regimen, un cluster ajustado con julio adentro ya sabe algo del 15 de julio cuando
predice el 1. Por eso `DemandProfileClusters` se ajusta **una vez por origen** sobre
la historia disponible hasta ese dia, y `assign` no reajusta nada. Es la misma
disciplina que el escalador del fold, y el assert antifugas del escalador existe por
un bug de este tipo.

**Por que la forma y no el nivel.** Las features se normalizan por el nivel de la
serie a proposito. Agrupar por nivel daria "productos que venden mucho" contra
"productos que venden poco", que es la banda de rotacion y ya existe. Lo que agrega
informacion es la **forma**: cuando vende dentro de la semana, si es intermitente, si
tiene picos. Dos productos con el mismo perfil semanal y volumenes distintos
pertenecen al mismo grupo.

**K-Means y DBSCAN hacen cosas distintas y las dos se usan.** K-Means parte el espacio
en `k` grupos y siempre asigna, asi que sirve como feature: nunca deja un nulo.
DBSCAN no fuerza una particion y marca **ruido**, asi que sirve para encontrar las
series que no se parecen a nada -- que es informacion operativa distinta, y se cruza
con la deteccion de anomalias.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "CLUSTER_COL",
    "DEFAULT_K",
    "MIN_DAYS",
    "SHAPE_FEATURES",
    "DemandProfileClusters",
    "dbscan_profiles",
    "elegir_k",
    "shape_features",
]

#: Nombre de la columna que el clustering agrega al panel.
CLUSTER_COL: str = "demand_cluster"

#: Cantidad de grupos. Elegido por silueta sobre el panel; ver `elegir_k`.
DEFAULT_K: int = 6

#: Dias minimos de historia para que un perfil semanal signifique algo. Con menos de
#: tres semanas, la media de cada dia de semana sale de dos o tres observaciones.
MIN_DAYS: int = 21

#: Features de **forma**, todas adimensionales o normalizadas por el nivel.
SHAPE_FEATURES: tuple[str, ...] = (
    "cv",
    "tasa_ceros",
    "amplitud_semanal",
    "pico_relativo",
    "autocorr_7",
    "racha_ceros_media",
    "tasa_quiebre",
)


def shape_features(
    panel: pd.DataFrame,
    *,
    target: str = S.DEMAND_LATENT,
    min_days: int = MIN_DAYS,
) -> pd.DataFrame:
    """Una fila por serie con su **forma**, sin el nivel.

    Todas las columnas son adimensionales: un coeficiente de variacion, tasas entre
    0 y 1, y amplitudes divididas por la media. Dos series con la misma forma y
    volumenes distintos dan la misma fila, que es exactamente lo que se quiere para
    que el grupo transfiera informacion de una a la otra.

    Las series con menos de `min_days` quedan **afuera**, no con ceros: un perfil
    semanal estimado sobre dos observaciones por dia es ruido, y meterlo como si
    fuera una forma corrompe los centroides.
    """
    cols = [S.SERIES_ID, S.DATE, target]
    df = panel[cols].copy()
    if S.IS_CENSORED in panel.columns:
        df[S.IS_CENSORED] = panel[S.IS_CENSORED].to_numpy()
    df[S.DATE] = pd.to_datetime(df[S.DATE])
    df = df.sort_values([S.SERIES_ID, S.DATE])
    df["dow"] = df[S.DATE].dt.dayofweek

    por_serie = df.groupby(S.SERIES_ID, observed=True)
    n_dias = por_serie[target].size()
    media = por_serie[target].mean()
    # Denominador seguro: una serie toda cero tiene forma indefinida, no infinita.
    escala = media.replace(0.0, np.nan)

    perfil = df.groupby([S.SERIES_ID, "dow"], observed=True)[target].mean()
    tasa_quiebre = (
        por_serie[S.IS_CENSORED].mean()
        if S.IS_CENSORED in df.columns
        else pd.Series(0.0, index=media.index)
    )

    out = pd.DataFrame(
        {
            "cv": por_serie[target].std(ddof=1) / escala,
            "tasa_ceros": por_serie[target].apply(lambda s: float((s <= 0).mean())),
            "amplitud_semanal": perfil.groupby(S.SERIES_ID).std(ddof=1) / escala,
            "pico_relativo": por_serie[target].max() / escala,
            "autocorr_7": por_serie[target].apply(_autocorr_semanal),
            "racha_ceros_media": por_serie[target].apply(_racha_ceros_media),
            "tasa_quiebre": tasa_quiebre,
        }
    )
    out["n_dias"] = n_dias
    out = out[out["n_dias"] >= min_days]

    # Una serie toda cero deja NaN en todo lo normalizado. Es un caso real y se
    # resuelve con 0, que es la forma correcta: sin variacion ni estacionalidad.
    return out.drop(columns="n_dias").fillna(0.0)


def _autocorr_semanal(s: pd.Series) -> float:
    """Autocorrelacion al rezago 7: cuanta estructura semanal tiene la serie.

    Es la feature que separa un producto con ritmo de semana de uno que se comporta
    como ruido, y es la que el modelo global aprovecha via los rezagos.
    """
    x = s.to_numpy(dtype="float64")
    if len(x) <= 8 or np.allclose(x, x[0]):
        return 0.0
    a, b = x[:-7], x[7:]
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.clip(np.corrcoef(a, b)[0, 1], -1.0, 1.0))


def _racha_ceros_media(s: pd.Series) -> float:
    """Largo medio de una racha de ceros consecutivos.

    Distingue intermitencia **dispersa** de intermitencia **en bloque**: veinte ceros
    sueltos y veinte ceros seguidos dan la misma `tasa_ceros` y exigen decisiones de
    reposicion distintas.
    """
    ceros = (s.to_numpy(dtype="float64") <= 0).astype("int8")
    if ceros.sum() == 0:
        return 0.0
    # Cada cambio de estado abre un bloque; se promedian los largos de los de ceros.
    bloques = np.split(ceros, np.flatnonzero(np.diff(ceros)) + 1)
    largos = [len(b) for b in bloques if b[0] == 1]
    return float(np.mean(largos)) if largos else 0.0


@dataclass
class DemandProfileClusters:
    """Agrupa series por forma de demanda. Se ajusta **una vez por origen**.

    El contrato es deliberadamente parecido al de un `Forecaster`: `fit` ve solo
    historia y `assign` no aprende nada. Si `assign` reajustara, el cluster de una
    serie podria cambiar segun que dias se le pasen, y esa dependencia es una fuga
    con otro nombre.
    """

    k: int = DEFAULT_K
    target: str = S.DEMAND_LATENT
    features: Sequence[str] = SHAPE_FEATURES
    random_state: int = cfg.SEED
    min_days: int = MIN_DAYS

    centroides_: pd.DataFrame | None = field(default=None, init=False)
    escalador_: Any = field(default=None, init=False)
    etiquetas_: pd.Series | None = field(default=None, init=False)
    silueta_: float | None = field(default=None, init=False)
    fallback_: int = field(default=0, init=False)
    """Cluster que reciben las series sin forma estimable. Es el mas poblado."""

    def fit(self, history: pd.DataFrame) -> DemandProfileClusters:
        """Ajusta sobre la historia hasta el origen. `history` no puede traer futuro.

        No se verifica que no lo traiga, porque el llamador es el arnes de
        backtesting y el assert vive alla; lo que se garantiza aca es que no se
        reajusta despues.
        """
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import StandardScaler

        tabla = shape_features(history, target=self.target, min_days=self.min_days)
        if tabla.empty:
            raise ValueError(
                f"ninguna serie llega a {self.min_days} dias de historia, asi que no "
                "hay forma que agrupar. Revisar el origen o bajar min_days."
            )

        cols = list(self.features)
        X = tabla[cols].to_numpy(dtype="float64")

        # Estandarizar es obligatorio: un coeficiente de variacion y una tasa entre
        # 0 y 1 no son comparables, y K-Means usa distancia euclidea.
        self.escalador_ = StandardScaler().fit(X)
        Xs = self.escalador_.transform(X)

        k_efectivo = min(self.k, len(tabla))
        km = KMeans(n_clusters=k_efectivo, random_state=self.random_state, n_init=10)
        etiquetas = km.fit_predict(Xs)

        self.centroides_ = pd.DataFrame(km.cluster_centers_, columns=cols)
        self.etiquetas_ = pd.Series(etiquetas, index=tabla.index, name=CLUSTER_COL)
        self.fallback_ = int(self.etiquetas_.value_counts().idxmax())
        self.silueta_ = (
            float(silhouette_score(Xs, etiquetas)) if 1 < k_efectivo < len(tabla) else None
        )
        return self

    def assign(self, history: pd.DataFrame) -> pd.Series:
        """Cluster por serie, sin reajustar. Indexado por `series_id`.

        Una serie sin forma estimable -- menos de `min_days`, que es justamente el
        caso de arranque en frio -- recibe el cluster **mas poblado** en vez de un
        nulo. Es una decision: el modelo global trata el nulo como rama propia, y la
        rama de "serie nueva" no tiene con que aprenderse. El grupo modal al menos
        le da la forma tipica del catalogo.
        """
        if self.centroides_ is None or self.escalador_ is None:
            raise RuntimeError("DemandProfileClusters: hay que llamar fit antes de assign")

        todas = pd.Index(history[S.SERIES_ID].unique(), name=S.SERIES_ID)
        tabla = shape_features(history, target=self.target, min_days=self.min_days)

        out = pd.Series(self.fallback_, index=todas, dtype="int16", name=CLUSTER_COL)
        if tabla.empty:
            return out

        Xs = self.escalador_.transform(tabla[list(self.features)].to_numpy(dtype="float64"))
        centros = self.centroides_.to_numpy(dtype="float64")
        # Distancia a cada centroide; el argmin es el grupo. Es lo que hace `predict`
        # de KMeans, escrito a mano para no serializar el estimador completo.
        d = ((Xs[:, None, :] - centros[None, :, :]) ** 2).sum(axis=2)
        out.loc[tabla.index] = d.argmin(axis=1).astype("int16")
        return out

    def add_feature(self, panel: pd.DataFrame, etiquetas: pd.Series) -> pd.DataFrame:
        """Pega la columna de cluster al panel, como entero.

        **Entero y no `category`, y esto costo una medicion para descubrirlo.**
        `features.build.feature_columns` filtra la matriz a dtypes numericos, asi que
        una columna categorica de pandas **se descarta en silencio**: el modelo
        entrena sin ella y da exactamente el mismo MASE, que es como se detecto.

        La convencion del proyecto es la que ya usan `store_id` y `product_id`:
        viajan como enteros y se declaran en `categorical_features`, y es LightGBM el
        que las trata sin orden. Pasar el nombre de la columna en ese parametro es
        **obligatorio**; sin eso el modelo parte en "cluster <= 3", que no significa
        nada porque el numero de grupo es una etiqueta arbitraria.
        """
        out = panel.copy()
        mapeado = out[S.SERIES_ID].map(etiquetas).fillna(self.fallback_)
        out[CLUSTER_COL] = mapeado.astype("int16")
        return out


def elegir_k(
    history: pd.DataFrame,
    *,
    candidatos: Sequence[int] = (3, 4, 5, 6, 8, 10),
    target: str = S.DEMAND_LATENT,
    random_state: int = cfg.SEED,
) -> pd.DataFrame:
    """Silueta por cada `k` candidato, para que `DEFAULT_K` sea una medicion.

    No elige solo: devuelve la tabla y la decision se escribe. Un `k` elegido por el
    codigo en cada corrida haria que la feature cambie de significado entre corridas.
    """
    filas = []
    for k in candidatos:
        modelo = DemandProfileClusters(k=k, target=target, random_state=random_state).fit(history)
        conteos = modelo.etiquetas_.value_counts()
        filas.append(
            {
                "k": k,
                "silueta": modelo.silueta_,
                "grupo_mas_chico": int(conteos.min()),
                "grupo_mas_grande": int(conteos.max()),
            }
        )
    return pd.DataFrame(filas)


def dbscan_profiles(
    history: pd.DataFrame,
    *,
    eps: float = 0.9,
    min_samples: int = 10,
    target: str = S.DEMAND_LATENT,
    features: Sequence[str] = SHAPE_FEATURES,
) -> pd.Series:
    """DBSCAN sobre las mismas features. Devuelve etiquetas con **ruido en -1**.

    No sirve como feature del modelo -- deja series sin grupo -- y no es para eso:
    sirve para encontrar las series que no se parecen a nada. K-Means siempre asigna,
    asi que nunca puede decir "esta no entra en ningun grupo", y esa respuesta es
    informacion operativa.

    `eps` esta en el espacio **estandarizado**, asi que 0,9 es nueve decimas de
    desvio en la metrica de siete dimensiones.
    """
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import StandardScaler

    tabla = shape_features(history, target=target)
    if tabla.empty:
        return pd.Series(dtype="int16", name="dbscan_cluster")

    Xs = StandardScaler().fit_transform(tabla[list(features)].to_numpy(dtype="float64"))
    etiquetas = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(Xs)
    return pd.Series(etiquetas, index=tabla.index, dtype="int16", name="dbscan_cluster")
