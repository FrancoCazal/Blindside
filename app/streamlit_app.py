"""Dashboard Streamlit · la superficie minima que satisface el requisito de deploy.

Es la **red de seguridad** de la entrega (seccion 13 del plan): no depende del
frontend de React ni de que la API este levantada, lee los artefactos del repo
directamente. Si el dia de la defensa falla el deploy, esto sigue funcionando.

Las pantallas siguen el orden de la seccion 10 del plan. Lo que no existe todavia
aparece como pendiente explicito en vez de con datos inventados: un dashboard con
numeros de relleno es peor que uno incompleto, porque el panel pregunta de donde
sale cada numero.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# El paquete se instala con `pip install -e .`, pero si alguien corre el archivo
# sin instalarlo conviene que funcione igual en vez de fallar con ImportError.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from blindside import config as cfg  # noqa: E402
from blindside.data import loaders  # noqa: E402
from blindside.data import schema as S  # noqa: E402

st.set_page_config(
    page_title="blindside-core",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------
# Carga con cache
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Cargando panel...")
def load_demand() -> tuple[pd.DataFrame | None, str]:
    """Panel con demanda latente. Devuelve tambien de que capa salio."""
    try:
        path = loaders.resolve_path("demand")
        return loaders.load_demand(path=path), str(path.parent.name)
    except loaders.DataNotAvailableError as exc:
        return None, str(exc)


@st.cache_data(show_spinner=False)
def load_backtest() -> pd.DataFrame | None:
    for name in ("backtest_models.parquet", "backtest_baselines.parquet"):
        path = cfg.REPORTS / name
        if path.exists():
            return pd.read_parquet(path)
    return None


@st.cache_data(show_spinner=False)
def load_markdown(name: str) -> str | None:
    path = cfg.REPORTS / name
    return path.read_text(encoding="utf-8") if path.exists() else None


@st.cache_data(show_spinner="Calculando triage...")
def load_triage(_layer: str) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Señales por serie y resumen por grupo. Cacheado porque recorre el panel entero.

    El `_layer` no se usa adentro: esta en la firma para que el cache se invalide si se
    cambia de capa de datos. Sin eso, pasar de `sample` a `processed` mostraria el
    triage de la capa anterior.
    """
    from blindside.evaluate import triage as T

    panel, _ = load_demand()
    if panel is None:
        return None, None
    señales = T.series_signals(panel, load_backtest())
    marcado = T.triage(señales)
    return marcado, T.resumen_por_grupo(marcado)


