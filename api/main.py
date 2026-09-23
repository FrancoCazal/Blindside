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
* El CORS es un **allowlist explicito** con los origenes del dev server del
  frontend, no un comodin. Sin autenticacion, `allow_origins=["*"]` significaria
  que cualquier pagina abierta en el navegador del usuario puede leer estos datos
  desde su maquina. Se sobreescribe con `BLINDSIDE_CORS_ORIGINS`.

Para la Fase 2 multi-tenant esto se vuelve bloqueante: hace falta autenticacion
por tenant y aislamiento de datos antes de que sirva a mas de una organizacion.
Esta en el roadmap de `docs/decisiones.md`.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from typing import TYPE_CHECKING, Any

import pandas as pd
from api import schemas as sc
from fastapi import FastAPI, HTTPException, Path, Query, status
from fastapi.middleware.cors import CORSMiddleware

from blindside import __version__
from blindside import config as cfg
from blindside.data import loaders
from blindside.data import schema as S
from blindside.models.base import TARGET_BY_BASIS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from pathlib import Path as FsPath

log = logging.getLogger(__name__)

#: Estado del proceso. Se carga una vez al arrancar y no por request: releer el
#: panel en cada consulta convertiria una API en un lector de parquet.
STATE: dict[str, Any] = {
    "panel": None,
    #: Que capa de datos se esta sirviendo, con sus conteos. Es lo que dispara el
    #: estado "estas viendo la muestra" de la interfaz.
    "panel_info": None,
    #: Un artefacto por base de calculo: basis -> dict con el modelo y su estado.
    #: Son dos porque el toggle de censura tiene que poder cambiar la cantidad
    #: sugerida, no solo la serie que se dibuja.
    "models": {},
    "coverage_empirical": None,
    "coverage_by_horizon": None,
    "coverage_note": None,
}


def _load_artifact(basis: cfg.Basis) -> dict[str, Any]:
    """Carga el artefacto de una base. Nunca levanta: degrada con el motivo.

    Un artefacto ilegible **no puede tumbar la API**. Antes si lo hacia, y lo
    expuso el rename de `dfcore` a `blindside`: joblib graba la ruta del modulo
    dentro del pickle, asi que todo .joblib anterior al rename murio con
    `ModuleNotFoundError: No module named 'dfcore'` y el contenedor entraba en
    bucle de reinicio.

    La misma falla aparece con cualquier desfasaje entre el artefacto y el codigo:
    una clase renombrada, un modulo movido, una version de scikit-learn distinta
    de la que serializo. Es una condicion esperable en operacion, no una excepcion
    excepcional, asi que se degrada a `loaded: false` con el motivo a la vista y
    los endpoints que dependen de ese modelo responden 503. El dashboard sigue
    funcionando porque lee los parquet directamente.
    """
    path = cfg.model_path(basis)
    slot: dict[str, Any] = {
        "model": None,
        "name": None,
        "target": None,
        "trained_until": None,
        "error": None,
        #: Que hay que correr para arreglarlo. Va separado del motivo para que el
        #: 503 diga las dos cosas sin repetirse.
        "fix": f"`python -m blindside.models train --basis {basis}`",
        "artifact": path.name,
    }
    if not path.exists():
        log.warning(
            "no hay artefacto para la base '%s' en %s; los endpoints que la pidan "
            "van a responder 503. Serializar con `make train`",
            basis,
            path,
        )
        return slot

    try:
        from blindside.models.base import Forecaster

        model = Forecaster.load(path)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de carga degrada igual
        slot["error"] = f"{type(exc).__name__}: {exc}"
        slot["fix"] = (
            "suele ser desfasaje entre el artefacto y el codigo: reentrenar con " "`make train`"
        )
        log.error(
            "el artefacto %s existe pero no se pudo cargar (%s). La API arranca sin "
            "esa base. Si acabas de renombrar el paquete o cambiar versiones, "
            "reentrenar con `make train`.",
            path,
            slot["error"],
        )
        return slot

    from blindside.models.base import fitted_target

    trained_on = fitted_target(model)
    expected = TARGET_BY_BASIS[basis]
    if trained_on is not None and trained_on != expected:
        # Se rechaza en vez de servirlo. Un artefacto cruzado hace que el toggle
        # de censura conteste lo mismo en las dos posiciones: la interfaz muestra
        # una diferencia de cero y parece que el proyecto no tiene efecto, o peor,
        # parece que funciona y no esta midiendo nada. Un 503 con el motivo es
        # mucho mas facil de diagnosticar que dos numeros identicos.
        slot["error"] = (
            f"el artefacto {path.name} se entreno sobre '{trained_on}' y la base "
            f"'{basis}' exige '{expected}'"
        )
        log.error("%s; %s", slot["error"], slot["fix"])
        return slot

    slot.update(
        model=model,
        name=model.name,
        target=trained_on or expected,
        trained_until=(model.last_train_date.date() if model.last_train_date is not None else None),
    )
    log.info("modelo '%s' cargado de %s para la base '%s'", model.name, path, basis)
    return slot


