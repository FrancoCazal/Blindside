"""FastAPI · superficie de servicio.

Implementa el contrato de `api/schemas.py`, que se congelo antes que este archivo
justamente para que el frontend pudiera arrancar contra datos simulados sin
esperar al backend (seccion 13 del plan).

Estado de seguridad, declarado y no escondido
---------------------------------------------
**Esta API no tiene autenticacion.** Es deliberado para el alcance del proyecto —
es un prototipo de demostracion que corre en `127.0.0.1` y detras de Docker
Compose — pero hay que decirlo en vez de dejarlo implicito:

* No hay autenticacion ni autorizacion. Cualquiera que alcance el puerto puede
  consultar todos los pronosticos y todas las cantidades de reposicion.
* No hay limite de tasa. Un `/forecast` con 500 series es una consulta costosa.
* El binding por defecto es local. **No exponer a una red publica sin agregar
  antes autenticacion**, porque las cantidades a reponer y los pronosticos por
  tienda son informacion comercial sensible.

Para la Fase 2 multi-tenant esto se vuelve bloqueante: hace falta autenticacion
por tenant y aislamiento de datos antes de que sirva a mas de una organizacion.
Esta en el roadmap de `docs/decisiones.md`.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd
from api import schemas as sc
from fastapi import FastAPI, HTTPException, status

from blindside import __version__
from blindside import config as cfg
from blindside.data import loaders
from blindside.data import schema as S

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

log = logging.getLogger(__name__)

#: Estado del proceso. Se carga una vez al arrancar y no por request: releer el
#: panel en cada consulta convertiria una API en un lector de parquet.
STATE: dict[str, Any] = {
    "panel": None,
    "model": None,
    "model_name": None,
    "trained_until": None,
    "coverage_empirical": None,
    #: Motivo por el que el artefacto no se pudo cargar, si existe pero fallo.
    #: Distingue "no hay modelo" de "hay uno y esta roto", que se arreglan distinto.
    "model_error": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Carga el panel y el artefacto al arrancar.

    Si no hay artefacto entrenado la API **igual levanta**, y `/health` lo dice con
    `model_loaded: false`. Es a proposito: un healthcheck que no distingue "no
    arranco" de "arranco sin modelo" hace perder tiempo cuando algo falla.
    """
    try:
        STATE["panel"] = loaders.load_demand()
    except loaders.DataNotAvailableError as exc:
        log.warning("sin datos: %s", exc)

    artifact = cfg.ARTIFACTS / "model.joblib"
    if not artifact.exists():
        log.warning(
            "no hay artefacto en %s; /forecast y /reorder van a responder 503",
            artifact,
        )
    else:
        # Un artefacto ilegible **no puede tumbar la API**. Antes si lo hacia, y lo
        # expuso el rename de `dfcore` a `blindside`: joblib graba la ruta del
        # modulo dentro del pickle, asi que todo .joblib anterior al rename murio
        # con `ModuleNotFoundError: No module named 'dfcore'` y el contenedor
        # entraba en bucle de reinicio.
        #
        # La misma falla aparece con cualquier desfasaje entre el artefacto y el
        # codigo: una clase renombrada, un modulo movido, una version de
        # scikit-learn distinta de la que serializo. Es una condicion esperable en
        # operacion, no una excepcion excepcional, asi que se degrada a
        # `model_loaded: false` con el motivo a la vista y los endpoints que
        # dependen del modelo responden 503. El dashboard sigue funcionando porque
        # lee los parquet directamente.
        try:
            from blindside.models.base import Forecaster

            model = Forecaster.load(artifact)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de carga degrada igual
            STATE["model_error"] = f"{type(exc).__name__}: {exc}"
            log.error(
                "el artefacto %s existe pero no se pudo cargar (%s). La API arranca "
                "sin modelo. Si acabas de renombrar el paquete o cambiar versiones, "
                "reentrenar con `make train`.",
                artifact,
                STATE["model_error"],
            )
        else:
            STATE["model"] = model
            STATE["model_name"] = model.name
            STATE["trained_until"] = (
                model.last_train_date.date() if model.last_train_date is not None else None
            )
            log.info("modelo '%s' cargado de %s", model.name, artifact)
            if STATE["panel"] is not None:
                _check_model_matches_panel(model, STATE["panel"])
    yield
    STATE.clear()


app = FastAPI(
    title="Blindside",
    version=__version__,
    summary=(
        "Pronostico de demanda de perecederos con recuperacion de demanda censurada "
        "y capa de decision de reposicion"
    ),
    description=__doc__,
    lifespan=lifespan,
)


# --------------------------------------------------------------------------
# Utilidades internas
# --------------------------------------------------------------------------
def _require_model():
    model = STATE.get("model")
    if model is not None:
        return model
    # El mensaje distingue los dos casos porque se arreglan distinto.
    error = STATE.get("model_error")
    detail = (
        f"el artefacto existe pero no se pudo cargar ({error}). Suele ser desfasaje "
        "entre el artefacto y el codigo: reentrenar con `make train`."
        if error
        else f"no hay modelo cargado. Entrenar y serializar en {cfg.ARTIFACTS / 'model.joblib'}"
    )
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


