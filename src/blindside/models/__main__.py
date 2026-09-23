"""Entrena y serializa los artefactos que consumen la API y el dashboard.

    python -m blindside.models train --model lgbm_quantile --conformal

El artefacto se entrena con **todo** el panel disponible, no con un fold: los folds
son para medir, y lo que se sirve tiene que usar toda la historia. Es la unica
parte del proyecto donde eso es correcto, y por eso vive en su propio comando en
vez de mezclarse con el arnes de backtesting.

Se serializan **dos** artefactos, uno por base de calculo (`--basis both`, que es
el default):

* `artifacts/model.joblib` — entrenado sobre demanda latente recuperada.
* `artifacts/model_observed.joblib` — entrenado sobre la venta observada.

Los dos con la misma arquitectura y los mismos hiperparametros, porque la
comparacion entre bases tiene que ser pareada: si cambia el modelo ademas del
target, la diferencia deja de ser atribuible a la censura (docs/decisiones.md
D10). El segundo existe para que el toggle de la interfaz pueda cambiar las
cantidades sugeridas y no solo la serie dibujada; sirviendo un unico artefacto el
control mas importante de la app no tendria efecto sobre la decision.

El formato es unico para todo el proyecto (ver `Forecaster.save`) y los nombres de
archivo salen de `config.MODEL_FILES`.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from blindside import config as cfg
from blindside.data import loaders
from blindside.data import schema as S
from blindside.models.base import TARGET_BY_BASIS, Forecaster

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)


def build_model(name: str, *, quantiles: Sequence[float]) -> Forecaster:
    if name == "lgbm_quantile":
        from blindside.models.gbdt import LightGBMQuantileForecaster

        return LightGBMQuantileForecaster(quantiles=quantiles)
    if name == "lgbm_global":
        from blindside.models.gbdt import LightGBMForecaster

        return LightGBMForecaster()
    if name == "ridge":
        from blindside.models.linear import RidgeForecaster

        return RidgeForecaster()
    if name == "seasonal_naive":
        from blindside.models.baselines import SeasonalNaiveForecaster

        return SeasonalNaiveForecaster()
    raise SystemExit(f"modelo '{name}' desconocido")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="blindside.models", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    tr = sub.add_parser("train", help="entrena y serializa los artefactos")
    tr.add_argument(
        "--model",
        default="lgbm_quantile",
        choices=["lgbm_quantile", "lgbm_global", "ridge", "seasonal_naive"],
    )
    tr.add_argument(
        "--basis",
        default="both",
        choices=["both", *TARGET_BY_BASIS],
        help=(
            "base de calculo del target. 'both' serializa los dos artefactos, que "
            "es lo que la API necesita para que el toggle de censura cambie la "
            "cantidad sugerida"
        ),
    )
    tr.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "ruta del artefacto. Solo valido con --basis observed|recovered; con "
            "'both' los nombres salen de config.MODEL_FILES"
        ),
    )
    tr.add_argument(
        "--conformal",
        action="store_true",
        help="envolver en ConformalForecaster para que emita intervalos calibrados",
    )
    tr.add_argument("--n-series", type=int, default=None, help="limitar series (pruebas)")
    tr.add_argument("--prefer-sample", action="store_true")
    return p.parse_args(argv)


def train_basis(
    panel: pd.DataFrame,
    *,
    basis: cfg.Basis,
    model_name: str,
    quantiles: Sequence[float],
    conformal: bool,
    out: Path | None = None,
) -> tuple[Forecaster, Path]:
    """Entrena una base y serializa su artefacto. Devuelve el modelo y la ruta."""
    target = TARGET_BY_BASIS[basis]
    model = build_model(model_name, quantiles=quantiles)
    if conformal:
        from blindside.decision.conformal import ConformalForecaster, CQRForecaster

        # CQR cuando el base sabe dar cuantiles, que es el caso del artefacto que
        # se sirve. Parte de los cuantiles estimados en vez de pegarle una
        # semiamplitud constante a la prediccion puntual, y por eso su ancho es
        # adaptativo por dia y no solo por serie. Medido sobre un fold real:
        # cobertura 0,886 con ancho 4,0 veces el MAE, contra 0,987 y 7,8 del
        # conformal de residuos adaptativo. Ver docs/decisiones.md D21.
        if getattr(model, "supports_quantiles", False):
            model = CQRForecaster(
                model,
                alpha=1 - cfg.FORECAST.coverage,
                horizon=cfg.FORECAST.horizon,
            )
        else:
            model = ConformalForecaster(
                model,
                alpha=1 - cfg.FORECAST.coverage,
                horizon=cfg.FORECAST.horizon,
                adaptive=True,
            )

    log.info(
        "entrenando '%s' sobre base '%s' (target %s) con %d series hasta %s",
        model.name,
        basis,
        target,
        panel[S.SERIES_ID].nunique(),
        panel[S.DATE].max().date(),
    )
    model.fit(panel, target=target)
    return model, model.save(out or cfg.model_path(basis))


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s · %(message)s")
    args = _parse_args(argv)

    bases: list[cfg.Basis] = ["recovered", "observed"] if args.basis == "both" else [args.basis]
    if args.out is not None and len(bases) > 1:
        raise SystemExit("--out no aplica con --basis both: son dos archivos distintos")

    panel = loaders.load_demand(prefer_sample=args.prefer_sample)
    if args.n_series:
        keep = pd.Index(sorted(panel[S.SERIES_ID].unique()))[: args.n_series]
        panel = panel[panel[S.SERIES_ID].isin(keep)].reset_index(drop=True)

    # El cuantil critico entra a la lista de cuantiles entrenados. Un q* entrenado
    # directamente es mejor que uno interpolado: la perdida cuantilica optimiza
    # ese cuantil y no otro.
    q_star = cfg.ECONOMICS.critical_fraction
    quantiles = tuple(sorted({*cfg.FORECAST.quantiles, q_star}))

    for basis in bases:
        model, path = train_basis(
            panel,
            basis=basis,
            model_name=args.model,
            quantiles=quantiles,
            conformal=args.conformal,
            out=args.out,
        )
        print(f"\nbase:      {basis}  (target {TARGET_BY_BASIS[basis]})", file=sys.stderr)
        print(f"artefacto: {path}", file=sys.stderr)
        print(f"modelo:    {model.name}", file=sys.stderr)
        print(f"entrenado hasta: {model.last_train_date.date()}", file=sys.stderr)
        print(f"cuantiles: {quantiles}  (q* = {q_star:.3f})", file=sys.stderr)

    if len(bases) == 1:
        print(
            "\nOJO: se serializo una sola base. La API necesita las dos para que el "
            "toggle de censura cambie la cantidad sugerida; la que falte responde 503.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