def _panel_info(panel: pd.DataFrame, path: FsPath) -> sc.PanelInfo:
    """Conteos del panel servido, contra la referencia del submuestreo.

    Los conteos van siempre contra su total: "60 de 3066 series" dice algo, "60
    series" no. La referencia sale del manifiesto de `data/interim/`; si no esta,
    queda en `None` y la interfaz no puede afirmar que ve el panel completo.
    """
    is_sample = path.parent == cfg.DATA_SAMPLE
    reference: dict[str, Any] = {}
    manifest = cfg.DATA_INTERIM / cfg.MANIFEST_FILE
    if manifest.exists():
        try:
            reference = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - manifiesto roto
            log.warning("manifiesto %s ilegible (%s); sin referencia de panel", manifest, exc)

    return sc.PanelInfo(
        source="sample" if is_sample else "processed",
        is_sample=is_sample,
        n_series=int(panel[S.SERIES_ID].nunique()),
        n_stores=int(panel[S.STORE_ID].nunique()),
        n_products=int(panel[S.PRODUCT_ID].nunique()),
        n_days=int(panel[S.DATE].nunique()),
        date_min=pd.Timestamp(panel[S.DATE].min()).date(),
        date_max=pd.Timestamp(panel[S.DATE].max()).date(),
        reference_n_series=reference.get("n_series_actual"),
        reference_n_stores=reference.get("n_stores"),
        reference_n_products=reference.get("n_products"),
    )