def _require_panel() -> pd.DataFrame:
    panel = STATE.get("panel")
    if panel is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="no hay datos cargados. Correr `make data` y `make recover`",
        )
    return panel


def _series_refs(panel: pd.DataFrame, series_ids: Sequence[str]) -> dict[str, sc.SeriesRef]:
    """Metadatos de las series pedidas. Falla si alguna no existe."""
    index = S.series_index(panel).set_index(S.SERIES_ID)
    missing = [s for s in series_ids if s not in index.index]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"series desconocidas: {missing[:10]}",
        )
    return {
        sid: sc.SeriesRef(
            series_id=sid,
            store_id=int(index.loc[sid, S.STORE_ID]),
            product_id=int(index.loc[sid, S.PRODUCT_ID]),
            city_id=int(index.loc[sid, S.CITY_ID]),
        )
        for sid in series_ids
    }


def _future_index(panel: pd.DataFrame, series_ids: Sequence[str], horizon: int) -> pd.DataFrame:
    """Indice de futuro desde el ultimo dia del panel. Sin columnas de target.

    Se construye igual que en el arnes de backtesting, y por el mismo motivo: el
    modelo tiene que recibir exactamente la misma forma en produccion que en
    validacion, o las metricas reportadas no dicen nada sobre lo que pasa aca.
    """
    origin = pd.Timestamp(panel[S.DATE].max())
    dates = [origin + pd.Timedelta(days=h) for h in range(1, horizon + 1)]
    grid = pd.MultiIndex.from_product(
        [list(series_ids), dates], names=[S.SERIES_ID, S.DATE]
    ).to_frame(index=False)
    grid["h"] = (grid[S.DATE] - origin).dt.days.astype("int16")

    # Tipos parejos con el panel, para que un map o un groupby posterior no
    # dependa de como se construyo el frame.
    grid[S.SERIES_ID] = grid[S.SERIES_ID].astype("string")

    static = S.series_index(panel)
    out = grid.merge(static, on=S.SERIES_ID, how="left")
    if out[S.STORE_ID].isna().any():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="el cruce con los atributos de serie dejo filas sin jerarquia",
        )
    return out


def _check_model_matches_panel(model, panel: pd.DataFrame) -> None:
    """Avisa si el artefacto se entreno sobre otra capa de datos que la servida.

    Es un desajuste train/serve que **ninguna metrica detecta**: el backtest del
    modelo puede estar perfecto y la API devolver la misma cantidad para todas las
    series, porque ninguna de las que se piden existe en su estado de origen.
    Paso en este proyecto con un artefacto de `data/sample/` sirviendo el panel de
    `data/processed/`.
    """
    seen = getattr(model, "_series_seen", None)
    base = getattr(model, "base", None)
    if not seen and base is not None:
        seen = getattr(base, "_series_seen", None)
    if not seen:
        return
    available = set(panel[S.SERIES_ID].astype(str).unique())
    overlap = len(available & set(seen))
    if overlap == 0:
        log.error(
            "el modelo conoce %d series y NINGUNA esta en el panel servido: el "
            "artefacto se entreno sobre otra capa de datos. Reentrenar con "
            "`make train`.",
            len(seen),
        )
    elif overlap < 0.5 * len(available):
        log.warning(
            "el modelo conoce %d de las %d series del panel servido (%.0f %%); las "
            "demas van a extrapolar",
            overlap,
            len(available),
            100 * overlap / len(available),
        )


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@app.get("/health", response_model=sc.Health, tags=["infra"])
def health() -> sc.Health:
    """Healthcheck. Distingue "arranco" de "arranco con modelo"."""
    return sc.Health(
        status="ok",
        version=__version__,
        model_loaded=STATE.get("model") is not None,
        model_name=STATE.get("model_name"),
        trained_until=STATE.get("trained_until"),
        model_error=STATE.get("model_error"),
    )


@app.get("/series", tags=["datos"])
def list_series(limit: int = 100) -> list[sc.SeriesRef]:
    """Series disponibles. Es lo que el frontend usa para poblar los selectores."""
    panel = _require_panel()
    index = S.series_index(panel).head(limit)
    return [
        sc.SeriesRef(
            series_id=str(r[S.SERIES_ID]),
            store_id=int(r[S.STORE_ID]),
            product_id=int(r[S.PRODUCT_ID]),
            city_id=int(r[S.CITY_ID]),
        )
        for _, r in index.iterrows()
    ]


