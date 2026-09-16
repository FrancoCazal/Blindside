"""CONTRATO 2 de 4 · interfaz de modelo.

Todo modelo del proyecto — baseline, LightGBM, SARIMA, GRU — implementa
`Forecaster`. El arnes de backtesting no sabe con que esta hablando, y eso es
lo que permite comparar catorce modelos contra el mismo arnes sin escribir
catorce evaluaciones.

Decision de diseno que sostiene el checklist antifugas (seccion 5.2 del plan):
un modelo recibe exactamente dos cosas.

* ``fit(history)`` — el panel **hasta el origen inclusive**. Nada posterior.
* ``predict(future)`` — un indice de futuro con ``series_id``, ``dt``, ``h`` y
  las covariables conocidas de antemano. **Sin columna de target.**

O sea que el modelo no tiene desde donde mirar el futuro ni por accidente. La
fuga deja de ser algo que hay que recordar no hacer y pasa a ser algo que no
se puede expresar. Los tests de `tests/test_leakage.py` verifican que ningun
modelo rompa esta separacion.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import joblib
import numpy as np
import pandas as pd

from dfcore.data import schema as S

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from typing_extensions import Self

#: Columnas que el indice de futuro tiene garantizadas.
FUTURE_INDEX_COLS: tuple[str, ...] = (S.SERIES_ID, S.DATE, "h")

#: Columnas que un indice de futuro NUNCA puede traer. Si aparecen es fuga.
FORBIDDEN_IN_FUTURE: tuple[str, ...] = (
    S.SALE_AMOUNT,
    S.DEMAND_LATENT,
    S.OOS_HOURS_OPEN,
    S.OOS_HOURS_DAY,
    S.AVAILABLE_WEIGHT,
    S.IS_CENSORED,
    S.INFLATION,
)


class NotFittedError(RuntimeError):
    """Se pidio predecir antes de entrenar."""


def quantile_col(q: float) -> str:
    """Nombre canonico de la columna de un cuantil. 0.9 -> 'pred_q90'."""
    return f"pred_q{int(round(q * 100)):02d}"


def check_future_index(future: pd.DataFrame) -> pd.DataFrame:
    """Valida el indice de futuro. Falla si trae informacion del futuro real."""
    missing = [c for c in FUTURE_INDEX_COLS if c not in future.columns]
    if missing:
        raise S.SchemaError(f"el indice de futuro no trae {missing}")
    leaked = [c for c in FORBIDDEN_IN_FUTURE if c in future.columns]
    if leaked:
        raise S.SchemaError(
            f"el indice de futuro trae columnas prohibidas {leaked}: eso es fuga, "
            "no una comodidad"
        )
    return future


class Forecaster(ABC):
    """Interfaz comun. Subclasificar e implementar `_fit` y `_predict`.

    Atributos que la subclase define:

    * ``name`` — etiqueta corta que aparece en los reportes y el dashboard.
    * ``supports_quantiles`` — si ``predict_quantile`` es nativo. Si es False,
      el envoltorio conformal se encarga de producir el intervalo.
    """

    name: str = "forecaster"
    supports_quantiles: bool = False

    def __init__(self) -> None:
        self._fitted: bool = False
        self._target: str = S.DEMAND_LATENT
        #: Ultima fecha vista en entrenamiento. El arnes la usa para verificar
        #: que ninguna prediccion caiga dentro del train.
        self.last_train_date: pd.Timestamp | None = None
        self._series_seen: set[str] = set()

    # -- API publica ------------------------------------------------------
    def fit(self, history: pd.DataFrame, *, target: str = S.DEMAND_LATENT) -> Self:
        """Entrena con el panel hasta el origen. `history` no incluye el futuro."""
        if target not in history.columns:
            raise S.SchemaError(f"el target '{target}' no esta en history")
        self._target = target
        self.last_train_date = pd.Timestamp(history[S.DATE].max())
        self._series_seen = set(history[S.SERIES_ID].astype(str).unique())
        self._fit(history, target=target)
        self._fitted = True
        return self

    def predict(self, future: pd.DataFrame) -> pd.Series:
        """Prediccion puntual. Devuelve una Serie alineada al indice de `future`."""
        self._check_ready(future)
        out = self._predict(future)
        return self._as_series(out, future)

    def predict_quantile(self, future: pd.DataFrame, quantiles: Sequence[float]) -> pd.DataFrame:
        """Cuantiles predichos, una columna por cuantil.

        Implementacion por defecto para modelos sin cuantiles nativos: devuelve
        la prediccion puntual repetida. Es deliberadamente inutil como intervalo
        — el intervalo honesto lo produce el envoltorio conformal a partir de
        residuos de calibracion, no un modelo puntual disfrazado.
        """
        point = self.predict(future)
        return pd.DataFrame(
            {quantile_col(q): point.to_numpy() for q in quantiles},
            index=future.index,
        )

    # -- Persistencia -----------------------------------------------------
    def save(self, path: Path) -> Path:
        """Serializa el modelo entrenado. Formato unico para todo el proyecto."""
        if not self._fitted:
            raise NotFittedError(f"{self.name} no esta entrenado")
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=3)
        return path

    @staticmethod
    def load(path: Path) -> Forecaster:
        obj = joblib.load(path)
        if not isinstance(obj, Forecaster):
            raise TypeError(f"{path} no contiene un Forecaster")
        return obj

    # -- Ganchos que implementa la subclase -------------------------------
    @abstractmethod
    def _fit(self, history: pd.DataFrame, *, target: str) -> None: ...

    @abstractmethod
    def _predict(self, future: pd.DataFrame) -> np.ndarray: ...

    # -- Internos ---------------------------------------------------------
    def _check_ready(self, future: pd.DataFrame) -> None:
        if not self._fitted:
            raise NotFittedError(f"{self.name} no esta entrenado")
        check_future_index(future)
        if self.last_train_date is not None:
            overlap = future[S.DATE] <= self.last_train_date
            if overlap.any():
                raise S.SchemaError(
                    f"{int(overlap.sum())} filas del futuro caen en el train "
                    f"(<= {self.last_train_date.date()}): el gap esta mal armado"
                )

    def _as_series(self, values: np.ndarray | pd.Series, future: pd.DataFrame) -> pd.Series:
        arr = np.asarray(values, dtype="float64").reshape(-1)
        if arr.shape[0] != len(future):
            raise ValueError(
                f"{self.name} devolvio {arr.shape[0]} predicciones para "
                f"{len(future)} filas de futuro"
            )
        # La demanda no es negativa. Recortar en cero es parte del contrato y no
        # una correccion cosmetica: una orden de reposicion negativa no existe.
        arr = np.clip(arr, 0.0, None)
        return pd.Series(arr, index=future.index, name=self.name)

    def __repr__(self) -> str:
        state = "fitted" if self._fitted else "unfitted"
        return f"{type(self).__name__}(name={self.name!r}, {state})"


class SeriesLevelForecaster(Forecaster):
    """Base para modelos que trabajan serie por serie sobre su historia.

    Cubre los baselines, SARIMA y Prophet. La subclase implementa
    `_fit_series` (que devuelve un estado por serie) y `_predict_series`.
    El fallback para series no vistas en train es explicito y no un KeyError.
    """

    def __init__(self) -> None:
        super().__init__()
        self._state: dict[str, Any] = {}
        self._global_fallback: float = 0.0

    def _fit(self, history: pd.DataFrame, *, target: str) -> None:
        self._state = {}
        for sid, grp in history.groupby(S.SERIES_ID, observed=True, sort=False):
            y = grp.sort_values(S.DATE)[target].to_numpy(dtype="float64")
            self._state[str(sid)] = self._fit_series(y)
        self._global_fallback = float(history[target].mean())

    def _predict(self, future: pd.DataFrame) -> np.ndarray:
        out = np.empty(len(future), dtype="float64")
        pos = 0
        # groupby(sort=False) preserva el orden de aparicion; se reconstruye el
        # orden original por posiciones para no depender del indice.
        order = np.empty(len(future), dtype="int64")
        for sid, grp in future.groupby(S.SERIES_ID, observed=True, sort=False):
            steps = grp["h"].to_numpy(dtype="int64")
            n = steps.shape[0]
            # La pertenencia se pregunta con `in` y no con `.get() is None`.
            # Un `_fit_series` puede devolver `None` legitimamente cuando la serie
            # no necesita estado — `ZeroForecaster` es el caso — y con `.get()`
            # eso seria indistinguible de "serie nunca vista", asi que el modelo
            # caeria al promedio global en vez de a su propia prediccion. El bug
            # es silencioso: el modelo devuelve numeros plausibles y equivocados.
            if str(sid) not in self._state:
                vals = np.full(n, self._global_fallback, dtype="float64")
            else:
                vals = np.asarray(
                    self._predict_series(self._state[str(sid)], steps), dtype="float64"
                ).reshape(-1)
                if vals.shape[0] != n:
                    # Sin este chequeo numpy difunde un array de largo 1 sobre los
                    # `n` pasos y el error pasa desapercibido.
                    raise ValueError(
                        f"{self.name}: _predict_series devolvio {vals.shape[0]} "
                        f"valores para {n} pasos de la serie {sid}"
                    )
            out[pos : pos + n] = vals
            order[pos : pos + n] = grp.index.to_numpy()
            pos += n
        restored = pd.Series(out, index=order).reindex(future.index)
        return restored.to_numpy()

    @abstractmethod
    def _fit_series(self, y: np.ndarray) -> Any:
        """Estado que hace falta para pronosticar esta serie."""

    @abstractmethod
    def _predict_series(self, state: Any, steps: np.ndarray) -> np.ndarray:
        """Pronostico para los pasos `steps` (1-indexados) de una serie."""
