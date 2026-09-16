# syntax=docker/dockerfile:1.7
#
# Imagen de demand-forecasting-core. Dos targets, y la eleccion importa:
#
#   serve  (default) - API + dashboard. Solo lo necesario para servir.
#   full             - todo requirements.txt, para correr el pipeline y entrenar.
#
# Construir:
#   docker build --target serve -t dfcore:serve .
#   docker build --target full  -t dfcore:full  .
#
# ---------------------------------------------------------------------------
# Por que dos targets
# ---------------------------------------------------------------------------
# requirements.txt tiene torch, jupyter, shap, optuna, umap-learn y xgboost. Nada
# de eso hace falta para responder /forecast ni para levantar el dashboard: el
# artefacto servido es un LightGBM, y la app lee parquet y dibuja. Instalar todo
# en la imagen de servicio la lleva de ~700 MB a varios GB y alarga cada build
# sin que nada de eso se ejecute nunca.
#
# El target `full` existe para correr `make data`, `make recover` y `make models`
# dentro de un contenedor, y ahi si hace falta el entorno completo.
#
# ---------------------------------------------------------------------------
# Como se evita la divergencia de versiones entre los dos targets
# ---------------------------------------------------------------------------
# El target `serve` NO tiene su propio archivo de dependencias. Instala una lista
# corta de paquetes de primer nivel usando `--constraint requirements.txt`, asi que
# las versiones **salen del mismo archivo** que el entorno completo. Un segundo
# requirements-serve.txt habria sido mas obvio de leer y habria abierto la puerta a
# que los pines se desincronicen en silencio, que es peor.

ARG PYTHON_VERSION=3.11

# ===========================================================================
# Stage base · dependencias del sistema, comunes a los dos targets
# ===========================================================================
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUTF8=1 \
    # El paquete se instala en un venv propio y no en el Python del sistema, para
    # que copiarlo entre stages sea copiar un solo directorio.
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# libgomp1 es la dependencia real de LightGBM y XGBoost: sin ella el import falla
# con un error de OpenMP que no menciona a LightGBM y cuesta diagnosticar.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV" \
    && pip install --upgrade pip setuptools wheel

WORKDIR /app

# ===========================================================================
# Stage deps-serve · solo lo que hace falta para servir
# ===========================================================================
FROM base AS deps-serve

COPY requirements.txt ./

# Las versiones vienen de requirements.txt via --constraint, asi que no hay dos
# fuentes de verdad. La lista de abajo es la superficie de import real:
#   dfcore nucleo -> numpy pandas pyarrow scikit-learn lightgbm joblib
#   api           -> fastapi uvicorn pydantic
#   app           -> streamlit
RUN pip install --constraint requirements.txt \
        numpy \
        pandas \
        pyarrow \
        scikit-learn \
        lightgbm \
        joblib \
        fastapi \
        "uvicorn[standard]" \
        pydantic \
        streamlit

# ===========================================================================
# Stage deps-full · el entorno completo de requirements.txt
# ===========================================================================
FROM base AS deps-full

COPY requirements.txt ./

# torch se instala **antes** y desde el indice CPU de PyTorch. En Linux el
# `torch==2.4.1` de PyPI es la build CUDA y arrastra los paquetes nvidia-*, que
# son del orden de 2,5 GB de wheels que este proyecto no usa: no hay GPU en el
# host de la defensa y los modelos servidos son LightGBM. La variante `+cpu`
# satisface el pin `torch==2.4.1` de requirements.txt (PEP 440 permite el
# sufijo local), asi que el paso siguiente la encuentra ya instalada.
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
        torch==2.4.1+cpu

RUN pip install -r requirements.txt

# xgboost 2.1.1 declara `nvidia-nccl-cu12` como dependencia dura en Linux, y son
# 454 MB medidos en site-packages. Es la libreria de comunicacion multi-GPU: aca
# xgboost corre con `tree_method="hist"` en CPU y no la toca nunca.
#
# Se desinstala DESPUES de requirements.txt y no antes con --no-deps, porque pip
# completa las dependencias faltantes de un paquete que ya esta instalado: un
# `pip install --no-deps xgboost` previo no evita nada, el `-r requirements.txt`
# la vuelve a traer. Se probo y el guard de abajo lo detecto.
#
# Verificado en el contenedor: sin nccl, xgboost 2.1.1 importa, entrena con
# tree_method="hist" y predice. Si alguna vez se quiere GPU, esta linea se saca.
RUN pip uninstall -y nvidia-nccl-cu12

# Red de seguridad: si una dependencia futura vuelve a arrastrar el stack CUDA, el
# build **falla aca** en vez de agregar gigabytes en silencio. La imagen es de CPU
# por diseno, no por casualidad, y esto lo vuelve verificable en cada build.
RUN if pip list 2>/dev/null | grep -Eiq '^nvidia-|^triton '; then \
        echo "ERROR: paquetes CUDA en una imagen de CPU:" >&2; \
        pip list 2>/dev/null | grep -Ei '^nvidia-|^triton ' >&2; \
        exit 1; \
    fi \
    && python -c "import torch, xgboost; assert not torch.version.cuda, torch.__version__; \
print('sin CUDA · torch', torch.__version__, '· xgboost', xgboost.__version__)"

# ===========================================================================
# Stage runtime-serve · imagen final de servicio
# ===========================================================================
FROM base AS serve

COPY --from=deps-serve /opt/venv /opt/venv

# Usuario sin privilegios. La API no tiene autenticacion (ver README), asi que
# reducir lo que puede hacer el proceso si alguien alcanza el puerto es lo menos
# que corresponde.
RUN useradd --create-home --uid 1000 dfcore

# El codigo va despues de las dependencias a proposito: cambia mucho mas seguido,
# y asi un cambio en src/ no invalida la capa de pip.
COPY --chown=dfcore:dfcore pyproject.toml README.md ./
COPY --chown=dfcore:dfcore src ./src
COPY --chown=dfcore:dfcore api ./api
COPY --chown=dfcore:dfcore app ./app

RUN pip install --no-deps -e .

# Los directorios de datos se crean vacios y se **montan** como volumenes. No se
# copian: data/ pesa cientos de MB y meterla en una capa volveria la imagen
# inmutable respecto de los datos, que es lo contrario de lo que se quiere.
RUN mkdir -p data/raw data/interim data/processed data/sample artifacts reports/figures \
    && chown -R dfcore:dfcore /app

USER dfcore

EXPOSE 8000 8501

# Healthcheck generico del stage. Cada servicio lo redefine en compose con el
# puerto que le corresponde.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ===========================================================================
# Stage runtime-full · pipeline, entrenamiento y tests
# ===========================================================================
FROM base AS full

COPY --from=deps-full /opt/venv /opt/venv

RUN useradd --create-home --uid 1000 dfcore

COPY --chown=dfcore:dfcore pyproject.toml README.md Makefile ./
COPY --chown=dfcore:dfcore src ./src
COPY --chown=dfcore:dfcore api ./api
COPY --chown=dfcore:dfcore app ./app
COPY --chown=dfcore:dfcore tests ./tests

RUN pip install --no-deps -e .

RUN mkdir -p data/raw data/interim data/processed data/sample artifacts reports/figures \
    && chown -R dfcore:dfcore /app

USER dfcore

# La cache de HuggingFace apunta a un directorio del proyecto para que se pueda
# montar como volumen y no se re-descarguen 115 MB en cada corrida.
ENV HF_HOME=/app/data/.hf_cache

CMD ["python", "-c", "import dfcore; print('dfcore', dfcore.__version__, 'listo')"]