# --------------------------------------------------------------------------
# Pantallas
# --------------------------------------------------------------------------
def screen_triage(panel: pd.DataFrame, layer: str) -> None:
    """Portada: de las 3.066 series, cuales mirar primero y por que motivo.

    **No es un ranking ni un top 10, y la razon esta medida.** El costo esta repartido
    -- el top 10 % de series concentra 26,5 % del costo de newsvendor, contra el 70-80 %
    que tendria un Pareto fuerte -- asi que un corte en la posicion 10 seria arbitrario.
    Y los ejes de criticidad son ortogonales: el solapamiento entre el top 50 por
    volumen y el top 50 por error normalizado es de 0 series. Un score compuesto los
    promediaria y perderia lo unico accionable, que es **por que** entro cada serie.
    """
    from blindside.evaluate import triage as T

    st.header("Qué mirar primero")
    if layer == "sample":
        st.warning(
            "Estás viendo la **muestra commiteada** de `data/sample/`, no el "
            "subconjunto completo. Correr `make data && make recover`.",
            icon="⚠️",
        )

    marcado, resumen = load_triage(layer)
    if marcado is None or resumen is None or resumen.empty:
        st.info("Sin datos para el triage.")
        return

    total = len(marcado)
    con_motivo = int((marcado["n_motivos"] > 0).sum())
    n_no_confiable = (
        int((marcado["mase_serie"] > 1).sum()) if "mase_serie" in marcado.columns else None
    )

    # Sin `delta`: la flecha de Streamlit significa "cambió respecto de antes", y acá no
    # hay comparación temporal. Una flecha verde al lado de "26 % del catálogo pide
    # atención" sugiere una mejora que nadie midió.
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Series en cartera", f"{total:,}")
    c2.metric("Piden atención", f"{con_motivo:,}")
    c3.metric("Con más de un motivo", f"{int((marcado['n_motivos'] >= 2).sum()):,}")
    c4.metric(
        "Modelo no confiable",
        f"{n_no_confiable:,}" if n_no_confiable is not None else "sin medir",
    )
    c1.caption("tienda × producto")
    c2.caption(f"**{con_motivo / total:.1%}** del catálogo")
    c3.caption("más de un eje a la vez")
    c4.caption(
        "peor que el naive estacional" if n_no_confiable is not None else "falta `make models`"
    )

    st.caption(
        f"El triage aísla el **{con_motivo / total:.1%}** del catálogo. Que la mayoría no "
        "tenga motivo es el resultado buscado: una alerta que marca un tercio del "
        "catálogo no prioriza nada. Los umbrales están medidos, no elegidos — ver "
        "`docs/decisiones.md` D25."
    )

    st.subheader("Los motivos, y cuánto pesa cada uno")
    # ProgressColumn y no `Styler.background_gradient`: el gradiente de pandas exige
    # matplotlib, que **no esta en la imagen de servicio** (queda afuera a proposito
    # porque pesa y no hace falta para responder /forecast). Verificado dentro del
    # contenedor: importarlo tumbaria la pagina en el demo y no en local.
    tabla_grupos = resumen[
        ["grupo", "series", "share_series", "share_volumen", "solo_este_motivo"]
    ].copy()
    # A porcentaje: `NumberColumn` con formato `%%` no escala, solo agrega el signo.
    tabla_grupos["share_series"] *= 100
    tabla_grupos["share_volumen"] *= 100
    st.dataframe(
        tabla_grupos,
        use_container_width=True,
        hide_index=True,
        column_config={
            "grupo": st.column_config.TextColumn("Motivo"),
            "series": st.column_config.NumberColumn("Series", format="%d"),
            "share_series": st.column_config.NumberColumn("% del catálogo", format="%.1f %%"),
            "share_volumen": st.column_config.ProgressColumn(
                "% del volumen", format="%.1f %%", min_value=0.0, max_value=100.0
            ),
            "solo_este_motivo": st.column_config.NumberColumn(
                "Sólo por este motivo",
                format="%d",
                help="Series que ese grupo es el único en detectar.",
            ),
        },
    )
    st.caption(
        "**Series y volumen no son lo mismo**, y las dos hacen falta: un motivo puede "
        "tocar pocas series y mucha plata. La última columna dice cuántas entran **sólo** "
        "por ese motivo, o sea las que ese grupo es el único en detectar."
    )

    st.subheader("Qué significa cada motivo")
    for g in T.GRUPOS:
        if g.clave not in marcado.columns:
            continue
        n = int(marcado[g.clave].sum())
        with st.expander(f"**{g.etiqueta}** · {n:,} series", expanded=False):
            st.markdown(f"**Qué significa.** {g.que_significa}")
            st.markdown(f"**Qué hacer.** {g.que_hacer}")

    st.subheader("Las series a revisar")
    motivos = {g.etiqueta: g.clave for g in T.GRUPOS if g.clave in marcado.columns}
    elegido = st.selectbox(
        "Filtrar por motivo",
        ["Todas las que piden atención", *motivos],
        help="Cada motivo pide una acción distinta, así que se revisan por separado.",
    )

    vista = (
        marcado[marcado["n_motivos"] > 0]
        if elegido == "Todas las que piden atención"
        else marcado[marcado[motivos[elegido]]]
    )
    if vista.empty:
        st.success("Ninguna serie cae en este grupo.")
        return

    cols = [
        c
        for c in ("demanda_media", "mase_serie", "frac_estimada", "racha_vigente")
        if c in vista.columns
    ]
    tabla = vista.sort_values(["n_motivos", "demanda_media"], ascending=False).head(25)[
        [*cols, "n_motivos", T.MOTIVO_COL]
    ]
    config = {
        "series_id": st.column_config.TextColumn("Serie"),
        "demanda_media": st.column_config.NumberColumn("Demanda media", format="%.3f"),
        "mase_serie": st.column_config.NumberColumn(
            "MASE de la serie",
            format="%.3f",
            help="Por encima de 1 el modelo le pierde al naive estacional.",
        ),
        "frac_estimada": st.column_config.ProgressColumn(
            "Señal estimada", format="%.0f %%", min_value=0.0, max_value=100.0
        ),
        "racha_vigente": st.column_config.NumberColumn("Días quebrado", format="%d"),
        "n_motivos": st.column_config.NumberColumn("Motivos", format="%d"),
        T.MOTIVO_COL: st.column_config.TextColumn("Por qué", width="large"),
    }
    mostrar = tabla.reset_index()
    if "frac_estimada" in mostrar.columns:
        mostrar["frac_estimada"] *= 100
    st.dataframe(mostrar, use_container_width=True, hide_index=True, column_config=config)
    st.caption(
        f"{len(vista):,} series en este filtro; se muestran las 25 con más motivos. "
        "Ordenadas por cantidad de motivos y después por volumen, **no por un score**: "
        "sumar ejes ortogonales daría un número sin significado."
    )

    st.download_button(
        "Descargar el filtro completo (CSV)",
        vista.reset_index().to_csv(index=False).encode("utf-8"),
        file_name=f"triage_{elegido.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )


def screen_overview(panel: pd.DataFrame, layer: str) -> None:
    st.header("Vista general")

    if layer == "sample":
        st.warning(
            "Estas viendo la **muestra commiteada** de `data/sample/`, no el "
            "subconjunto completo. Sirve para que el repo corra sin descargar nada; "
            "no para leer resultados. Correr `make data && make recover`.",
            icon="⚠️",
        )

    summary = S.describe_censoring(panel)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Series", f"{int(summary['n_series']):,}")
    c2.metric("Dias", int(summary["n_days"]))
    c3.metric("Dias con quiebre", f"{summary['share_censored_days']:.1%}")
    c4.metric(
        "Horas de quiebre (media, dias censurados)",
        f"{summary['mean_oos_hours_when_censored']:.1f} / {len(cfg.CENSORING.open_hours)}",
    )

    hourly_share = (
        summary["share_censored_days"]
        * summary["mean_oos_hours_when_censored"]
        / len(cfg.CENSORING.open_hours)
    )
    st.caption(
        f"Eso son **{hourly_share:.1%} de horas comerciales en quiebre**, que reproduce "
        "el ≈20 % que declara la ficha del dataset. Es la comprobacion de que la "
        "ventana comercial asumida (indices 6..21, 16 franjas) es la correcta."
    )

    st.subheader("Recuperacion de demanda censurada")
    from blindside.decision.censoring import censoring_report

    report = censoring_report(panel)
    st.dataframe(
        report.style.format(
            {
                "demanda_observada": "{:.4f}",
                "demanda_latente": "{:.4f}",
                "uplift_pct": "{:+.2f} %",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Los dias limpios tienen uplift **exactamente 0 %** por diseno: son la verdad "
        "de terreno con la que se mide el sesgo, asi que corregirlos destruiria la "
        "medicion. La correccion vive solo en los dias con quiebre."
    )

    result = load_backtest()
    if result is None:
        st.info("Sin backtest todavia. Correr `make backtest` o `make models`.")
        return

    from blindside.evaluate import metrics as M
    from blindside.models.baselines import REFERENCE_BASELINE

    summary_tbl = M.summarize(result)
    try:
        improvement = M.improvement_vs_baseline(
            summary_tbl, baseline=REFERENCE_BASELINE, metric="mase"
        )
    except KeyError:
        st.info(f"El backtest no incluye `{REFERENCE_BASELINE}`, no hay con que comparar.")
        return

    best = improvement.iloc[0]
    st.subheader("Contra el objetivo")
    c1, c2, c3 = st.columns(3)
    c1.metric("Mejor modelo", str(best["model"]))
    c2.metric("MASE", f"{best['mean']:.4f}", f"{best['improvement_pct']:+.1f} % vs naive est.")
    c3.metric(
        "Objetivo 20 %",
        "cumple" if bool(best["meets_target_20pct"]) else "no cumple",
    )
    st.dataframe(
        improvement.style.format(
            {
                "mean": "{:.4f}",
                "std": "{:.4f}",
                "worst_origin": "{:.4f}",
                "improvement_pct": "{:+.1f} %",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "La columna **peor origen** es la que importa para operar: responde que pasa "
        "el mes que sale mal. Un promedio bueno puede esconder un origen catastrofico."
    )


def screen_series(panel: pd.DataFrame) -> None:
    st.header("Serie individual")

    index = S.series_index(panel)
    cities = sorted(index[S.CITY_ID].unique())
    city = st.selectbox("Ciudad", cities)
    stores = sorted(index.loc[index[S.CITY_ID] == city, S.STORE_ID].unique())
    store = st.selectbox("Tienda", stores)
    products = sorted(index.loc[index[S.STORE_ID] == store, S.PRODUCT_ID].unique())
    product = st.selectbox("Producto", products)

    sid = f"{store}_{product}"
    series = panel[panel[S.SERIES_ID] == sid].sort_values(S.DATE)
    if series.empty:
        st.warning("Esa combinacion no esta en el panel.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Demanda observada media", f"{series[S.SALE_AMOUNT].mean():.3f}")
    c2.metric("Demanda latente media", f"{series[S.DEMAND_LATENT].mean():.3f}")
    c3.metric("Dias con quiebre", f"{series[S.IS_CENSORED].mean():.1%}")

    chart = series.set_index(S.DATE)[[S.SALE_AMOUNT, S.DEMAND_LATENT]].rename(
        columns={S.SALE_AMOUNT: "venta observada", S.DEMAND_LATENT: "demanda latente"}
    )
    st.line_chart(chart, height=340)
    st.caption(
        "Donde las dos lineas se separan hubo quiebre: la venta registrada fue cero o "
        "parcial pero la demanda no lo era. Entrenar sobre la linea de abajo produce el "
        "**efecto spiral-down** — se pide de menos, hay mas quiebres, se observa menos "
        "demanda, se pide de menos todavia."
    )

    st.subheader("Horas de quiebre por dia")
    st.bar_chart(series.set_index(S.DATE)[[S.OOS_HOURS_OPEN]], height=200)


def screen_censoring() -> None:
    st.header("Ablación de censura")
    body = load_markdown("censoring_ablation.md")
    if body is None:
        st.info("Sin ablacion todavia. Correr `make ablation`.")
        return
    st.markdown(body)


def screen_models() -> None:
    st.header("Comparativa de modelos")
    result = load_backtest()
    if result is None:
        st.info("Sin backtest todavia. Correr `make models`.")
        return

    from blindside.evaluate import contracts as C
    from blindside.evaluate import metrics as M

    st.subheader("Por origen de backtest")
    by_origin = M.metrics_by_origin(result)
    pivot = by_origin.pivot(index=C.ORIGIN, columns=C.MODEL, values="mase")
    st.line_chart(pivot, height=320)
    st.caption(
        "Una linea por modelo a traves de los 8 origenes. La dispersion entre origenes "
        "es parte del resultado, no ruido a promediar."
    )

    st.subheader("Degradacion por horizonte")
    by_h = M.metrics_by_horizon(result)
    st.line_chart(by_h.pivot(index=C.HORIZON_STEP, columns=C.MODEL, values="mase"), height=320)
    st.caption(
        "Responde cuanto dura el modelo antes de necesitar reentrenamiento. Ojo con "
        "leerla como monotona: con estacionalidad semanal el error en h=7 puede bajar "
        "legitimamente, porque el objetivo cae el mismo dia de la semana que el origen."
    )

    st.subheader("Por banda de rotacion")
    st.info(
        "Se calcula en el reporte de `make models` (`reports/metrics.md`). Que el modelo "
        "complejo no le gane al ingenuo en baja rotacion es un resultado esperado y "
        "publicado, no un fracaso."
    )


def screen_decision(panel: pd.DataFrame) -> None:
    st.header("Reposición")

    st.markdown(
        "La cantidad a reponer sale de la economia, no del pronostico puntual. Con "
        "`Cu` el costo de quedarse corto y `Co` el de quedarse largo — que en "
        "perecederos es **perdida total al vencimiento**, no capital inmovilizado — el "
        "cuantil optimo es la fraccion critica `q* = Cu / (Cu + Co)`."
    )

    c1, c2 = st.columns(2)
    cu = c1.number_input("Cu · costo de quedarse corto", 0.1, 20.0, 1.0, 0.1)
    co = c2.number_input("Co · costo de quedarse largo", 0.1, 20.0, 0.6, 0.1)

    from blindside.decision.newsvendor import critical_fraction

    q_star = critical_fraction(cu=cu, co=co)
    st.metric("Cuantil critico q*", f"{q_star:.3f}")
    if q_star > 0.5:
        st.caption(
            f"q* = {q_star:.3f} está por encima de la mediana: quedarse corto duele mas "
            "que quedarse largo, asi que la orden optima es mayor que el pronostico "
            "puntual. La prediccion del modelo cuantilico en q* **es** la orden."
        )
    else:
        st.caption(
            f"q* = {q_star:.3f} está por debajo de la mediana: el sobrante duele mas que "
            "el quiebre, asi que conviene pedir menos que el pronostico puntual."
        )

    artifact = cfg.ARTIFACTS / "model.joblib"
    if not artifact.exists():
        st.info(
            f"Sin artefacto en `{artifact.relative_to(cfg.ROOT)}`. La tabla de "
            "cantidades sugeridas necesita un modelo cuantilico serializado. Es lo "
            "unico que falta para cerrar esta pantalla de punta a punta."
        )
        return

    from blindside.models.base import Forecaster

    model = Forecaster.load(artifact)
    if not getattr(model, "supports_quantiles", False):
        st.warning(
            f"El artefacto cargado (`{model.name}`) no produce cuantiles, asi que no "
            "puede emitir una orden derivada de la economia. Serializar un "
            "`LightGBMQuantileForecaster`."
        )
        return

    st.success(f"Modelo `{model.name}` cargado, entrenado hasta {model.last_train_date}.")


def screen_leakage() -> None:
    st.header("Validación y antifugas")
    st.markdown(
        """
El checklist antifugas de la metodologia esta implementado como **tests que fallan
si hay fuga**. Un README que dice "evite leakage" no prueba nada.

```bash
make test-leakage      # los ocho items, con caso negativo cada uno
```

| Item | Verificacion |
|---|---|
| Sin features posteriores a `t` | Constantes dentro de cada `(serie, origen)` |
| Lags por grupo y ordenados | El lag de la primera fila de la serie es nulo |
| Sin agregados globales | Ninguna feature iguala un promedio del panel |
| Sin target encoding del futuro | Ninguna correlaciona ≥ 0,999 con el target |
| El escalador se ajusta en train | Su media es la del fold, no la del panel |
| Test de shuffle | Al permutar el target, el error se derrumba |
| Alineacion del target | Correr el target un dia **empeora** la metrica |
| Test de fold | Train y test disjuntos, y el gap es el horizonte |

Dos barreras son **estructurales** y no dependen de acordarse de nada:

1. Un modelo recibe `history` (hasta el origen) y un `future` **sin columna de
   target**. No tiene desde donde mirar el futuro ni por accidente.
2. Las features se calculan una sola vez por `(serie, origen)` y se replican para
   los `h` objetivos. Una feature que dependa de la fecha objetivo cambiaria
   dentro del grupo, y eso es exactamente lo que el primer test detecta.
        """
    )
    st.caption(
        "El test de alineacion reemplazo al de monotonia del horizonte, que en esta "
        "serie no probaba nada: con estacionalidad semanal el error en h=7 puede "
        "bajar legitimamente porque el objetivo cae el mismo dia de la semana que "
        "el origen."
    )


def screen_report() -> None:
    st.header("Reporte de metricas")
    body = load_markdown("metrics.md")
    if body is None:
        st.info("Sin reporte todavia. Correr `make models`.")
        return
    st.markdown(body)


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
def main() -> None:
    st.sidebar.title("📦 blindside-core")
    st.sidebar.caption(
        "Pronóstico de demanda de perecederos con recuperación de demanda censurada "
        "y capa de decisión de reposición."
    )

    panel, layer = load_demand()
    if panel is None:
        st.error(
            "No hay datos de demanda recuperada.\n\n"
            "```bash\nmake data      # descarga y submuestrea\n"
            "make recover   # recupera la demanda censurada\n```\n\n"
            f"Detalle: {layer}"
        )
        st.stop()

    screens = {
        "Qué mirar primero": lambda: screen_triage(panel, layer),
        "Vista general": lambda: screen_overview(panel, layer),
        "Serie individual": lambda: screen_series(panel),
        "Ablación de censura": screen_censoring,
        "Comparativa de modelos": screen_models,
        "Reposición": lambda: screen_decision(panel),
        "Validación y antifugas": screen_leakage,
        "Reporte completo": screen_report,
    }
    choice = st.sidebar.radio("Pantalla", list(screens))
    st.sidebar.divider()
    st.sidebar.caption(
        f"Capa de datos: `{layer}` · horizonte {cfg.FORECAST.horizon} d · "
        f"{cfg.FORECAST.n_origins} orígenes"
    )
    st.sidebar.caption(
        "Datos: [FreshRetailNet-50K](https://huggingface.co/datasets/"
        "Dingdong-Inc/FreshRetailNet-50K) (Dingdong-Inc, CC BY 4.0). `sale_amount` "
        "esta normalizado por un coeficiente no divulgado, asi que las magnitudes "
        "son adimensionales."
    )
    screens[choice]()


if __name__ == "__main__":
    main()
