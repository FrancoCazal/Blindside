"""Entrena y serializa el artefacto que consumen la API y el dashboard.

    python -m dfcore.models train --model lgbm_quantile --conformal

El artefacto se entrena con **todo** el panel disponible, no con un fold: los folds
son para medir, y lo que se sirve tiene que usar toda la historia. Es la unica
parte del proyecto donde eso es correcto, y por eso vive en su propio comando en
vez de mezclarse con el arnes de backtesting.

Se serializa en `artifacts/model.joblib`, que es la ruta que la API espera. El
formato es unico para todo el proyecto (ver `Forecaster.save`).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from dfcore import config as cfg
from dfcore.data import loaders
from dfcore.data import schema as S
from dfcore.models.base import Forecaster

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)


def build_model(name: str, *, quantiles: Sequence[float]) -> Forecaster:
    if name == "lgbm_quantile":
        from dfcore.models.gbdt import LightGBMQuantileForecaster

        return LightGBMQuantileForecaster(quantiles=quantiles)
    if name == "lgbm_global":
        from dfcore.models.gbdt import LightGBMForecaster

        return LightGBMForecaster()
    if name == "ridge":
        from dfcore.models.linear import RidgeForecaster

        return RidgeForecaster()
    if name == "seasonal_naive":
        from dfcore.models.baselines import SeasonalNaiveForecaster

        return SeasonalNaiveForecaster()
    raise SystemExit(f"modelo '{name}' desconocido")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="dfcore.models", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    tr = sub.add_parser("train", help="entrena y serializa el artefacto")
    tr.add_argument(
        "--model",
        default="lgbm_quantile",
        choices=["lgbm_quantile", "lgbm_global", "ridge", "seasonal_naive"],
    )
    tr.add_argument("--out", type=Path, default=cfg.ARTIFACTS / "model.joblib")
    tr.add_argument(
        "--conformal",
        action="store_true",
        help="envolver en ConformalForecaster para que emita intervalos calibrados",
    )
    tr.add_argument("--n-series", type=int, default=None, help="limitar series (pruebas)")
    tr.add_argument("--prefer-sample", action="store_true")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s · %(message)s")
    args = _parse_args(argv)

    panel = loaders.load_demand(prefer_sample=args.prefer_sample)
    if args.n_series:
        keep = pd.Index(sorted(panel[S.SERIES_ID].unique()))[: args.n_series]
        panel = panel[panel[S.SERIES_ID].isin(keep)].reset_index(drop=True)

    # El cuantil critico entra a la lista de cuantiles entrenados. Un q* entrenado
    # directamente es mejor que uno interpolado: la perdida cuantilica optimiza
    # ese cuantil y no otro.
    q_star = cfg.ECONOMICS.critical_fraction
    quantiles = tuple(sorted({*cfg.FORECAST.quantiles, q_star}))

    model = build_model(args.model, quantiles=quantiles)
    if args.conformal:
        from dfcore.decision.conformal import ConformalForecaster

        model = ConformalForecaster(
            model,
            alpha=1 - cfg.FORECAST.coverage,
            horizon=cfg.FORECAST.horizon,
            adaptive=True,
        )

    log.info(
        "entrenando '%s' con %d series hasta %s",
        model.name,
        panel[S.SERIES_ID].nunique(),
        panel[S.DATE].max().date(),
    )
    model.fit(panel, target=S.DEMAND_LATENT)
    path = model.save(args.out)

    print(f"\nartefacto: {path}", file=sys.stderr)
    print(f"modelo:    {model.name}", file=sys.stderr)
    print(f"entrenado hasta: {model.last_train_date.date()}", file=sys.stderr)
    print(f"cuantiles: {quantiles}  (q* = {q_star:.3f})", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
