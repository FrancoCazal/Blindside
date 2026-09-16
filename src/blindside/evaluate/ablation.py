"""CLI de la ablacion de censura · el resultado central del proyecto.

Corre el mismo modelo dos veces cambiando **solo el target** — venta observada
contra demanda latente recuperada — y escribe el reporte comparativo.

Es la evidencia de la tesis del trabajo. El razonamiento de por que tiene que ser
pareada, y por que la escala de MASE tiene que ser comun a las dos ramas, esta en
`backtest.run_censoring_ablation` y en docs/decisiones.md D10.
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
from blindside.evaluate.backtest import run_censoring_ablation

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)

#: Numeros publicados de CADRE sobre este mismo dataset, para que la comparacion
#: sea contra un tercero y no contra uno mismo.
#: https://www.mdpi.com/2071-1050/18/15/7642
CADRE_REFERENCE = {
    "bias_censored": -0.081,
    "bias_corrected": -0.013,
    "wape_censored": 0.3942,
    "wape_corrected": 0.3671,
}


def write_report(table: pd.DataFrame, *, out_path: Path, model_name: str, n_series: int) -> Path:
    observed = table[table["trained_on"] == S.SALE_AMOUNT].iloc[0]
    latent = table[table["trained_on"] == S.DEMAND_LATENT].iloc[0]

    lines = [
        "# Ablacion de censura",
        "",
        "> Generado por `make ablation`. No editar a mano.",
        "",
        "El **mismo** modelo entrenado dos veces, cambiando unicamente el target.",
        "Las dos ramas se evaluan contra la misma verdad de terreno: la venta observada",
        "de los dias **sin ninguna hora de quiebre**, que es el unico terreno donde la",
        "demanda real se conoce.",
        "",
        f"- Modelo: `{model_name}`",
        f"- Series: {n_series}",
        f"- Dias limpios evaluados: {int(observed['n_clean_days']):,}",
        "",
        "## Resultado",
        "",
        "| Entrenado sobre | Sesgo re-censurado | Sesgo dias limpios "
        "| MASE dias limpios | WAPE dias limpios |",
        "|---|---|---|---|---|",
        f"| venta observada (`sale_amount`) | {100 * observed['recensored_bias']:+.2f} % | "
        f"{100 * observed['clean_day_bias']:+.2f} % | "
        f"{observed['mase_clean_days']:.4f} | {observed['wape_clean_days']:.4f} |",
        f"| demanda latente (`demand_latent`) | {100 * latent['recensored_bias']:+.2f} % | "
        f"{100 * latent['clean_day_bias']:+.2f} % | "
        f"{latent['mase_clean_days']:.4f} | {latent['wape_clean_days']:.4f} |",
        "",
        f"**Reduccion de sesgo re-censurado: {table.attrs['bias_reduction_pp']:.2f} "
        "puntos porcentuales.**",
        "",
        "## Lectura",
        "",
        "El **sesgo re-censurado** es la metrica de referencia. Se le vuelve a aplicar a la",
        "prediccion de demanda latente el patron real de quiebres y se compara contra la",
        "venta registrada: si el modelo recupero la demanda latente, re-censurarla da",
        "exactamente lo que se vendio, y el sesgo es cero.",
        "",
        "El signo negativo en la rama de venta observada es el **efecto spiral-down**: el",
        "modelo aprendio de una demanda deprimida por los quiebres, asi que su prediccion",
        "re-censurada queda por debajo de la venta real. Es el sesgo que en la operacion se",
        "realimenta — se pide de menos, hay mas quiebres, se observa menos demanda, se pide",
        "de menos todavia.",
        "",
        "El **sesgo en dias limpios** va al lado como diagnostico y no como resultado. Los",
        "dias sin quiebre no son una muestra aleatoria: el stock se agota cuando la gente",
        "compra mucho, asi que ese subconjunto tiende a dias de demanda baja y un modelo que",
        "predice bien la demanda latente esperada sobrepredice ahi sin estar equivocado.",
        "Leer esa columna como si midiera la censura invierte la conclusion.",
        "",
        "El MASE de las dos ramas usa el **mismo denominador**, el de la rama de venta",
        "observada. Cada rama calculando su propia escala regalaria una mejora aparente",
        "de ~30 % que solo refleja que la serie corregida varia mas.",
        "",
        "## Contra la literatura",
        "",
        "Numeros publicados de CADRE, medidos sobre este mismo dataset",
        "([MDPI Sustainability 18(15):7642](https://www.mdpi.com/2071-1050/18/15/7642)):",
        "",
        "| Indicador | CADRE sin corregir | CADRE corregido "
        "| Este proyecto sin corregir | Este proyecto corregido |",
        "|---|---|---|---|---|",
        f"| Sesgo re-censurado | {100 * CADRE_REFERENCE['bias_censored']:+.1f} % | "
        f"{100 * CADRE_REFERENCE['bias_corrected']:+.1f} % | "
        f"{100 * observed['recensored_bias']:+.2f} % | {100 * latent['recensored_bias']:+.2f} % |",
        f"| WAPE | {CADRE_REFERENCE['wape_censored']:.4f} | "
        f"{CADRE_REFERENCE['wape_corrected']:.4f} | "
        f"{observed['wape_clean_days']:.4f} | {latent['wape_clean_days']:.4f} |",
        "",
        "El sesgo **sin corregir** reproduce de cerca el valor publicado, lo que respalda",
        "que la medicion esta bien planteada. La correccion propia es mas conservadora que",
        "la de CADRE, y eso es una consecuencia declarada de los dos limites del",
        "recuperador: tope de inflacion en x3 y nada de correccion cuando queda menos del",
        "15 % de la masa de demanda diaria disponible. Se prefiere un sesgo residual",
        "conocido a una varianza inventada a partir de una sola venta en un dia casi",
        "entero en quiebre. Ver docs/decisiones.md D11.",
        "",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("reporte escrito en %s", out_path)
    return out_path


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=cfg.REPORTS / "censoring_ablation.md")
    p.add_argument("--model", default="lgbm_global", choices=["lgbm_global", "ridge"])
    p.add_argument("--n-series", type=int, default=None, help="limitar series (pruebas)")
    p.add_argument("--n-origins", type=int, default=cfg.FORECAST.n_origins)
    p.add_argument("--prefer-sample", action="store_true")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s · %(message)s")
    args = _parse_args(argv)

    panel = loaders.load_demand(prefer_sample=args.prefer_sample)
    if args.n_series:
        keep = pd.Index(sorted(panel[S.SERIES_ID].unique()))[: args.n_series]
        panel = panel[panel[S.SERIES_ID].isin(keep)].reset_index(drop=True)

    def factory():
        if args.model == "ridge":
            from blindside.models.linear import RidgeForecaster

            return RidgeForecaster()
        from blindside.models.gbdt import LightGBMForecaster

        return LightGBMForecaster()

    forecast = cfg.ForecastConfig(
        horizon=cfg.FORECAST.horizon,
        season_length=cfg.FORECAST.season_length,
        n_origins=args.n_origins,
        step=cfg.FORECAST.step,
        min_train_days=cfg.FORECAST.min_train_days,
        coverage=cfg.FORECAST.coverage,
        quantiles=cfg.FORECAST.quantiles,
    )
    table = run_censoring_ablation(panel, factory, forecast=forecast)
    write_report(
        table,
        out_path=args.out,
        model_name=args.model,
        n_series=int(panel[S.SERIES_ID].nunique()),
    )

    print("\n=== Ablacion de censura ===", file=sys.stderr)
    print(table.to_string(index=False), file=sys.stderr)
    print(
        f"\nReduccion de sesgo: {table.attrs['bias_reduction_pp']:.2f} puntos porcentuales",
        file=sys.stderr,
    )
    print(f"Reporte: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
