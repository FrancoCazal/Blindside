"""Busqueda de hiperparametros con Optuna, sobre origenes moviles.

**La decision central es que el objetivo es el backtest y no una validacion cruzada.**
Un `GridSearchCV` con K-Fold aleatorio sobre datos de panel es la forma mas facil de
producir un numero excelente y falso: cada fold mira dias posteriores a los de su
train, asi que optimiza contra un problema mas facil que el real. Aca cada trial corre
el **mismo** `run_backtest` que produce las metricas oficiales, con los mismos origenes
moviles, y el objetivo es el MASE medio entre origenes.

El costo de esa decision es que cada trial vale un backtest completo. Es la razon de
que la busqueda tome una submuestra de series y menos origenes, y de que eso se
declare en el reporte en vez de presentarse como si se hubiera buscado sobre todo.

**Por que penalizar la dispersion.** El objetivo no es el MASE medio pelado sino
`media + peso * desvio entre origenes`. Un conjunto de parametros que promedia 0,82
oscilando entre 0,70 y 0,95 es peor en produccion que uno que promedia 0,84 con
desvio 0,02, porque lo que se sufre es el origen malo y no el promedio. Con
`peso = 0` se recupera el criterio ingenuo.

**Optuna es opcional.** Esta en `requirements.txt` pero la imagen de servicio lo deja
afuera, y el import es perezoso para que importar este modulo no lo exija.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.data import schema as S

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_N_TRIALS",
    "Busqueda",
    "Resultado",
    "buscar_lgbm",
    "disponible",
    "espacio_lgbm",
]

#: Trials por defecto. Pocos a proposito: con TPE la mayor parte de la mejora aparece
#: temprano, y cada trial cuesta un backtest entero.
DEFAULT_N_TRIALS: int = 25


def disponible() -> bool:
    """Si Optuna esta instalado. No levanta, para que el llamador pueda decidir."""
    return find_spec("optuna") is not None


@dataclass(frozen=True)
class Busqueda:
    """Alcance de la busqueda. Se persiste con el resultado para que sea reproducible.

    Los valores por defecto estan reducidos respecto de la corrida oficial: 400 series
    y 4 origenes en vez de 3066 y 8. Es un presupuesto, y el reporte lo declara.
    """

    n_trials: int = DEFAULT_N_TRIALS
    n_series: int = 400
    n_origins: int = 4
    n_estimators: int = 300
    peso_dispersion: float = 0.5
    """Cuanto pesa el desvio entre origenes en el objetivo. 0 = solo la media."""
    seed: int = cfg.SEED


@dataclass
class Resultado:
    """Lo que la busqueda encontro, con el contraste contra los parametros actuales."""

    mejores_params: dict[str, Any]
    mejor_objetivo: float
    mejor_mase: float
    mejor_desvio: float
    base_objetivo: float
    base_mase: float
    base_desvio: float
    busqueda: Busqueda
    historia: pd.DataFrame = field(repr=False)

    @property
    def mejora_pct(self) -> float:
        """Mejora del MASE contra los parametros por defecto, en porcentaje."""
        return (1.0 - self.mejor_mase / self.base_mase) * 100.0

    @property
    def vale_la_pena(self) -> bool:
        """Si la mejora supera la dispersion entre origenes de la propia corrida.

        Es el criterio que evita adoptar ruido: una mejora de 0,3 % cuando el desvio
        entre origenes es de 4 % no es una mejora, es una realizacion afortunada del
        azar sobre los origenes que se eligieron.
        """
        return (self.base_mase - self.mejor_mase) > self.base_desvio

    def a_json(self, ruta: Path) -> Path:
        """Persiste lo necesario para reproducir y para auditar la decision."""
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(
                {
                    "mejores_params": self.mejores_params,
                    "mejor_mase": self.mejor_mase,
                    "mejor_desvio": self.mejor_desvio,
                    "base_mase": self.base_mase,
                    "base_desvio": self.base_desvio,
                    "mejora_pct": self.mejora_pct,
                    "vale_la_pena": self.vale_la_pena,
                    "busqueda": asdict(self.busqueda),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return ruta


def espacio_lgbm(trial: Any) -> dict[str, Any]:
    """Espacio de busqueda para LightGBM.

    Los rangos estan centrados en los valores actuales de `DEFAULT_LGBM_PARAMS` y no
    en los de la libreria: la pregunta es si se puede mejorar lo que ya funciona, no
    explorar desde cero, y un espacio enorme con 25 trials no muestrea nada.

    `objective` y `metric` **no** se buscan. La eleccion de L1 sobre L2 es una
    decision documentada (D10: la mediana es lo que se quiere con cola derecha larga),
    no un hiperparametro: dejarla en el espacio permitiria que la busqueda la revierta
    por unas milesimas de MASE y cambie el significado de la salida.
    """
    return {
        "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 31, 255, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 120, log=True),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "lambda_l2": trial.suggest_float("lambda_l2", 1e-3, 20.0, log=True),
    }


def _objetivo_de(result: pd.DataFrame, peso: float) -> tuple[float, float, float]:
    """MASE medio, desvio entre origenes, y el objetivo penalizado."""
    from blindside.evaluate import metrics as M

    por_origen = M.metrics_by_origin(result)
    mase = por_origen["mase"].to_numpy(dtype="float64")
    media = float(np.mean(mase))
    desvio = float(np.std(mase, ddof=1)) if len(mase) > 1 else 0.0
    return media, desvio, media + peso * desvio


def buscar_lgbm(
    panel: pd.DataFrame,
    *,
    busqueda: Busqueda | None = None,
    target: str = S.DEMAND_LATENT,
) -> Resultado:
    """Corre la busqueda y devuelve el mejor conjunto con su contraste.

    Siempre evalua primero los parametros **actuales**, para que la mejora se mida
    contra algo y no contra el peor trial. Sin esa referencia, cualquier busqueda
    "encuentra una mejora" por construccion.
    """
    if not disponible():
        raise ImportError(
            "optuna no esta instalado. Esta en requirements.txt, pero la imagen de "
            "servicio lo deja afuera. Instalar con: pip install optuna==4.0.0"
        )
    import optuna

    from blindside.evaluate.backtest import run_backtest
    from blindside.models.gbdt import DEFAULT_LGBM_PARAMS, LightGBMForecaster

    b = busqueda or Busqueda()
    panel = _submuestrear(panel, n_series=b.n_series, seed=b.seed)
    fc = cfg.ForecastConfig(
        horizon=cfg.FORECAST.horizon,
        season_length=cfg.FORECAST.season_length,
        n_origins=b.n_origins,
        step=cfg.FORECAST.step,
        min_train_days=cfg.FORECAST.min_train_days,
    )
    log.info(
        "busqueda: %d trials sobre %d series y %d origenes",
        b.n_trials,
        panel[S.SERIES_ID].nunique(),
        b.n_origins,
    )

    def evaluar(params: dict[str, Any]) -> tuple[float, float, float]:
        modelo = LightGBMForecaster(params=params, n_estimators=b.n_estimators)
        result = run_backtest(panel, [modelo], target=target, forecast=fc)
        return _objetivo_de(result, b.peso_dispersion)

    # La referencia: los parametros que el proyecto usa hoy.
    base_mase, base_desvio, base_obj = evaluar({})
    log.info("base: MASE %.4f (desvio %.4f), objetivo %.4f", base_mase, base_desvio, base_obj)

    filas: list[dict[str, Any]] = [
        {
            "trial": -1,
            "objetivo": base_obj,
            "mase": base_mase,
            "desvio": base_desvio,
            **DEFAULT_LGBM_PARAMS,
        }
    ]

    def objetivo(trial: Any) -> float:
        params = espacio_lgbm(trial)
        mase, desvio, obj = evaluar(params)
        # Se registran los params COMPLETOS -- los buscados mas los que quedaron en su
        # default -- y no solo los buscados. Guardar solo los buscados deja nulos en la
        # tabla del reporte para las columnas que el espacio no toca, y un nulo ahi se
        # lee como "no estaba" cuando en realidad valia su default.
        filas.append(
            {
                "trial": trial.number,
                "objetivo": obj,
                "mase": mase,
                "desvio": desvio,
                **{**DEFAULT_LGBM_PARAMS, **params},
            }
        )
        return obj

    # TPESampler con semilla: la busqueda tiene que dar lo mismo al re-correrla.
    estudio = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=b.seed),
        study_name="lgbm_mase_origenes",
    )
    estudio.optimize(objetivo, n_trials=b.n_trials, show_progress_bar=False)

    historia = pd.DataFrame(filas).sort_values("objetivo").reset_index(drop=True)
    mejor = historia.iloc[0]
    mejores = (
        dict(DEFAULT_LGBM_PARAMS)
        if int(mejor["trial"]) == -1
        else {**DEFAULT_LGBM_PARAMS, **estudio.best_params}
    )

    return Resultado(
        mejores_params=mejores,
        mejor_objetivo=float(mejor["objetivo"]),
        mejor_mase=float(mejor["mase"]),
        mejor_desvio=float(mejor["desvio"]),
        base_objetivo=base_obj,
        base_mase=base_mase,
        base_desvio=base_desvio,
        busqueda=b,
        historia=historia,
    )


def _submuestrear(panel: pd.DataFrame, *, n_series: int, seed: int) -> pd.DataFrame:
    """Submuestra por serie con semilla fija. Devuelve el panel entero si ya es chico."""
    sids = np.sort(panel[S.SERIES_ID].unique())
    if len(sids) <= n_series:
        return panel
    rng = np.random.default_rng(seed)
    elegidas = set(rng.choice(sids, size=n_series, replace=False))
    return panel[panel[S.SERIES_ID].isin(elegidas)].copy()


def escribir_reporte(res: Resultado, ruta: Path, *, top: int = 10) -> Path:
    """Reporte en markdown, con la lectura derivada y no fija."""
    fila_base = (
        f"| Parametros actuales | {res.base_mase:.4f} "
        f"| {res.base_desvio:.4f} | {res.base_objetivo:.4f} |"
    )
    fila_mejor = (
        f"| Mejor encontrado | {res.mejor_mase:.4f} "
        f"| {res.mejor_desvio:.4f} | {res.mejor_objetivo:.4f} |"
    )
    lineas = [
        "# Busqueda de hiperparametros",
        "",
        "> Generado por `make tune`. No editar a mano.",
        "",
        "## Alcance, que esta reducido y se declara",
        "",
        f"- Trials: {res.busqueda.n_trials}",
        f"- Series: {res.busqueda.n_series} (la corrida oficial usa 3066)",
        f"- Origenes: {res.busqueda.n_origins} (la oficial usa {cfg.FORECAST.n_origins})",
        f"- Arboles por modelo: {res.busqueda.n_estimators}",
        f"- Objetivo: MASE medio + {res.busqueda.peso_dispersion} x desvio entre origenes",
        "",
        "Cada trial corre el **mismo** `run_backtest` que produce las metricas",
        "oficiales, con origenes moviles. No hay validacion cruzada aleatoria: sobre",
        "datos de panel produciria un numero mejor y falso.",
        "",
        "## Resultado",
        "",
        "| | MASE | Desvio entre origenes | Objetivo |",
        "|---|---|---|---|",
        fila_base,
        fila_mejor,
        "",
        f"Diferencia de MASE: **{res.mejora_pct:+.2f} %**.",
        "",
        _lectura(res),
        "",
        "## Mejores parametros",
        "",
        "```json",
        json.dumps(
            {k: v for k, v in res.mejores_params.items() if k not in {"num_threads", "verbosity"}},
            indent=2,
        ),
        "```",
        "",
        f"## Los {top} mejores trials",
        "",
        *_tabla_trials(res.historia.head(top)),
        "",
    ]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


def _tabla_trials(df: pd.DataFrame) -> list[str]:
    """Tabla markdown a mano.

    `DataFrame.to_markdown` exige `tabulate`, que no esta en `requirements.txt`; los
    otros generadores de reporte del proyecto tambien arman las filas a mano, asi que
    esto no agrega una dependencia por una tabla.
    """
    cols = [
        c
        for c in df.columns
        if c not in {"objective", "metric", "num_threads", "verbosity", "seed"}
    ]

    def fmt(v: Any) -> str:
        return f"{v:.5g}" if isinstance(v, int | float | np.floating) else str(v)

    return [
        "| " + " | ".join(cols) + " |",
        "|" + "|".join(["---"] * len(cols)) + "|",
        *("| " + " | ".join(fmt(r[c]) for c in cols) + " |" for _, r in df.iterrows()),
    ]


def _lectura(res: Resultado) -> str:
    """Deriva la conclusion de los numeros, para que el reporte no pueda mentir."""
    delta = res.base_mase - res.mejor_mase
    if delta <= 0:
        return (
            "**La busqueda no mejoro los parametros actuales.** Es un resultado valido y "
            "se reporta: dice que los valores elegidos a mano ya estaban en una zona "
            "razonable del espacio, y que el margen que queda en hiperparametros es "
            "menor que el que queda en features o en la capa de decision."
        )
    if not res.vale_la_pena:
        return (
            f"**La mejora ({delta:.4f} de MASE) es menor que la dispersion entre origenes "
            f"({res.base_desvio:.4f}), asi que no se adopta.** Adoptarla seria confundir una "
            "realizacion afortunada del azar sobre los origenes elegidos con una mejora "
            "real. El criterio esta declarado en el codigo (`Resultado.vale_la_pena`) y no "
            "se decide despues de ver el numero."
        )
    return (
        f"**La mejora ({delta:.4f} de MASE, {res.mejora_pct:+.2f} %) supera la dispersion "
        f"entre origenes ({res.base_desvio:.4f}).** Vale adoptarla, con la advertencia de que "
        "la busqueda corrio sobre una submuestra: antes de fijar estos valores conviene "
        "confirmarlos con una corrida completa."
    )


def main(argv: list[str] | None = None) -> int:
    """CLI: `python -m blindside.models.tuning --trials 25`."""
    import argparse

    from blindside.data import loaders

    p = argparse.ArgumentParser(description="Busqueda de hiperparametros sobre origenes moviles")
    p.add_argument("--trials", type=int, default=DEFAULT_N_TRIALS)
    p.add_argument("--n-series", type=int, default=400)
    p.add_argument("--n-origins", type=int, default=4)
    p.add_argument("--n-estimators", type=int, default=300)
    p.add_argument(
        "--peso-dispersion",
        type=float,
        default=0.5,
        help="cuanto pesa el desvio entre origenes en el objetivo; 0 = solo la media",
    )
    p.add_argument("--out", default="reports/tuning.md")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not disponible():
        log.error("optuna no esta instalado: pip install optuna==4.0.0")
        return 1

    res = buscar_lgbm(
        loaders.load_demand(),
        busqueda=Busqueda(
            n_trials=args.trials,
            n_series=args.n_series,
            n_origins=args.n_origins,
            n_estimators=args.n_estimators,
            peso_dispersion=args.peso_dispersion,
        ),
    )

    from pathlib import Path

    ruta = escribir_reporte(res, Path(args.out))
    res.a_json(Path(args.out).with_suffix(".json"))
    print(f"base  MASE {res.base_mase:.4f} (desvio {res.base_desvio:.4f})")
    print(f"mejor MASE {res.mejor_mase:.4f} (desvio {res.mejor_desvio:.4f})")
    print(f"diferencia {res.mejora_pct:+.2f} % | adoptar: {res.vale_la_pena}")
    print(f"reporte en {ruta}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
