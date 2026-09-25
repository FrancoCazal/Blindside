"""Explicabilidad: atribucion por feature de las predicciones.

El calculo de TreeSHAP lo hace el modelo (`contributions()`); lo que vive aca es la
capa que lo usa -- desenvolver envoltorios, rankear, agregar sobre muchas filas.
"""

from blindside.explain.attribution import (
    Aporte,
    AtribucionLocal,
    ModeloExplicable,
    NoExplicableError,
    atribucion_global,
    atribuir,
    modelo_explicable,
)

__all__ = [
    "Aporte",
    "AtribucionLocal",
    "ModeloExplicable",
    "NoExplicableError",
    "atribucion_global",
    "atribuir",
    "modelo_explicable",
]
