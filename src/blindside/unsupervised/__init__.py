"""Aprendizaje no supervisado sobre el catalogo: estructura, grupos y anomalias.

Tres piezas con propositos distintos:

- `embeddings`: proyeccion 2D del catalogo con PCA, para el mapa de la interfaz.
- `clustering`: grupos por **forma** de demanda, como feature de arranque en frio.
- `anomalies`: ventanas raras y residuos inesperados, para no entrenar sobre basura.

Las tres comparten una disciplina: nada se ajusta con datos posteriores al origen.
Un cluster o un detector ajustado sobre el panel completo es una fuga, aunque no
toque la columna de target.
"""

from blindside.unsupervised.anomalies import (
    ANOMALY_COL,
    SCORE_COL,
    WindowAnomalyDetector,
    perfil_por_cluster,
    residual_anomalies,
)
from blindside.unsupervised.clustering import (
    CLUSTER_COL,
    DEFAULT_K,
    SHAPE_FEATURES,
    DemandProfileClusters,
    dbscan_profiles,
    elegir_k,
    shape_features,
)
from blindside.unsupervised.embeddings import (
    FEATURES,
    product_features,
    project_products,
    rotation_band,
)

__all__ = [
    "ANOMALY_COL",
    "CLUSTER_COL",
    "DEFAULT_K",
    "FEATURES",
    "SCORE_COL",
    "SHAPE_FEATURES",
    "DemandProfileClusters",
    "WindowAnomalyDetector",
    "dbscan_profiles",
    "elegir_k",
    "perfil_por_cluster",
    "product_features",
    "project_products",
    "residual_anomalies",
    "rotation_band",
    "shape_features",
]