@app.post("/forecast", response_model=sc.ForecastResponse, tags=["pronostico"])
def forecast(req: sc.ForecastRequest) -> sc.ForecastResponse:
    """Pronostico con intervalo, si el modelo cargado esta conformalizado."""
    panel = _require_panel()
    model = _require_model()
    refs = _series_refs(panel, req.series_ids)

    future = _future_index(panel, req.series_ids, req.horizon)
    point = model.predict(future)

    lo = hi = None
    if hasattr(model, "predict_interval"):
        interval = model.predict_interval(future)
        lo, hi = interval["pred_lo"], interval["pred_hi"]

    forecasts = []
    for sid in req.series_ids:
        mask = future[S.SERIES_ID] == sid
        rows = future.loc[mask]
        points = [
            sc.ForecastPoint(
                dt=r[S.DATE].date(),
                h=int(r["h"]),
                y_pred=float(point.loc[i]),
                pred_lo=float(lo.loc[i]) if lo is not None else None,
                pred_hi=float(hi.loc[i]) if hi is not None else None,
            )
            for i, r in rows.iterrows()
        ]
        forecasts.append(sc.SeriesForecast(series=refs[sid], points=points))

    return sc.ForecastResponse(
        model_name=str(STATE["model_name"]),
        coverage_nominal=req.coverage,
        coverage_empirical=STATE.get("coverage_empirical"),
        forecasts=forecasts,
    )


@app.post("/reorder", response_model=sc.ReorderResponse, tags=["decision"])
def reorder(req: sc.ReorderRequest) -> sc.ReorderResponse:
    """Cantidad a reponer: el cuantil critico del newsvendor.

    La salida del modelo **es** la orden. No es un pronostico que alguien tenga que
    interpretar y despues ajustar a mano con un stock de seguridad.
    """
    from blindside.decision.newsvendor import critical_fraction

    panel = _require_panel()
    model = _require_model()
    refs = _series_refs(panel, req.series_ids)

    economics = cfg.EconomicsConfig(cu=req.cu, co=req.co)
    q_star = critical_fraction(cu=req.cu, co=req.co)
    future = _future_index(panel, req.series_ids, req.horizon)

    if hasattr(model, "reorder_quantity"):
        qty = model.reorder_quantity(future, economics=economics)
    elif hasattr(model, "predict_quantile") and getattr(model, "supports_quantiles", False):
        from blindside.decision.newsvendor import optimal_order_from_quantiles

        quantiles = getattr(model, "quantiles", cfg.FORECAST.quantiles)
        qty = optimal_order_from_quantiles(
            model.predict_quantile(future, quantiles),
            quantiles=quantiles,
            economics=economics,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"el modelo cargado ('{STATE['model_name']}') no produce cuantiles, "
                "asi que no puede emitir una orden derivada de la economia. Cargar "
                "un LightGBMQuantileForecaster o un ConformalForecaster."
            ),
        )

    lines = [
        sc.ReorderLine(
            series=refs[str(r[S.SERIES_ID])],
            dt=r[S.DATE].date(),
            qty=float(qty.loc[i]),
            critical_fraction=q_star,
            # Sin verdad de terreno no hay faltante ni sobrante realizado. Se
            # informan en cero y el dashboard los toma del backtest, que si tiene
            # con que compararse. Inventar una estimacion aca seria peor.
            expected_shortfall=0.0,
            expected_overage=0.0,
            cost_delta_pct=0.0,
        )
        for i, r in future.iterrows()
    ]
    return sc.ReorderResponse(critical_fraction=q_star, lines=lines, total_cost_delta_pct=0.0)


@app.get("/backtest", response_model=sc.BacktestResponse, tags=["evaluacion"])
def backtest() -> sc.BacktestResponse:
    """Metricas del ultimo backtest, con dispersion entre origenes.

    Lee `reports/backtest_models.parquet`, que produce `make models`. No corre el
    backtest en el request: son minutos de entrenamiento y una API no es el lugar.
    """
    from blindside.evaluate import metrics as M

    path = cfg.REPORTS / "backtest_models.parquet"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"no hay resultado de backtest en {path}. Correr `make models`",
        )
    result = pd.read_parquet(path)
    summary = M.summarize(result)
    return sc.BacktestResponse(
        target=S.DEMAND_LATENT,
        horizon=cfg.FORECAST.horizon,
        season_length=cfg.FORECAST.season_length,
        rows=[
            sc.MetricRow(
                model_name=str(r["model"]),
                metric=str(r["metric"]),
                mean=float(r["mean"]),
                std=float(r["std"]),
                worst_origin=float(r["worst_origin"]),
                best_origin=float(r["best_origin"]),
                n_origins=int(r["n_origins"]),
            )
            for _, r in summary.iterrows()
        ],
    )


@app.get("/censoring", tags=["evaluacion"])
def censoring() -> dict[str, Any]:
    """Resumen de censura del panel: observado contra latente recuperado."""
    from blindside.decision.censoring import censoring_report

    panel = _require_panel()
    report = censoring_report(panel)
    return {
        "summary": S.describe_censoring(panel),
        "comparison": report.to_dict(orient="records"),
        "note": (
            "En dias sin quiebre la demanda latente es identica a la venta observada, "
            "por diseno: son la verdad de terreno con la que se mide el sesgo."
        ),
    }


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "name": "blindside-core",
        "version": __version__,
        "docs": "/docs",
        "warning": "sin autenticacion; no exponer a una red publica",
    }


def _today() -> date:  # pragma: no cover - punto de inyeccion para tests
    return date.today()
