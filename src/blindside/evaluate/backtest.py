"""Arnes de backtesting de origen movil.

Un solo lugar corre todos los modelos, y por eso las comparaciones son
comparables. La secuencia de cada fold es siempre la misma:

1. Cortar el panel en `history` (hasta el origen) y `truth` (los `H` dias que
   siguen).
2. Calcular el denominador de MASE **con `history`**, nunca con la serie
   completa.
3. Entrenar cada modelo con `history` y solo con `history`.
4. Armar el indice de futuro, que no lleva ninguna columna de target.
5. Predecir, unir con la verdad y volcar todo al contrato de backtest.

Los pasos 2 y 4 son los que hacen que la afirmacion de "sin fugas" sea una
propiedad del arnes y no una promesa. Un modelo nuevo hereda esas garantias sin
tener que acordarse de nada, porque no recibe los datos con los que podria
filtrar.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from blindside import config as cfg
from blindside.data import loaders
from blindside.data import schema as S
from blindside.evaluate import contracts as C
from blindside.models.base import Forecaster, quantile_col
from blindside.validation.splits import Fold, RollingOriginSplitter, naive_seasonal_scale

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)


def _future_index(
    panel: pd.DataFrame, fold: Fold, *, keep_known_future: bool = True
) -> pd.DataFrame:
    """Indice de futuro del fold: `series_id`, `dt`, `h` y lo conocido de antemano.

    Se construye desde el panel real y no por producto cartesiano de fechas para
    que respete los huecos: si una serie no tiene fila en un dia, no se le inventa
    un objetivo.

    Las columnas prohibidas se eliminan explicitamente aca. `Forecaster._check_ready`
    vuelve a verificarlo, o sea que hay dos barreras: una en el productor y otra
    en el consumidor.
    """
    window = panel[(panel[S.DATE] >= fold.test_start) & (panel[S.DATE] <= fold.test_end)]
    cols = [S.SERIES_ID, S.DATE, *S.HIERARCHY_COLS]
    if keep_known_future:
        cols += list(S.KNOWN_FUTURE_COLS)
    out = window[[c for c in cols if c in window.columns]].copy()
    out["h"] = (out[S.DATE] - fold.origin).dt.days.astype("int16")
    return out.reset_index(drop=True)


def run_fold(
    panel: pd.DataFrame,
    fold: Fold,
    models: Sequence[Forecaster],
    *,
    target: str = S.DEMAND_LATENT,
    season_length: int = cfg.FORECAST.season_length,
    quantiles: Sequence[float] = (),
) -> pd.DataFrame:
    """Corre un fold para todos los modelos y devuelve el resultado del contrato."""
    dates = panel[S.DATE]
    history = panel[fold.train_mask(dates)]
    truth = panel[fold.test_mask(dates)]
    if history.empty or truth.empty:
        raise ValueError(f"{fold!r} quedo sin train o sin test")

    # Denominador de MASE del fold. Se calcula una vez y viaja en el resultado.
    scale = naive_seasonal_scale(history, target=target, season_length=season_length)

    future = _future_index(panel, fold)
    # `Y_TRUE` se asigna antes del rename: si el target es la propia venta
    # observada (rama de ablacion de censura) las dos columnas son la misma y un
    # rename doble la colapsaria, dejando el resultado sin verdad de terreno.
    truth_slim = truth[
        [S.SERIES_ID, S.DATE, S.SALE_AMOUNT, S.IS_CENSORED, S.AVAILABLE_WEIGHT]
    ].copy()
    truth_slim[C.Y_TRUE] = truth[target].to_numpy()
    truth_slim = truth_slim.rename(columns={S.SALE_AMOUNT: C.Y_OBSERVED})

    frames = []
    for model in models:
        model.fit(history, target=target)
        preds = model.predict(future)

        block = future[[S.SERIES_ID, S.DATE, "h"]].copy()
        block[C.Y_PRED] = preds.to_numpy()
        if quantiles and model.supports_quantiles:
            qdf = model.predict_quantile(future, quantiles)
            # Los cuantiles se ordenan por fila para que no se cruzen: un q90 por
            # debajo del q50 no es un intervalo, es un bug.
            ordered = np.sort(qdf.to_numpy(dtype="float64"), axis=1)
            for i, q in enumerate(sorted(quantiles)):
                block[quantile_col(q)] = ordered[:, i]

        # El intervalo calibrado se guarda cuando el modelo lo produce. Sin esto
        # el parquet del backtest no tiene con que medir la cobertura empirica, y
        # la promesa de 90 % queda sin verificar: el proyecto se apoya en
        # cuantiles calibrados, asi que la cobertura **medida** es evidencia
        # central y no un extra.
        if hasattr(model, "predict_interval"):
            interval = model.predict_interval(future)
            block[C.PRED_LO] = np.asarray(interval["pred_lo"], dtype="float64")
            block[C.PRED_HI] = np.asarray(interval["pred_hi"], dtype="float64")

        block = block.merge(truth_slim, on=[S.SERIES_ID, S.DATE], how="inner")
        block[C.MODEL] = model.name
        block[C.ORIGIN] = fold.index
        block[C.ORIGIN_DATE] = fold.origin
        block[C.NAIVE_SCALE] = block[S.SERIES_ID].map(scale).astype("float64")
        frames.append(block)
        log.info("fold %d · %s · %d predicciones", fold.index, model.name, len(block))

    return pd.concat(frames, ignore_index=True)


def run_backtest(
    panel: pd.DataFrame,
    models: Sequence[Forecaster],
    *,
    target: str = S.DEMAND_LATENT,
    forecast: cfg.ForecastConfig = cfg.FORECAST,
    quantiles: Sequence[float] = (),
    splitter: RollingOriginSplitter | None = None,
) -> pd.DataFrame:
    """Backtest completo. Valida el contrato y el minimo de origenes."""
    panel = S.validate_panel(panel, required=(*S.PANEL_REQUIRED, target), allow_gaps=True)
    splitter = splitter or RollingOriginSplitter(
        horizon=forecast.horizon,
        n_origins=forecast.n_origins,
        step=forecast.step,
        min_train_days=forecast.min_train_days,
    )
    folds = splitter.folds(panel)
    log.info(
        "backtest: %d modelos x %d origenes, horizonte %d, target '%s'",
        len(models),
        len(folds),
        forecast.horizon,
        target,
    )

    frames = [
        run_fold(
            panel,
            fold,
            models,
            target=target,
            season_length=forecast.season_length,
            quantiles=quantiles,
        )
        for fold in folds
    ]
    result = pd.concat(frames, ignore_index=True)
    result = C.validate_result(
        result,
        quantiles=quantiles if any(quantile_col(q) in result.columns for q in quantiles) else (),
    )
    C.coverage_of_origins(result, required=forecast.n_origins)
    return result


# --------------------------------------------------------------------------
# Ablacion de censura · el resultado central del proyecto
# --------------------------------------------------------------------------
def run_censoring_ablation(
    panel: pd.DataFrame,
    model_factory,
    *,
    forecast: cfg.ForecastConfig = cfg.FORECAST,
    splitter: RollingOriginSplitter | None = None,
) -> pd.DataFrame:
    """Compara el **mismo modelo** entrenado sobre venta observada y sobre latente.

    Es la comparacion pareada que aisla el efecto de la recuperacion de censura,
    y es el resultado central del proyecto. La logica de por que tiene que ser
    pareada:

    El sesgo absoluto de un modelo mezcla el efecto de la censura con el de su
    funcion de perdida — una perdida L1 estima la mediana y en una distribucion
    con cola derecha eso ya produce sesgo negativo por si solo. Entrenando dos
    veces el mismo modelo y cambiando **unicamente el target**, el efecto de la
    perdida es identico en las dos ramas y se cancela en la diferencia. Lo que
    queda es atribuible a la censura.

    Las dos ramas se evaluan contra la **misma** verdad de terreno: la venta
    observada de los dias sin ninguna hora de quiebre. Es el unico terreno donde
    la demanda real se conoce, asi que es el unico donde la comparacion es
    legitima. Evaluar la rama latente contra demanda latente y la rama observada
    contra venta observada compararia cosas distintas.

    `model_factory` es un invocable sin argumentos que devuelve un modelo nuevo:
    hace falta una instancia limpia por rama para que no quede estado compartido.
    """
    from blindside.decision.censoring import clean_day_bias, recensored_bias
    from blindside.evaluate import metrics as M

    runs = {
        target: run_backtest(
            panel, [model_factory()], target=target, forecast=forecast, splitter=splitter
        )
        for target in (S.SALE_AMOUNT, S.DEMAND_LATENT)
    }

    # Escala **comun** de MASE para las dos ramas. Cada rama calcula su propio
    # denominador a partir de su propio target, y el de la demanda latente es
    # mayor porque la serie corregida varia mas. Comparar los MASE crudos entre
    # ramas mediria esa diferencia de denominador y no la del modelo, lo que
    # regalaria una mejora de ~30 % que no existe. Se toma el denominador de la
    # rama de venta observada, que es la escala de la verdad de terreno comun.
    ref = runs[S.SALE_AMOUNT]
    common_scale = ref.set_index([C.ORIGIN, S.SERIES_ID])[C.NAIVE_SCALE]
    common_scale = common_scale[~common_scale.index.duplicated()]

    rows = []
    for target, result in runs.items():
        clean = ~result[S.IS_CENSORED].to_numpy(dtype=bool)
        # Verdad comun a las dos ramas: la venta observada de los dias limpios.
        sub = result.loc[clean]
        y_clean = sub[C.Y_OBSERVED].to_numpy(dtype="float64")
        p_clean = sub[C.Y_PRED].to_numpy(dtype="float64")
        scale_clean = (
            pd.MultiIndex.from_arrays([sub[C.ORIGIN], sub[S.SERIES_ID]])
            .map(common_scale)
            .to_numpy(dtype="float64")
        )
        rows.append(
            {
                "trained_on": target,
                "model": result[C.MODEL].iloc[0],
                "recensored_bias": recensored_bias(
                    result[C.Y_OBSERVED],
                    result[C.Y_PRED],
                    available_weight=result[S.AVAILABLE_WEIGHT],
                ),
                "clean_day_bias": clean_day_bias(
                    result[C.Y_OBSERVED], result[C.Y_PRED], is_censored=result[S.IS_CENSORED]
                ),
                "mase_clean_days": M.mase(y_clean, p_clean, scale_clean),
                "wape_clean_days": M.wape(y_clean, p_clean),
                "mean_pred": float(result[C.Y_PRED].mean()),
                "n_clean_days": int(clean.sum()),
            }
        )
    out = pd.DataFrame(rows)
    observed_bias = float(out.loc[out["trained_on"] == S.SALE_AMOUNT, "recensored_bias"].iloc[0])
    latent_bias = float(out.loc[out["trained_on"] == S.DEMAND_LATENT, "recensored_bias"].iloc[0])
    out.attrs["bias_reduction_pp"] = 100 * (abs(observed_bias) - abs(latent_bias))
    log.info(
        "ablacion de censura: sesgo %.2f %% entrenando sobre venta observada, "
        "%.2f %% sobre demanda latente (reduccion de %.2f puntos)",
        100 * observed_bias,
        100 * latent_bias,
        out.attrs["bias_reduction_pp"],
    )
    return out


# --------------------------------------------------------------------------
# Reporte
# --------------------------------------------------------------------------
def write_report(
    result: pd.DataFrame,
    *,
    out_path: Path,
    target: str,
    forecast: cfg.ForecastConfig = cfg.FORECAST,
    rotation: pd.Series | None = None,
) -> Path:
    """Escribe `reports/metrics.md`. Todo con dispersion entre origenes."""
    from blindside.evaluate import metrics as M
    from blindside.models.baselines import REFERENCE_BASELINE

    summary = M.summarize(result)
    by_h = M.metrics_by_horizon(result)
    cens = M.censoring_metrics(result)

    lines: list[str] = [
        "# Metricas de backtest",
        "",
        "> Generado por `make backtest`. No editar a mano.",
        "",
        "## Configuracion",
        "",
        f"- Target evaluado: `{target}`",
        f"- Horizonte: {forecast.horizon} dias",
        f"- Estacionalidad (denominador de MASE): {forecast.season_length} dias",
        f"- Origenes de backtest: {C.n_origins(result)}",
        f"- Series: {result[S.SERIES_ID].nunique()}",
        f"- Predicciones evaluadas: {len(result):,}",
        "",
        "El denominador de MASE se calcula con el **train de cada origen**, nunca",
        "con la serie completa. Las metricas van con su dispersion entre origenes:",
        "un promedio bueno puede esconder un origen catastrofico.",
        "",
        "## Resumen por modelo · MASE",
        "",
    ]

    try:
        improvement = M.improvement_vs_baseline(summary, baseline=REFERENCE_BASELINE, metric="mase")
        lines += [
            "| Modelo | MASE medio | Desvio | Peor origen | Mejora vs naive estacional | >= 20 % |",
            "|---|---|---|---|---|---|",
        ]
        for _, r in improvement.iterrows():
            flag = "si" if r["meets_target_20pct"] else "no"
            lines.append(
                f"| `{r['model']}` | {r['mean']:.4f} | {r['std']:.4f} | "
                f"{r['worst_origin']:.4f} | {r['improvement_pct']:+.1f} % | {flag} |"
            )
    except KeyError:
        lines.append(f"_No corrio el baseline de referencia `{REFERENCE_BASELINE}`._")
    lines.append("")

    lines += [
        "## Todas las metricas",
        "",
        "| Modelo | Metrica | Media | Desvio | Peor | Mejor |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in summary.sort_values(["metric", "mean"]).iterrows():
        lines.append(
            f"| `{r['model']}` | {r['metric']} | {r['mean']:.4f} | {r['std']:.4f} | "
            f"{r['worst_origin']:.4f} | {r['best_origin']:.4f} |"
        )
    lines.append("")

    lines += [
        "## Degradacion por horizonte",
        "",
        "Responde cuanto dura el modelo antes de necesitar reentrenamiento. El error",
        "debe **crecer** con el horizonte; si baja, hay un desalineamiento de indices.",
        "",
        "| Modelo | h | MASE | WAPE |",
        "|---|---|---|---|",
    ]
    for _, r in by_h.iterrows():
        lines.append(
            f"| `{r[C.MODEL]}` | {int(r[C.HORIZON_STEP])} | {r['mase']:.4f} | {r['wape']:.4f} |"
        )
    lines.append("")

    lines += [
        "## Sesgo de censura",
        "",
        "**Sesgo re-censurado** es la metrica de referencia: se le vuelve a aplicar a la",
        "prediccion de demanda latente el patron real de quiebres y se compara contra la",
        "venta registrada. Un cero significa que el modelo recupero la demanda latente.",
        "Un valor negativo es el efecto spiral-down medido. Referencia publicada sobre",
        "este mismo dataset (CADRE): -8,1 % sin correccion, -1,3 % con correccion.",
        "",
        "**Sesgo en dias limpios** es un diagnostico, no un resultado. Los dias sin quiebre",
        "no son una muestra aleatoria: el stock se agota cuando la gente compra mucho, asi",
        "que ese subconjunto tiende a dias de demanda baja y un modelo correcto sobrepredice",
        "ahi sin estar equivocado.",
        "",
        "| Modelo | Sesgo re-censurado | Sesgo dias limpios "
        "| MASE dias limpios | MASE dias censurados |",
        "|---|---|---|---|---|",
    ]
    for _, r in cens.iterrows():
        lines.append(
            f"| `{r['model']}` | {100 * r['recensored_bias']:+.2f} % | "
            f"{100 * r['clean_day_bias']:+.2f} % | "
            f"{r['mase_clean']:.4f} | {r['mase_censored']:.4f} |"
        )
    lines.append("")

    if rotation is not None:
        band = M.metrics_by_group(result, rotation, name="rotation_band")
        lines += [
            "## Por banda de rotacion",
            "",
            "Que el modelo complejo no le gane al ingenuo en baja rotacion es un",
            "resultado esperado y publicado, no un fracaso. Se reporta igual.",
            "",
            "| Modelo | Banda | MASE | WAPE | n |",
            "|---|---|---|---|---|",
        ]
        for _, r in band.iterrows():
            lines.append(
                f"| `{r[C.MODEL]}` | {r['rotation_band']} | {r['mase']:.4f} | "
                f"{r['wape']:.4f} | {int(r['n']):,} |"
            )
        lines.append("")

    cov = M.coverage_report(result, nominal=forecast.coverage)
    if not cov.empty:
        lines += [
            "## Calibracion de intervalos",
            "",
            "| Modelo | Nominal | Empirica | Gap | Ancho medio | Cumple |",
            "|---|---|---|---|---|---|",
        ]
        for _, r in cov.iterrows():
            flag = "si" if r["meets_nominal"] else "no"
            lines.append(
                f"| `{r['model']}` | {r['coverage_nominal']:.0%} | "
                f"{r['coverage_empirical']:.1%} | {r['gap']:+.1%} | "
                f"{r['interval_width']:.3f} | {flag} |"
            )
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("reporte escrito en %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _model_factories() -> dict[str, object]:
    """Registro nombre -> fabrica. Las importaciones son perezosas a proposito.

    Los modelos pesados se importan solo cuando se piden, asi que el arnes de
    baselines sigue corriendo en un entorno donde LightGBM o torch no esten
    instalados. El plan lo pide explicitamente para Prophet y pmdarima
    (seccion 17: "aislados en modulo opcional, no bloquean el camino critico"),
    y la misma disciplina se aplica al resto.
    """

    def lgbm():
        from blindside.models.gbdt import LightGBMForecaster

        return LightGBMForecaster()

    def lgbm_quantile():
        from blindside.models.gbdt import LightGBMQuantileForecaster

        return LightGBMQuantileForecaster()

    def xgb():
        from blindside.models.gbdt import XGBoostForecaster

        return XGBoostForecaster()

    def ridge():
        from blindside.models.linear import RidgeForecaster

        return RidgeForecaster()

    def lasso():
        from blindside.models.linear import LassoForecaster

        return LassoForecaster()

    def elasticnet():
        from blindside.models.linear import ElasticNetForecaster

        return ElasticNetForecaster()

    def conformal_lgbm():
        """El modelo que la API sirve, medido con el mismo arnes que el resto.

        Es el unico del registro que produce intervalos, asi que es el que llena
        la seccion de cobertura del reporte. El cuantil critico entra a la lista
        de cuantiles entrenados igual que en `blindside.models train`, para que lo
        que se mide sea el artefacto que se sirve y no un primo cercano.
        """
        from blindside.decision.conformal import ConformalForecaster
        from blindside.models.gbdt import LightGBMQuantileForecaster

        quantiles = tuple(sorted({*cfg.FORECAST.quantiles, cfg.ECONOMICS.critical_fraction}))
        return ConformalForecaster(
            LightGBMQuantileForecaster(quantiles=quantiles),
            alpha=1 - cfg.FORECAST.coverage,
            horizon=cfg.FORECAST.horizon,
            adaptive=True,
        )

    def conformal_lgbm_point():
        """Variante barata: intervalo conformal sobre el LightGBM puntual.

        Entrena un modelo por fold en vez de uno por cuantil, asi que sirve para
        medir cobertura cuando el presupuesto de computo no alcanza para el
        cuantilico. El intervalo sale de los residuos de calibracion en los dos
        casos, no de los cuantiles del modelo de abajo.
        """
        from blindside.decision.conformal import ConformalForecaster
        from blindside.models.gbdt import LightGBMForecaster

        return ConformalForecaster(
            LightGBMForecaster(),
            alpha=1 - cfg.FORECAST.coverage,
            horizon=cfg.FORECAST.horizon,
            adaptive=True,
        )

    return {
        "lgbm_global": lgbm,
        "lgbm_quantile": lgbm_quantile,
        "conformal_lgbm": conformal_lgbm,
        "conformal_lgbm_point": conformal_lgbm_point,
        "xgb_global": xgb,
        "ridge": ridge,
        "lasso": lasso,
        "elasticnet": elasticnet,
    }


def _load_models(names: Sequence[str] | None, season_length: int) -> list[Forecaster]:
    """Instancia los modelos pedidos. Sin `names`, corre los cinco baselines."""
    from blindside.models.baselines import BASELINE_REGISTRY, make_baselines

    if not names:
        return make_baselines(season_length=season_length)

    baselines = {m.name: m for m in make_baselines(season_length=season_length)}
    factories = _model_factories()
    known = set(baselines) | set(factories)

    models: list[Forecaster] = []
    for name in names:
        if name in baselines:
            models.append(baselines[name])
            continue
        if name not in factories:
            raise SystemExit(f"modelo '{name}' desconocido. Disponibles: {sorted(known)}")
        try:
            models.append(factories[name]())
        except ImportError as exc:
            log.error("no se pudo cargar '%s': %s", name, exc)
            raise SystemExit(1) from exc

    # El baseline de referencia entra siempre: sin el no se puede calcular la
    # mejora porcentual, que es como esta expresado el objetivo del proyecto.
    from blindside.models.baselines import REFERENCE_BASELINE

    if REFERENCE_BASELINE not in {m.name for m in models}:
        log.info("agregando '%s' como referencia de MASE", REFERENCE_BASELINE)
        models.insert(0, baselines[REFERENCE_BASELINE])
    assert set(BASELINE_REGISTRY) <= known
    return models


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backtest de origen movil.")
    p.add_argument("--out", type=Path, default=cfg.REPORTS / "metrics.md")
    p.add_argument(
        "--target",
        default=S.DEMAND_LATENT,
        choices=[S.DEMAND_LATENT, S.SALE_AMOUNT],
        help="demanda latente recuperada (por defecto) o venta observada cruda",
    )
    p.add_argument("--models", nargs="*", default=None, help="subconjunto de modelos")
    p.add_argument("--horizon", type=int, default=cfg.FORECAST.horizon)
    p.add_argument("--n-origins", type=int, default=cfg.FORECAST.n_origins)
    p.add_argument("--step", type=int, default=cfg.FORECAST.step)
    p.add_argument("--min-train-days", type=int, default=cfg.FORECAST.min_train_days)
    p.add_argument("--n-series", type=int, default=None, help="limitar series (pruebas)")
    p.add_argument("--save-result", type=Path, default=None, help="parquet con el detalle")
    p.add_argument(
        "--prefer-sample",
        action="store_true",
        help=(
            "usar data/sample/ aunque exista el subconjunto grande. Lo usa la CI, "
            "para no depender de un fallback implicito"
        ),
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s · %(message)s")
    args = _parse_args(argv)

    load = loaders.load_demand if args.target == S.DEMAND_LATENT else loaders.load_panel
    panel = load(prefer_sample=args.prefer_sample)

    if args.n_series:
        keep = pd.Index(sorted(panel[S.SERIES_ID].unique()))[: args.n_series]
        panel = panel[panel[S.SERIES_ID].isin(keep)].reset_index(drop=True)

    forecast = cfg.ForecastConfig(
        horizon=args.horizon,
        season_length=cfg.FORECAST.season_length,
        n_origins=args.n_origins,
        step=args.step,
        min_train_days=args.min_train_days,
        coverage=cfg.FORECAST.coverage,
        quantiles=cfg.FORECAST.quantiles,
    )
    models = _load_models(args.models, forecast.season_length)
    if not models:
        log.error("no hay modelos para correr")
        return 1

    result = run_backtest(panel, models, target=args.target, forecast=forecast)

    from blindside.validation.splits import rotation_bands

    splitter = RollingOriginSplitter(
        horizon=forecast.horizon,
        n_origins=forecast.n_origins,
        step=forecast.step,
        min_train_days=forecast.min_train_days,
    )
    first_origin = splitter.origins(panel[S.DATE])[0]
    bands = rotation_bands(panel[panel[S.DATE] <= first_origin], target=args.target)

    write_report(result, out_path=args.out, target=args.target, forecast=forecast, rotation=bands)

    if args.save_result:
        args.save_result.parent.mkdir(parents=True, exist_ok=True)
        result.to_parquet(args.save_result, index=False, compression="zstd")

    # El cierre del dia 1 del cronograma es "un MASE de baseline impreso".
    from blindside.evaluate import metrics as M
    from blindside.models.baselines import REFERENCE_BASELINE

    summary = M.summarize(result)
    mase_rows = summary[summary["metric"] == "mase"].sort_values("mean")
    print("\n=== MASE por modelo (media +- desvio entre origenes) ===", file=sys.stderr)
    for _, r in mase_rows.iterrows():
        marker = "  <- denominador de MASE" if r["model"] == REFERENCE_BASELINE else ""
        print(
            f"  {r['model']:<26} {r['mean']:.4f} +- {r['std']:.4f}"
            f"   (peor origen {r['worst_origin']:.4f}){marker}",
            file=sys.stderr,
        )
    print(f"\nReporte completo: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["run_backtest", "run_fold", "write_report"]