def _coverage_by_horizon() -> tuple[list[sc.CoveragePoint], str | None]:
    """Cobertura empirica por paso del horizonte, desde el backtest guardado.

    Devuelve lista vacia con un motivo cuando no se puede calcular. La pantalla de
    salud del modelo tiene que poder decir *por que* no hay cobertura en vez de
    mostrar un numero sintetico: el proyecto mide justamente la brecha entre
    cobertura prometida y cobertura real, asi que inventarla seria contradictorio.
    """
    from blindside.evaluate import contracts as C

    path = cfg.REPORTS / "backtest_models.parquet"
    if not path.exists():
        return [], (
            f"no hay backtest guardado en {path.name}: correr `make models`. La "
            "cobertura empirica se mide en el backtest, no en el request"
        )

    result = pd.read_parquet(path)
    if C.PRED_LO not in result.columns or result[C.PRED_LO].isna().all():
        return [], (
            f"{path.name} no trae intervalos: los modelos del ultimo backtest son "
            "puntuales. La cobertura empirica exige un modelo conformalizado en la "
            "corrida (`--models lgbm_quantile` con conformal)"
        )

    from blindside.evaluate import metrics as M

    nominal = cfg.FORECAST.coverage
    rows: list[sc.CoveragePoint] = []
    intervals = result.dropna(subset=[C.PRED_LO, C.PRED_HI])
    for h, g in intervals.groupby(C.HORIZON_STEP, observed=True):
        rows.append(
            sc.CoveragePoint(
                h=int(h),
                coverage_nominal=nominal,
                coverage_empirical=M.empirical_coverage(
                    g[C.Y_TRUE].to_numpy(dtype="float64"),
                    g[C.PRED_LO].to_numpy(dtype="float64"),
                    g[C.PRED_HI].to_numpy(dtype="float64"),
                ),
                n=int(len(g)),
            )
        )
    return rows, None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Carga el panel y los artefactos al arrancar.

    Si no hay artefacto entrenado la API **igual levanta**, y `/health` lo dice con
    `model_loaded: false`. Es a proposito: un healthcheck que no distingue "no
    arranco" de "arranco sin modelo" hace perder tiempo cuando algo falla.
    """
    try:
        path = loaders.resolve_path("demand")
        STATE["panel"] = loaders.load_demand(path=path)
        STATE["panel_info"] = _panel_info(STATE["panel"], path)
    except loaders.DataNotAvailableError as exc:
        log.warning("sin datos: %s", exc)

    STATE["models"] = {basis: _load_artifact(basis) for basis in cfg.MODEL_FILES}
    if STATE["panel"] is not None:
        for slot in STATE["models"].values():
            if slot["model"] is not None:
                _check_model_matches_panel(slot["model"], STATE["panel"])

    try:
        STATE["coverage_by_horizon"], STATE["coverage_note"] = _coverage_by_horizon()
    except Exception as exc:  # noqa: BLE001 - un reporte roto no tumba la API
        STATE["coverage_by_horizon"], STATE["coverage_note"] = [], f"{type(exc).__name__}: {exc}"
        log.warning("no se pudo calcular la cobertura por horizonte: %s", exc)
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

#: Origenes que pueden llamar a la API desde un navegador. Son los del dev server
#: del frontend (Vite en 5173, su preview en 4173) y se sobreescriben con
#: BLINDSIDE_CORS_ORIGINS separados por coma.
#:
#: Es un allowlist explicito y **no** un comodin: esta API no tiene
#: autenticacion, asi que `*` significaria que cualquier pagina que el usuario
#: tenga abierta puede leer los pronosticos y las cantidades de reposicion de
#: todas las tiendas desde su navegador. `allow_credentials` queda en False
#: porque no hay cookie ni token que mandar, y ponerlo en True con un comodin es
#: justamente la combinacion que los navegadores rechazan.
DEFAULT_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)


def cors_origins() -> list[str]:
    raw = os.environ.get("BLINDSIDE_CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()] or list(DEFAULT_CORS_ORIGINS)
    if "*" in origins:
        log.warning(
            "CORS con comodin: cualquier sitio puede consultar esta API desde el "
            "navegador y no hay autenticacion. Solo para desarrollo local."
        )
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# --------------------------------------------------------------------------
# Utilidades internas
# --------------------------------------------------------------------------
def _basis_of(*, recover_censoring: bool) -> cfg.Basis:
    """Traduce el flag del request al nombre de la base de calculo."""
    return "recovered" if recover_censoring else "observed"


def _slot(basis: cfg.Basis) -> dict[str, Any]:
    return STATE.get("models", {}).get(basis) or {}


def _require_model(basis: cfg.Basis = cfg.DEFAULT_BASIS):
    """Modelo de una base, o 503 explicando cual falta y como se arregla."""
    slot = _slot(basis)
    model = slot.get("model")
    if model is not None:
        return model

    # El mensaje distingue los tres casos porque se arreglan distinto: no hay
    # artefacto, hay uno y no carga, o hay uno entrenado sobre la otra base.
    error = slot.get("error")
    artifact = slot.get("artifact") or cfg.model_path(basis).name
    fix = slot.get("fix") or "`make train`"
    detail = (
        f"la base '{basis}' no esta disponible: {error}. {fix}"
        if error
        else (
            f"no hay modelo para la base '{basis}'. Falta "
            f"{cfg.ARTIFACTS / artifact}; entrenar con {fix}"
        )
    )
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


def _model_name(basis: cfg.Basis) -> str:
    return str(_slot(basis).get("name") or "")


def _series_seen(model) -> set[str] | None:
    """Series que el modelo vio en entrenamiento, atravesando el envoltorio."""
    seen = getattr(model, "_series_seen", None)
    if not seen:
        base = getattr(model, "base", None)
        seen = getattr(base, "_series_seen", None)
    return set(seen) if seen else None


def _opt_int(value: Any) -> int | None:
    return None if value is None or pd.isna(value) else int(value)


def _opt_float(value: Any) -> float | None:
    return None if value is None or pd.isna(value) else float(value)


def _require_backtest() -> pd.DataFrame:
    """Resultado del ultimo backtest, o 503 con el comando que lo genera.

    No se corre el backtest en el request: son minutos de entrenamiento por modelo
    y una API no es el lugar.
    """
    path = cfg.REPORTS / "backtest_models.parquet"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"no hay resultado de backtest en {path}. Correr `make models`",
        )
    return pd.read_parquet(path)


#: Nombres de columna del contrato de backtest. Se leen aca para no importar el
#: modulo de contratos en cada request.
C_MODEL = "model"
C_ORIGIN = "origin"
C_ORIGIN_DATE = "origin_date"

#: Metricas que la interfaz muestra. El resto viven en el reporte: una pantalla
#: con nueve metricas no comunica cual importa.
_METRICAS_VISIBLES: tuple[str, ...] = ("mase", "wape", "mae", "coverage")


def _rotation_bands() -> pd.Series:
    """Banda de rotacion por serie, calculada una vez y memorizada.

    Usa los mismos cortes que el backtest para desagregar sus metricas, asi que la
    clase que muestra la tabla es la misma con la que se reporta que el modelo
    complejo no le gana al ingenuo en baja rotacion.
    """
    cacheada = STATE.get("rotation_bands")
    if cacheada is not None:
        return cacheada
    from blindside.validation.splits import rotation_bands

    panel = _require_panel()
    bandas = rotation_bands(panel, target=S.DEMAND_LATENT)
    STATE["rotation_bands"] = bandas
    return bandas


def _uplift_pct(observed, recovered) -> float:
    """Cuanto mas alta es la demanda latente que la venta observada, en porcentaje.

    Se calcula sobre las **sumas** y no como promedio de razones por dia: un dia
    con venta observada cero — que es exactamente el caso de quiebre total — daria
    una razon infinita y dominaria el promedio.
    """
    total_observed = float(observed.sum())
    if total_observed <= 0:
        return 0.0
    return 100.0 * (float(recovered.sum()) / total_observed - 1.0)


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
    seen = _series_seen(model)
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
    """Healthcheck. Distingue "arranco" de "arranco con modelo".

    Es tambien el endpoint del que la interfaz deriva su estado global: que capa de
    datos se esta sirviendo, si el toggle de censura tiene las dos bases cargadas y
    cuanta de la cobertura prometida se cumple de verdad.
    """
    panel = STATE.get("panel")
    models = []
    for basis, slot in STATE.get("models", {}).items():
        model = slot.get("model")
        seen = _series_seen(model) if model is not None else None
        in_panel = None
        if seen is not None and panel is not None:
            in_panel = len(seen & set(panel[S.SERIES_ID].astype(str).unique()))
        models.append(
            sc.ModelStatus(
                basis=sc.Basis(basis),
                artifact=slot.get("artifact") or cfg.model_path(basis).name,
                loaded=model is not None,
                model_name=slot.get("name"),
                target=slot.get("target"),
                trained_until=slot.get("trained_until"),
                n_series_seen=len(seen) if seen is not None else None,
                n_series_in_panel=in_panel,
                error=slot.get("error"),
            )
        )

    default = _slot(cfg.DEFAULT_BASIS)
    return sc.Health(
        status="ok",
        version=__version__,
        model_loaded=default.get("model") is not None,
        model_name=default.get("name"),
        trained_until=default.get("trained_until"),
        model_error=default.get("error"),
        models=models,
        panel=STATE.get("panel_info"),
        coverage_nominal=cfg.FORECAST.coverage,
        coverage_by_horizon=STATE.get("coverage_by_horizon") or [],
        coverage_note=STATE.get("coverage_note"),
    )


def _catalog_label(row: pd.Series) -> str:
    """Descripcion buscable de una serie.

    El dataset no trae nombres de producto, solo la jerarquia de categorias en
    ids, asi que la descripcion es la jerarquia. Es fea y es cierta; un nombre
    inventado seria legible y falso.
    """
    parts = [f"tienda {int(row[S.STORE_ID])}", f"producto {int(row[S.PRODUCT_ID])}"]
    if S.MANAGEMENT_GROUP_ID in row:
        parts.append(f"grupo {int(row[S.MANAGEMENT_GROUP_ID])}")
    cats = [
        c
        for c in (S.FIRST_CATEGORY_ID, S.SECOND_CATEGORY_ID, S.THIRD_CATEGORY_ID)
        if c in row and pd.notna(row[c])
    ]
    if cats:
        parts.append("cat " + "/".join(str(int(row[c])) for c in cats))
    if S.CITY_ID in row and pd.notna(row[S.CITY_ID]):
        parts.append(f"ciudad {int(row[S.CITY_ID])}")
    return " · ".join(parts)


@app.get("/series", response_model=sc.SeriesPage, tags=["datos"])
def list_series(
    q: str | None = Query(
        default=None,
        description=(
            "busqueda incremental sobre el codigo de la serie y su jerarquia. "
            "Varias palabras se combinan con AND"
        ),
    ),
    store_id: int | None = Query(default=None, description="filtra por tienda"),
    rotation_band: str | None = Query(
        default=None, description="filtra por clase de rotacion: baja, media o alta"
    ),
    limit: int = Query(default=100, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> sc.SeriesPage:
    """Series disponibles, con busqueda y paginacion. Es el selector de la interfaz.

    Devuelve `total` aparte de la pagina porque el selector muestra el conteo de
    resultados sobre el total: con 3066 series un desplegable no es usable y el
    usuario necesita saber si lo que busca esta filtrado o no existe.

    La busqueda corre sobre el codigo de la serie y sobre la jerarquia. Como el
    dataset no trae nombres de producto, la jerarquia es una lista de ids, asi que
    un numero suelto ("2") tambien aparece en el producto o en la categoria y la
    busqueda trae de mas. Para filtrar con precision esta `store_id`; la busqueda
    esta para descubrir. Con nombres de producto esto se resolveria solo, pero
    inventarlos seria inventar datos.
    """
    panel = _require_panel()
    index = S.series_index(panel)
    index["label"] = index.apply(_catalog_label, axis=1)
    # La banda de rotacion es la columna "Clase" de la tabla. Se calcula una vez
    # al arrancar: es un groupby sobre el panel entero y no cambia entre requests.
    bandas = _rotation_bands()
    index["rotation_band"] = index[S.SERIES_ID].map(bandas)

    if store_id is not None:
        index = index[index[S.STORE_ID] == store_id]
    if rotation_band is not None:
        index = index[index["rotation_band"] == rotation_band]
    if q:
        haystack = index[S.SERIES_ID].astype(str).str.lower() + " " + index["label"].str.lower()
        for token in q.lower().split():
            index = index[haystack.loc[index.index].str.contains(token, regex=False)]

    total = int(len(index))
    page = index.sort_values(S.SERIES_ID).iloc[offset : offset + limit]
    items = [
        sc.SeriesItem(
            series_id=str(r[S.SERIES_ID]),
            store_id=int(r[S.STORE_ID]),
            product_id=int(r[S.PRODUCT_ID]),
            city_id=_opt_int(r.get(S.CITY_ID)),
            management_group_id=_opt_int(r.get(S.MANAGEMENT_GROUP_ID)),
            first_category_id=_opt_int(r.get(S.FIRST_CATEGORY_ID)),
            second_category_id=_opt_int(r.get(S.SECOND_CATEGORY_ID)),
            third_category_id=_opt_int(r.get(S.THIRD_CATEGORY_ID)),
            rotation_band=(str(r["rotation_band"]) if pd.notna(r["rotation_band"]) else None),
            label=str(r["label"]),
        )
        for _, r in page.iterrows()
    ]
    return sc.SeriesPage(total=total, limit=limit, offset=offset, query=q, items=items)


@app.get("/series/{series_id}/history", response_model=sc.SeriesHistory, tags=["datos"])
def series_history(
    series_id: str = Path(description="id de la serie, '<store_id>_<product_id>'"),
    days: int | None = Query(
        default=None, ge=7, le=400, description="ultimos N dias; por defecto toda la historia"
    ),
) -> sc.SeriesHistory:
    """Venta observada contra demanda latente, dia por dia, con los tramos de quiebre.

    Es el endpoint de la pantalla principal y el unico lugar de la API donde las
    dos series se devuelven juntas. Van juntas a proposito: el argumento del
    proyecto es la **brecha** entre ellas, y dos llamadas separadas invitan a
    dibujarlas desalineadas o a comparar rangos de fechas distintos.

    En los dias sin quiebre las dos series son identicas por diseno, no por
    casualidad: son la verdad de terreno con la que se mide el sesgo, asi que
    corregirlas destruiria la medicion. `summary.uplift_pct_clean_days` lo
    devuelve como comprobacion, y tiene que dar 0.
    """
    return _build_history(_require_panel(), series_id, days)


@app.post("/series/history", response_model=sc.SeriesHistoryBatch, tags=["datos"])
def series_history_batch(req: sc.SeriesHistoryRequest) -> sc.SeriesHistoryBatch:
    """La misma historia para varias series de una vez.

    Existe porque la pantalla de reposicion la necesita **por fila**: el sparkline
    de quiebre de los ultimos 14 dias y la comparacion contra la politica de media
    movil salen de la historia, no del pronostico. Una llamada por fila seria un
    N+1 contra un panel que ya esta en memoria.
    """
    panel = _require_panel()
    return sc.SeriesHistoryBatch(
        series=[_build_history(panel, sid, req.days) for sid in req.series_ids]
    )


def _build_history(panel: pd.DataFrame, series_id: str, days: int | None) -> sc.SeriesHistory:
    rows = panel[panel[S.SERIES_ID].astype(str) == series_id].sort_values(S.DATE)
    if rows.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"serie '{series_id}' desconocida en el panel servido",
        )
    if days is not None:
        rows = rows.tail(days)

    static = rows.iloc[-1]
    censored = rows[S.IS_CENSORED].astype(bool).to_numpy()
    observed = rows[S.SALE_AMOUNT].to_numpy(dtype="float64")
    recovered = rows[S.DEMAND_LATENT].to_numpy(dtype="float64")
    dates = [pd.Timestamp(d).date() for d in rows[S.DATE]]

    points = [
        sc.HistoryPoint(
            dt=dates[i],
            observed=float(observed[i]),
            recovered=float(recovered[i]),
            is_censored=bool(censored[i]),
            oos_hours_open=float(rows[S.OOS_HOURS_OPEN].iloc[i]),
            available_weight=_opt_float(rows[S.AVAILABLE_WEIGHT].iloc[i])
            if S.AVAILABLE_WEIGHT in rows.columns
            else None,
            inflation_factor=_opt_float(rows[S.INFLATION].iloc[i])
            if S.INFLATION in rows.columns
            else None,
        )
        for i in range(len(rows))
    ]

    runs: list[sc.StockoutRun] = []
    start: int | None = None
    for i, flag in enumerate(censored):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append(sc.StockoutRun(start=dates[start], end=dates[i - 1], n_days=i - start))
            start = None
    if start is not None:
        runs.append(sc.StockoutRun(start=dates[start], end=dates[-1], n_days=len(censored) - start))

    clean = ~censored
    last28 = censored[-28:]
    summary = sc.HistorySummary(
        n_days=len(rows),
        n_censored_days=int(censored.sum()),
        censored_days_last_28=int(last28.sum()),
        share_censored_days=float(censored.mean()),
        max_run_days=max((r.n_days for r in runs), default=0),
        mean_oos_hours_when_censored=(
            float(rows.loc[censored, S.OOS_HOURS_OPEN].mean()) if censored.any() else None
        ),
        uplift_pct=_uplift_pct(observed, recovered),
        uplift_pct_clean_days=_uplift_pct(observed[clean], recovered[clean]),
    )

    return sc.SeriesHistory(
        series=sc.SeriesRef(
            series_id=series_id,
            store_id=int(static[S.STORE_ID]),
            product_id=int(static[S.PRODUCT_ID]),
            city_id=_opt_int(static.get(S.CITY_ID)),
        ),
        open_hours=len(cfg.CENSORING.open_hours),
        points=points,
        runs=runs,
        summary=summary,
    )


@app.post("/forecast", response_model=sc.ForecastResponse, tags=["pronostico"])
def forecast(req: sc.ForecastRequest) -> sc.ForecastResponse:
    """Pronostico con intervalo, si el modelo cargado esta conformalizado.

    `recover_censoring` elige el artefacto: el entrenado sobre demanda latente o el
    entrenado sobre venta observada. Es un modelo distinto y no un ajuste del
    mismo, porque el sesgo de la censura se aprende durante el entrenamiento —
    corregir la salida despues seria inventar el efecto que el proyecto mide.
    """
    basis = _basis_of(recover_censoring=req.recover_censoring)
    panel = _require_panel()
    model = _require_model(basis)
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
        model_name=_model_name(basis),
        basis=sc.Basis(basis),
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

    basis = _basis_of(recover_censoring=req.recover_censoring)
    panel = _require_panel()
    model = _require_model(basis)
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
                f"el modelo cargado para la base '{basis}' ('{_model_name(basis)}') no "
                "produce cuantiles, asi que no puede emitir una orden derivada de la "
                "economia. Cargar un LightGBMQuantileForecaster o un ConformalForecaster."
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
    return sc.ReorderResponse(
        critical_fraction=q_star,
        basis=sc.Basis(basis),
        model_name=_model_name(basis),
        lines=lines,
        total_cost_delta_pct=0.0,
    )


@app.get("/backtest", response_model=sc.BacktestResponse, tags=["evaluacion"])
def backtest() -> sc.BacktestResponse:
    """Metricas del ultimo backtest, con dispersion entre origenes.

    Lee `reports/backtest_models.parquet`, que produce `make models`. No corre el
    backtest en el request: son minutos de entrenamiento y una API no es el lugar.
    """
    from blindside.evaluate import metrics as M

    result = _require_backtest()
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


@app.post("/explain", response_model=sc.ExplainResponse, tags=["explicabilidad"])
def explain(req: sc.ExplainRequest) -> sc.ExplainResponse:
    """Contribuciones por feature de una prediccion concreta.

    Son TreeSHAP **de verdad**, calculadas por LightGBM con `pred_contrib=True`, no
    el paquete `shap`: son los mismos valores — es la implementacion que LightGBM
    lleva adentro — y asi la explicabilidad funciona en la imagen de servicio, que
    deja `shap` afuera porque pesa y no hace falta para responder `/forecast`.

    Se explica el cuantil critico y no la mediana, porque la cifra que la interfaz
    muestra es la cantidad a pedir.
    """
    basis = _basis_of(recover_censoring=req.recover_censoring)
    panel = _require_panel()
    model = _require_model(basis)
    refs = _series_refs(panel, [req.series_id])

    # El modelo explicable puede estar debajo del envoltorio conformal.
    interno = getattr(model, "base", model)
    if not hasattr(interno, "contributions") or not hasattr(interno, "design_matrix"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"el modelo cargado para la base '{basis}' ('{_model_name(basis)}') no "
                "produce contribuciones por feature. Solo los modelos de arbol las "
                "emiten; cargar un LightGBM."
            ),
        )

    future = _future_index(panel, [req.series_id], cfg.FORECAST.horizon)
    fila = future[future[S.DATE] == pd.Timestamp(req.dt)]
    if fila.empty:
        disponibles = sorted({pd.Timestamp(d).date().isoformat() for d in future[S.DATE]})
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"la fecha {req.dt} no esta en el horizonte que el modelo puede "
                f"predecir. Disponibles: {disponibles}"
            ),
        )

    X = interno.design_matrix(fila)
    aportes, base_value = interno.contributions(X)
    prediccion = float(model.predict(fila).iloc[0])

    serie = aportes.iloc[0]
    orden = serie.abs().sort_values(ascending=False).head(req.top_k).index
    valores = X.iloc[0]
    contribuciones = [
        sc.ShapContribution(
            feature=str(f),
            value=_opt_float(valores.get(f)),
            contribution=float(serie[f]),
        )
        for f in orden
    ]

    return sc.ExplainResponse(
        series=refs[req.series_id],
        dt=req.dt,
        basis=sc.Basis(basis),
        model_name=_model_name(basis),
        quantile=getattr(interno, "_explainable_quantile", lambda: None)(),
        base_value=base_value,
        prediction=prediccion,
        contributions=contribuciones,
    )


@app.get("/products/map", response_model=sc.ProductMap, tags=["datos"])
def products_map() -> sc.ProductMap:
    """Proyeccion 2D del catalogo de productos.

    Es una proyeccion medida, no un dibujo: PCA sobre seis features de
    comportamiento de demanda por producto, con la varianza explicada en la
    respuesta para que la pantalla pueda declarar cuanto del fenomeno cabe en dos
    dimensiones. PCA y no UMAP porque es lineal y reproducible: un mapa que cambia
    de forma entre corridas no sirve como evidencia.
    """
    from blindside.unsupervised import embeddings as emb

    panel = _require_panel()
    puntos, varianza = emb.project_products(panel)
    return sc.ProductMap(
        method="pca",
        features=list(emb.FEATURES),
        explained_variance=varianza,
        points=[
            sc.ProductPoint(
                product_id=int(r[S.PRODUCT_ID]),
                x=float(r["x"]),
                y=float(r["y"]),
                rotation_band=str(r["rotation_band"]),
                demanda_media=float(r["demanda_media"]),
                tasa_quiebre=float(r["tasa_quiebre"]),
                n_series=int(r["n_series"]),
            )
            for _, r in puntos.iterrows()
        ],
    )


@app.get("/backtest/breakdown", response_model=sc.BacktestBreakdown, tags=["evaluacion"])
def backtest_breakdown() -> sc.BacktestBreakdown:
    """El backtest desagregado por origen, por horizonte y por banda de rotacion.

    Los datos ya estaban en el parquet; esto los expone. El agregado solo no
    alcanza: la metodologia prohibe el numero unico porque un promedio bueno
    esconde un origen catastrofico, y es justamente el origen malo el que despues
    pasa en produccion.
    """
    from blindside.evaluate import metrics as M
    from blindside.validation.splits import rotation_bands

    result = _require_backtest()
    panel = STATE.get("panel")

    por_origen = M.metrics_by_origin(result)
    origenes = [
        sc.OriginMetric(
            model_name=str(r[C_MODEL]),
            origin=int(r[C_ORIGIN]),
            origin_date=pd.Timestamp(r[C_ORIGIN_DATE]).date(),
            metric=metric,
            value=float(r[metric]),
        )
        for _, r in por_origen.iterrows()
        for metric in _METRICAS_VISIBLES
        if metric in por_origen.columns and pd.notna(r[metric])
    ]

    por_horizonte = M.metrics_by_horizon(result)
    horizontes = [
        sc.HorizonMetric(
            model_name=str(r[C_MODEL]),
            h=int(r["h"]),
            metric=metric,
            value=float(r[metric]),
        )
        for _, r in por_horizonte.iterrows()
        for metric in _METRICAS_VISIBLES
        if metric in por_horizonte.columns and pd.notna(r[metric])
    ]

    bandas: list[sc.BandMetric] = []
    if panel is not None:
        # Las bandas se definen con el train del primer origen, nunca con la serie
        # completa: elegir los grupos sabiendo el resultado seria trampa.
        primer_origen = pd.Timestamp(result[C_ORIGIN_DATE].min())
        train = panel[panel[S.DATE] <= primer_origen]
        if not train.empty:
            bands = rotation_bands(train, target=S.DEMAND_LATENT)
            tabla = M.metrics_by_group(result, bands, name="rotation_band")
            bandas = [
                sc.BandMetric(
                    model_name=str(r[C_MODEL]),
                    band=str(r["rotation_band"]),
                    metric=metric,
                    value=float(r[metric]),
                    n=int(r.get("n", 0)),
                )
                for _, r in tabla.iterrows()
                for metric in _METRICAS_VISIBLES
                if metric in tabla.columns and pd.notna(r[metric])
            ]

    return sc.BacktestBreakdown(
        target=S.DEMAND_LATENT,
        horizon=cfg.FORECAST.horizon,
        n_origins=int(result[C_ORIGIN].nunique()),
        origins=origenes,
        horizons=horizontes,
        bands=bandas,
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
