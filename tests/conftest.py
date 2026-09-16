"""Fixtures compartidas.

Los tests corren sobre un panel **sintetico** generado aca, no sobre el dataset
real. Tres razones, en orden de importancia:

1. La CI no puede depender de descargar 115 MB de HuggingFace.
2. En un panel sintetico el proceso generador es conocido, asi que se puede
   verificar que el codigo recupera lo que se inyecto — por ejemplo, que la
   recuperacion de censura devuelve la demanda latente que se uso para simular
   los quiebres. Eso es verificacion, no fe.
3. Es chico y los tests corren en segundos.

Los tests que si necesitan el dataset real van marcados `slow` y quedan fuera de
`make test`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dfcore import config as cfg
from dfcore.data import schema as S

N_DAYS = 97  # los mismos 90 + 7 del dataset real
START = pd.Timestamp("2024-03-28")


def _synthetic_series(
    rng: np.random.Generator,
    *,
    n_days: int,
    level: float,
    weekly_amplitude: float,
    zero_prob: float,
) -> np.ndarray:
    """Demanda latente con estacionalidad semanal conocida y ceros de cola.

    La amplitud semanal se fija a mano, asi que un test puede verificar que el
    modelo (o SHAP) la encuentra. Es la ventaja metodologica de un generador
    sobre un dataset real: aca se sabe la respuesta.
    """
    t = np.arange(n_days)
    dow = (START.dayofweek + t) % 7
    weekly = 1.0 + weekly_amplitude * np.sin(2 * np.pi * dow / 7)
    trend = 1.0 + 0.002 * t
    noise = rng.gamma(shape=4.0, scale=0.25, size=n_days)
    demand = level * weekly * trend * noise
    if zero_prob > 0:
        demand = np.where(rng.random(n_days) < zero_prob, 0.0, demand)
    return np.round(demand, 3)


@pytest.fixture(scope="session")
def hourly_profile() -> np.ndarray:
    """Perfil intradiario de 24 horas, con pico de manana y de tarde.

    Cero fuera de la ventana comercial 6..21, que es lo que hace el dataset real.
    """
    profile = np.zeros(24)
    for hour in cfg.CENSORING.open_hours:
        morning = np.exp(-0.5 * ((hour - 9) / 2.0) ** 2)
        evening = np.exp(-0.5 * ((hour - 18) / 2.0) ** 2)
        profile[hour] = 0.6 * morning + 1.0 * evening
    return profile / profile.sum()


@pytest.fixture(scope="session")
def synthetic_hourly_panel(hourly_profile: np.ndarray) -> pd.DataFrame:
    """Panel con secuencias horarias y censura **inyectada de forma conocida**.

    El procedimiento imita el mecanismo real: se genera la demanda latente, se
    reparte en el dia segun el perfil, se marcan horas de quiebre, y la venta
    observada es la demanda de las horas que quedaron disponibles. Asi
    `demand_latent_true` es la verdad de terreno que la recuperacion tiene que
    reconstruir.
    """
    rng = np.random.default_rng(cfg.SEED)
    dates = pd.date_range(START, periods=N_DAYS, freq="D")
    rows = []

    # 3 tiendas x 8 productos = 24 series, con jerarquia coherente.
    for store in range(3):
        for product in range(8):
            level = float(rng.uniform(0.5, 6.0))
            zero_prob = 0.25 if product >= 6 else 0.02  # dos productos de cola
            latent = _synthetic_series(
                rng,
                n_days=N_DAYS,
                level=level,
                weekly_amplitude=float(rng.uniform(0.15, 0.35)),
                zero_prob=zero_prob,
            )
            # Rachas de quiebre: empiezan al azar y duran entre 1 y 10 horas.
            status = np.zeros((N_DAYS, 24), dtype="int8")
            for day in range(N_DAYS):
                if rng.random() < 0.45:
                    start_h = int(rng.integers(6, 22))
                    length = int(rng.integers(1, 11))
                    status[day, start_h : min(start_h + length, 24)] = 1

            hours_latent = latent[:, None] * hourly_profile[None, :]
            hours_sale = np.where(status == 1, 0.0, hours_latent)
            observed = hours_sale.sum(axis=1)

            open_idx = np.asarray(cfg.CENSORING.open_hours)
            oos_open = status[:, open_idx].sum(axis=1)

            for i, dt in enumerate(dates):
                rows.append(
                    {
                        S.CITY_ID: store // 2,
                        S.STORE_ID: store,
                        S.MANAGEMENT_GROUP_ID: 0,
                        S.FIRST_CATEGORY_ID: product // 4,
                        S.SECOND_CATEGORY_ID: product // 2,
                        S.THIRD_CATEGORY_ID: product,
                        S.PRODUCT_ID: product,
                        S.DATE: dt,
                        S.SALE_AMOUNT: float(observed[i]),
                        S.HOURS_SALE: hours_sale[i].astype("float32"),
                        S.OOS_HOURS_OPEN: int(oos_open[i]),
                        S.HOURS_STOCK_STATUS: status[i],
                        S.DISCOUNT: float(rng.choice([1.0, 0.9, 0.8])),
                        S.HOLIDAY_FLAG: int(dt.dayofweek == 6),
                        S.ACTIVITY_FLAG: int(rng.random() < 0.15),
                        S.PRECIPITATION: float(rng.gamma(2, 1.5)),
                        S.AVG_TEMPERATURE: float(15 + 10 * np.sin(2 * np.pi * i / 365)),
                        S.AVG_HUMIDITY: float(rng.uniform(60, 90)),
                        S.AVG_WIND_LEVEL: float(rng.uniform(1, 3)),
                        # Verdad de terreno, solo para los tests. No es del contrato.
                        "demand_latent_true": float(latent[i]),
                    }
                )

    df = pd.DataFrame(rows)
    df[S.SERIES_ID] = S.make_series_id(df)
    df[S.OOS_HOURS_DAY] = np.stack(df[S.HOURS_STOCK_STATUS].to_numpy()).sum(axis=1).astype("int16")
    n_open = len(cfg.CENSORING.open_hours)
    df[S.AVAILABLE_WEIGHT] = ((n_open - df[S.OOS_HOURS_OPEN]) / n_open).astype("float32")
    df[S.IS_CENSORED] = df[S.OOS_HOURS_OPEN] > 0
    return S.cast_panel(df).sort_values([S.SERIES_ID, S.DATE]).reset_index(drop=True)


@pytest.fixture(scope="session")
def synthetic_panel(synthetic_hourly_panel: pd.DataFrame) -> pd.DataFrame:
    """Panel diario sin secuencias horarias."""
    return synthetic_hourly_panel.drop(columns=[*S.HOURLY_COLS, "demand_latent_true"])


@pytest.fixture(scope="session")
def recovered_panel(synthetic_hourly_panel: pd.DataFrame) -> pd.DataFrame:
    """Panel con demanda latente recuperada, listo para features y modelos."""
    from dfcore.decision.censoring import HourlyProfileRecovery

    out = HourlyProfileRecovery().recover(synthetic_hourly_panel)
    return out.drop(columns=[*S.HOURLY_COLS, "profile_weight"], errors="ignore")


@pytest.fixture(scope="session")
def small_forecast_config() -> cfg.ForecastConfig:
    """Configuracion reducida: 3 origenes en vez de 8, para que los tests vuelen."""
    return cfg.ForecastConfig(horizon=7, season_length=7, n_origins=3, step=3, min_train_days=42)


@pytest.fixture()
def supervised_matrix(recovered_panel: pd.DataFrame) -> pd.DataFrame:
    """Matriz supervisada de unos pocos origenes."""
    from dfcore.features import build as fb

    state = fb.add_origin_features(recovered_panel, target=S.DEMAND_LATENT)
    origins = pd.DatetimeIndex(sorted(state[S.DATE].unique()))[-20:-8]
    return fb.build_supervised(state, origins, horizon=7, target=S.DEMAND_LATENT)
