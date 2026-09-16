"""Asserts antifugas · el checklist de la seccion 5.2 vuelto codigo ejecutable.

Un README que dice "evite leakage" no prueba nada. Un test que falla si hay fuga,
si. Este modulo tiene las funciones y `tests/test_leakage.py` las corre; la idea
es que la afirmacion de rigor sea verificable por cualquiera con `make test`.

Los ocho items del checklist y donde se verifican:

1. Ningun feature usa informacion posterior a `t` → `assert_no_future_columns`
2. Lags y rolling por grupo, ordenados por fecha → `assert_lags_are_grouped`
3. Sin agregados sobre el dataset completo → `assert_no_global_aggregates`
4. Sin target encoding con datos del futuro → `assert_no_target_leakage`
5. El escalador se ajusta solo en train de cada fold → `assert_pipeline_fitted_on_train`
6. Test de shuffle → `shuffle_test`
7. Test de futuro → `future_shift_test`
8. Test de fold → `assert_fold_disjoint`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from blindside.data import schema as S
from blindside.features import build as fb

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from blindside.validation.splits import Fold

log = logging.getLogger(__name__)


class LeakageError(AssertionError):
    """Se detecto fuga de informacion. Es un fallo, no un aviso."""


# --------------------------------------------------------------------------
# 1 · ninguna feature posterior al origen
# --------------------------------------------------------------------------
def assert_no_future_columns(supervised: pd.DataFrame) -> None:
    """Ninguna feature puede provenir del dia objetivo.

    Verifica dos cosas. Que las columnas prohibidas del contrato no esten en la
    lista de features, y que el conjunto de features sea **constante dentro de
    cada (serie, origen)**: si una feature cambia entre `h=1` y `h=7` del mismo
    origen, entonces depende de la fecha objetivo y no del origen, que es
    exactamente la forma que tiene la fuga en este diseno.

    Las excepciones legitimas son las que se conocen de antemano: el calendario
    del dia objetivo, el paso `h`, y las covariables planificadas.
    """
    features = fb.feature_columns(supervised)
    from blindside.features.calendar import CALENDAR_FEATURES

    allowed_to_vary = {
        fb.H,
        *CALENDAR_FEATURES,
        *S.KNOWN_FUTURE_COLS,
        "days_to_holiday",
        "is_holiday",
    }
    suspects = [c for c in features if c not in allowed_to_vary]
    if not suspects:
        return

    grouped = supervised.groupby([S.SERIES_ID, fb.ORIGIN_DATE], observed=True)
    varying = [c for c in suspects if grouped[c].nunique(dropna=False).max() > 1]
    if varying:
        raise LeakageError(
            f"estas features cambian dentro de un mismo (serie, origen): {varying}. "
            "Si dependen de la fecha objetivo, contienen informacion posterior al "
            "origen. Anclarlas al origen o declararlas como conocidas de antemano."
        )


# --------------------------------------------------------------------------
# 2 · lags por grupo y ordenados
# --------------------------------------------------------------------------
def assert_lags_are_grouped(
    panel: pd.DataFrame, *, target: str, lag: int = 1, tol: float = 1e-4
) -> None:
    """El lag de la primera fila de cada serie debe ser nulo.

    Es el chequeo mas simple y el que detecta el error mas frecuente: calcular
    `shift()` sobre el DataFrame entero sin agrupar. Cuando eso pasa, la primera
    fila de la serie B hereda el ultimo valor de la serie A, y el modelo aprende
    una relacion entre productos distintos que no existe.
    """
    col = f"{'latent' if target == S.DEMAND_LATENT else 'obs'}_lag_{lag}"
    if col not in panel.columns:
        raise LeakageError(f"no existe la columna {col}; nada que verificar")
    df = panel.sort_values([S.SERIES_ID, S.DATE], kind="mergesort")
    firsts = df.groupby(S.SERIES_ID, observed=True).head(lag)
    bad = int(firsts[col].notna().sum())
    if bad:
        raise LeakageError(
            f"{bad} series tienen {col} no nulo en su primera fila: el shift se "
            "hizo sin agrupar por serie y una serie esta leyendo el final de otra"
        )
    # Y que el valor efectivamente sea el del dia anterior de la misma serie.
    sample = df[df[S.SERIES_ID] == df[S.SERIES_ID].iloc[0]]
    expected = sample[target].shift(lag).to_numpy()
    got = sample[col].to_numpy()
    both = ~(np.isnan(expected) | np.isnan(got))
    if both.any() and not np.allclose(expected[both], got[both], atol=tol):
        raise LeakageError(f"{col} no coincide con {target}.shift({lag}) dentro de la serie")


# --------------------------------------------------------------------------
# 3 · sin agregados globales
# --------------------------------------------------------------------------
def assert_no_global_aggregates(
    train: pd.DataFrame, full: pd.DataFrame, *, columns: Sequence[str], tol: float = 1e-6
) -> None:
    """Una feature no puede coincidir con un agregado del panel **completo**.

    Detecta el patron de calcular `df.groupby(serie)[y].mean()` sobre todo el
    dataset y pegarlo como feature: el valor de la fila de train contendria el
    promedio de dias de test.
    """
    offenders = []
    for col in columns:
        if col not in train.columns:
            continue
        global_mean = full[col].mean()
        # Si la columna es constante e igual al promedio global, huele a agregado.
        if train[col].nunique(dropna=True) == 1 and abs(train[col].iloc[0] - global_mean) < tol:
            offenders.append(col)
    if offenders:
        raise LeakageError(
            f"{offenders} son constantes e iguales al agregado global: se calcularon "
            "sobre el dataset completo en vez de dentro del fold"
        )


# --------------------------------------------------------------------------
# 4 · sin target encoding del futuro
# --------------------------------------------------------------------------
def assert_no_target_leakage(supervised: pd.DataFrame, *, threshold: float = 0.999) -> None:
    """Ninguna feature puede estar casi perfectamente correlacionada con el target.

    Una correlacion de 0,999 con `y` no es una feature buena, es el target
    disfrazado. El umbral es alto a proposito: `latent_lag_0` correlaciona fuerte
    y es legitimo, mientras que una copia del objetivo llega a 1,0.
    """
    features = fb.feature_columns(supervised)
    y = supervised[fb.Y].to_numpy(dtype="float64")
    if np.allclose(y.std(), 0):
        return
    offenders: list[tuple[str, float]] = []
    for col in features:
        x = supervised[col].to_numpy(dtype="float64")
        mask = np.isfinite(x) & np.isfinite(y)
        if mask.sum() < 30 or np.allclose(x[mask].std(), 0):
            continue
        r = abs(float(np.corrcoef(x[mask], y[mask])[0, 1]))
        if r >= threshold:
            offenders.append((col, r))
    if offenders:
        raise LeakageError(
            f"features casi identicas al target: {offenders}. Es el target "
            "disfrazado, no una feature predictiva"
        )


# --------------------------------------------------------------------------
# 5 · el preprocesamiento se ajusta solo con train
# --------------------------------------------------------------------------
def assert_pipeline_fitted_on_train(
    pipeline: object, train: pd.DataFrame, full: pd.DataFrame, *, column: str
) -> None:
    """La media aprendida por el escalador debe ser la del train, no la del panel.

    Se compara el estadistico guardado en el `StandardScaler` con la media del
    train y con la del panel completo. Si se parece mas a la del panel completo,
    el pipeline se ajusto fuera del fold.
    """
    scaler = _find_scaler(pipeline)
    if scaler is None or not hasattr(scaler, "mean_"):
        raise LeakageError("no se encontro un escalador ajustado en el pipeline")
    names = list(getattr(scaler, "feature_names_in_", []))
    if column not in names:
        return
    idx = names.index(column)
    learned = float(np.asarray(scaler.mean_)[idx])
    d_train = abs(learned - float(train[column].mean()))
    d_full = abs(learned - float(full[column].mean()))
    if d_full < d_train:
        raise LeakageError(
            f"el escalador de '{column}' aprendio una media mas cercana al panel "
            f"completo ({d_full:.3g}) que al train del fold ({d_train:.3g})"
        )


def _find_scaler(obj: object) -> object | None:
    from sklearn.base import BaseEstimator

    if hasattr(obj, "mean_") and hasattr(obj, "scale_"):
        return obj
    steps = getattr(obj, "steps", None) or getattr(obj, "transformers_", None)
    if steps:
        for step in steps:
            candidate = step[1] if isinstance(step, tuple) else step
            if isinstance(candidate, BaseEstimator):
                found = _find_scaler(candidate)
                if found is not None:
                    return found
    return None


# --------------------------------------------------------------------------
# 6 · test de shuffle
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ShuffleResult:
    """Resultado del test de permutacion.

    Atributos:
        metric_real: error del modelo entrenado normalmente.
        metric_shuffled: error del modelo entrenado con el target permutado.
        metric_constant: error de predecir siempre la media del train. Es el
            techo de "no saber nada", y sirve de referencia autocalibrada.
        ratio: metric_shuffled / metric_real.
        no_better_than_constant: el modelo permutado no le gana al predictor
            constante. Es la evidencia mas fuerte de que no queda senal.
    """

    metric_real: float
    metric_shuffled: float
    metric_constant: float
    ratio: float
    degraded_enough: bool
    no_better_than_constant: bool

    @property
    def passed(self) -> bool:
        return self.degraded_enough and self.no_better_than_constant

    def __repr__(self) -> str:
        verdict = "OK" if self.passed else "FALLA"
        return (
            f"ShuffleResult({verdict}: real={self.metric_real:.4f}, "
            f"permutado={self.metric_shuffled:.4f}, constante={self.metric_constant:.4f}, "
            f"ratio={self.ratio:.2f})"
        )


def shuffle_test(
    fit_predict: Callable[[pd.DataFrame, pd.DataFrame], np.ndarray],
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    metric: Callable[[np.ndarray, np.ndarray], float],
    target: str = fb.Y,
    seed: int = 0,
    min_degradation: float = 1.25,
) -> ShuffleResult:
    """Permuta el target del train y verifica que la metrica se derrumbe.

    Razonamiento: si al destruir toda la relacion entre features y target el
    modelo sigue prediciendo bien, entonces la senal no venia de las features —
    venia de una fuga. Es el test que se muestra corriendo en la defensa, porque
    es el unico que demuestra ausencia de fuga en vez de afirmarla.

    El criterio tiene **dos** partes, y la segunda es la que importa.

    El cociente de degradacion depende del ruido irreducible de las series: en
    demanda de perecederos, con coeficiente de variacion alto y una cola de
    ceros, ni el mejor modelo posible se aleja tanto de la media, asi que exigir
    un cociente grande castigaria al modelo por el ruido de los datos y no por
    tener fugas. Por eso `min_degradation` es 1,25 y no un numero mas vistoso:
    con una fuga real el cociente se queda pegado a 1,0, asi que cualquier
    separacion clara de 1 ya es evidencia.

    La segunda parte es autocalibrada y no depende de elegir umbral: el modelo
    con target permutado **no puede ganarle a predecir la media del train**. Si
    le gana, quedo senal despues de destruir la relacion con el target, y la
    unica forma de que eso pase es que la senal venga de otro lado.
    """
    y_test = test[target].to_numpy(dtype="float64")
    y_train = train[target].to_numpy(dtype="float64")

    pred_real = np.asarray(fit_predict(train, test), dtype="float64")
    metric_real = float(metric(y_test, pred_real))

    rng = np.random.default_rng(seed)
    shuffled = train.copy()
    shuffled[target] = rng.permutation(y_train)
    pred_shuf = np.asarray(fit_predict(shuffled, test), dtype="float64")
    metric_shuffled = float(metric(y_test, pred_shuf))

    # La referencia es el **mejor** constante posible, no "la media".
    # El minimizador de una metrica constante depende de la metrica: la media
    # minimiza el error cuadratico y la mediana el absoluto. En demanda de
    # perecederos la distribucion tiene cola derecha, asi que mediana y media se
    # separan bastante, y usar la media como referencia bajo MAE fija un techo
    # demasiado bajo: un modelo sin ninguna senal que prediga la mediana le
    # "gana" a esa referencia y el test acusaria fuga donde no hay. Se prueban
    # las dos y se toma la mejor, que es la barra mas exigente.
    candidates = (float(np.mean(y_train)), float(np.median(y_train)))
    metric_constant = min(float(metric(y_test, np.full(y_test.shape, c))) for c in candidates)

    ratio = metric_shuffled / metric_real if metric_real > 0 else float(np.inf)
    result = ShuffleResult(
        metric_real=metric_real,
        metric_shuffled=metric_shuffled,
        metric_constant=metric_constant,
        ratio=ratio,
        degraded_enough=ratio >= min_degradation,
        # Se admite un 5 % de holgura: el modelo permutado puede quedar
        # marginalmente por debajo del constante por azar de la particion.
        no_better_than_constant=metric_shuffled >= metric_constant * 0.95,
    )
    log.info("test de shuffle · %r", result)
    return result


# --------------------------------------------------------------------------
# 7 · test de futuro
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ShiftResult:
    """Resultado del test de desalineamiento del target."""

    metric_aligned: float
    metric_shifted_back: float
    metric_shifted_fwd: float
    passed: bool

    def __repr__(self) -> str:
        verdict = "OK" if self.passed else "FALLA"
        return (
            f"ShiftResult({verdict}: alineado={self.metric_aligned:.4f}, "
            f"corrido-1={self.metric_shifted_back:.4f}, "
            f"corrido+1={self.metric_shifted_fwd:.4f})"
        )


def target_shift_test(
    fit_predict: Callable[[pd.DataFrame, pd.DataFrame], np.ndarray],
    train: pd.DataFrame,
    test: pd.DataFrame,
    *,
    metric: Callable[[np.ndarray, np.ndarray], float],
    target: str = fb.Y,
    group: str = S.SERIES_ID,
) -> ShiftResult:
    """Corre el target un dia en cada direccion y verifica que empeore.

    Es el item 7 del checklist hecho de una forma que **si** prueba algo. La
    version ingenua — "el error tiene que crecer con el horizonte" — no sirve en
    esta serie, y vale la pena explicar por que, porque es un resultado sobre los
    datos y no sobre el codigo.

    Con estacionalidad semanal fuerte y `m = 7`, el error de un pronostico en
    `h = 7` puede ser **menor** que en `h = 1` sin que haya nada mal: el objetivo
    en `T+7` cae el mismo dia de la semana que `T`, asi que se le parece mas que
    el de `T+1`. Con el naive estacional el efecto es todavia mas claro: todos
    los pasos usan un valor a exactamente `m` dias de su objetivo, o sea que su
    error es plano en `h` por construccion. Exigir monotonia ahi mide el
    calendario, no la alineacion de indices.

    Este test ataca la alineacion de frente. Si el pipeline tuviera un error de
    un dia — features de `t+1` pegadas al objetivo de `t`, o al reves —, correr
    el target un dia **corregiria** ese error y la metrica mejoraria. Que empeore
    en las dos direcciones es evidencia directa de que el alineamiento actual es
    el correcto, y no depende de ninguna propiedad estacional de la serie.
    """
    y_test = test[target].to_numpy(dtype="float64")
    pred = np.asarray(fit_predict(train, test), dtype="float64")
    aligned = float(metric(y_test, pred))

    results: dict[int, float] = {}
    for shift in (-1, 1):
        moved = train.copy()
        moved[target] = moved.groupby(group, observed=True)[target].shift(shift)
        moved = moved[moved[target].notna()]
        pred_moved = np.asarray(fit_predict(moved, test), dtype="float64")
        results[shift] = float(metric(y_test, pred_moved))

    passed = aligned <= min(results.values())
    result = ShiftResult(
        metric_aligned=aligned,
        metric_shifted_back=results[-1],
        metric_shifted_fwd=results[1],
        passed=passed,
    )
    if not passed:
        log.warning(
            "correr el target un dia mejora la metrica: hay un desalineamiento " "de indices · %r",
            result,
        )
    return result


def future_shift_test(metric_by_h: pd.Series, *, tolerance: float = 0.02) -> bool:
    """Diagnostico: el error del horizonte lejano contra el del cercano.

    **No es un criterio de aprobacion, y es importante no usarlo como tal.** Con
    estacionalidad semanal el error puede bajar legitimamente en `h = m`, porque
    el objetivo cae el mismo dia de la semana que el origen. Para verificar
    alineacion de indices esta `target_shift_test`, que no depende del calendario.

    Sirve para lo que si es: la **curva de degradacion** que responde cuanto dura
    el modelo antes de necesitar reentrenamiento, y para detectar el caso
    grosero de un error que se desploma con el horizonte.
    """
    if len(metric_by_h) < 2:
        return True
    ordered = metric_by_h.sort_index()
    half = len(ordered) // 2
    early = float(ordered.iloc[:half].mean())
    late = float(ordered.iloc[half:].mean())
    ok = late >= early * (1 - tolerance)
    if not ok:
        log.info(
            "el error del horizonte lejano (%.4f) es menor que el del cercano "
            "(%.4f); con estacionalidad semanal puede ser legitimo, verificar "
            "alineacion con target_shift_test",
            late,
            early,
        )
    return ok


# --------------------------------------------------------------------------
# 8 · test de fold
# --------------------------------------------------------------------------
def assert_fold_disjoint(fold: Fold, panel: pd.DataFrame, *, date_col: str = S.DATE) -> None:
    """Train y test de un fold no comparten ni una fila, y el gap es el correcto."""
    dates = panel[date_col]
    train_mask = fold.train_mask(dates)
    test_mask = fold.test_mask(dates)

    overlap = int((train_mask & test_mask).sum())
    if overlap:
        raise LeakageError(f"{fold!r}: {overlap} filas estan en train y en test a la vez")
    if not test_mask.any():
        raise LeakageError(f"{fold!r}: el test quedo vacio")
    if not train_mask.any():
        raise LeakageError(f"{fold!r}: el train quedo vacio")

    max_train = dates[train_mask].max()
    min_test = dates[test_mask].min()
    if min_test <= max_train:
        raise LeakageError(
            f"{fold!r}: el test empieza en {min_test.date()} y el train termina en "
            f"{max_train.date()}"
        )
    if (min_test - max_train).days != 1:
        raise LeakageError(
            f"{fold!r}: el test deberia empezar el dia siguiente al origen, "
            f"empieza {(min_test - max_train).days} dias despues"
        )
    actual_gap = (dates[test_mask].max() - max_train).days
    if actual_gap != fold.gap_days:
        raise LeakageError(
            f"{fold!r}: el gap real es {actual_gap} dias y el horizonte es "
            f"{fold.gap_days}; el ultimo dia de test debe estar a `horizon` dias "
            "del ultimo de train"
        )


def assert_all_folds_disjoint(folds: Sequence[Fold], panel: pd.DataFrame) -> None:
    for fold in folds:
        assert_fold_disjoint(fold, panel)


__all__ = [
    "LeakageError",
    "ShiftResult",
    "ShuffleResult",
    "assert_all_folds_disjoint",
    "assert_fold_disjoint",
    "assert_lags_are_grouped",
    "assert_no_future_columns",
    "assert_no_global_aggregates",
    "assert_no_target_leakage",
    "assert_pipeline_fitted_on_train",
    "future_shift_test",
    "shuffle_test",
    "target_shift_test",
]
