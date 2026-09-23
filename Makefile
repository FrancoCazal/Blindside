.PHONY: help setup data recover sample lint format test test-leakage backtest models train ablation app api clean \
        front front-setup front-build front-test api-schema \
        docker-build docker-build-full docker-up docker-down docker-logs docker-ps docker-shell docker-test docker-data

# En Windows el interprete del venv no esta en PATH salvo que se active. Se
# resuelve aca para que `make` funcione igual en las tres plataformas.
ifeq ($(OS),Windows_NT)
PY := .venv/Scripts/python.exe
else
PY := .venv/bin/python
endif

help:
	@echo "setup         - instala dependencias fijas + el paquete en modo editable"
	@echo "data          - descarga y submuestrea FreshRetailNet-50K a data/interim/"
	@echo "recover       - recupera la demanda censurada -> data/processed/demand.parquet"
	@echo "sample        - genera data/sample/ (commiteado) desde data/interim/"
	@echo "lint          - ruff check"
	@echo "format        - ruff format"
	@echo "test          - pytest (excluye los marcados slow)"
	@echo "test-leakage  - solo los tests antifugas (los de la defensa)"
	@echo "backtest      - baselines -> reports/metrics.md, imprime el MASE"
	@echo "models        - baselines + LightGBM + lineales -> reports/metrics.md"
	@echo "train         - entrena y serializa los DOS artefactos (observado y recuperado)"
	@echo "ablation      - ablacion de censura: venta observada vs demanda latente"
	@echo "app           - levanta el dashboard Streamlit en localhost"
	@echo "api           - levanta la API FastAPI en localhost"
	@echo "clean         - borra caches y artefactos intermedios"
	@echo ""
	@echo "Frontend (React + Vite, necesita la API corriendo):"
	@echo "  front-setup  - npm install"
	@echo "  front        - dev server en http://127.0.0.1:5173"
	@echo "  front-build  - tsc + vite build a frontend/dist"
	@echo "  front-test   - vitest (logica pura + render con fetch simulado)"
	@echo "  api-schema   - regenera los tipos TS desde el OpenAPI de la API"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build      - construye la imagen de servicio (api + app)"
	@echo "  docker-build-full - construye la imagen del pipeline (entrena, testea)"
	@echo "  docker-up         - levanta api en :8000 y app en :8501"
	@echo "  docker-down       - baja los servicios"
	@echo "  docker-logs       - sigue los logs de los dos servicios"
	@echo "  docker-ps         - estado y salud de los contenedores"
	@echo "  docker-shell      - shell dentro de la imagen del pipeline"
	@echo "  docker-test       - corre la suite dentro del contenedor"
	@echo ""
	@echo "Camino critico completo desde cero:  make setup data recover backtest"

setup:
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e . --no-deps

data:
	$(PY) -m blindside.data.freshretail --out data/interim --seed 42

recover:
	$(PY) -m blindside.decision recover --method hourly_profile

sample:
	$(PY) -m blindside.data.freshretail --make-sample --out data/sample --seed 42
	$(PY) -m blindside.decision recover --method hourly_profile --sample --out data/sample

lint:
	$(PY) -m ruff check src tests api app

format:
	$(PY) -m ruff format src tests api app

test:
	$(PY) -m pytest -m "not slow"

test-leakage:
	$(PY) -m pytest -m leakage -v

backtest:
	$(PY) -m blindside.evaluate.backtest --out reports/metrics.md \
		--save-result reports/backtest_baselines.parquet

models:
	$(PY) -m blindside.evaluate.backtest --out reports/metrics.md \
		--models seasonal_naive naive croston_sba moving_average \
		         seasonal_moving_average lgbm_global ridge \
		--save-result reports/backtest_models.parquet

train:
	$(PY) -m blindside.models train --model lgbm_quantile --conformal --basis both

ablation:
	$(PY) -m blindside.evaluate.ablation --out reports/censoring_ablation.md

app:
	$(PY) -m streamlit run app/streamlit_app.py --server.address 127.0.0.1

api:
	$(PY) -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

clean:
	$(PY) -c "import shutil,pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	$(PY) -c "import shutil; [shutil.rmtree(d, ignore_errors=True) for d in ('.pytest_cache','.ruff_cache','.mypy_cache')]"

# --- Frontend ------------------------------------------------------------
# El front habla con la API por HTTP y no por un proxy de Vite, asi que necesita
# que el origen del dev server este en el allowlist de CORS (lo esta por defecto).

front-setup:
	cd frontend && npm install

front:
	cd frontend && npm run dev

front-build:
	cd frontend && npm run build

front-test:
	cd frontend && npm test

# Los tipos del frontend salen del OpenAPI, no se escriben a mano: un rename en
# api/schemas.py rompe la compilacion del front, que es lo que se quiere.
api-schema:
	$(PY) -c "import json; from api.main import app; open('frontend/openapi.json','w',encoding='utf-8').write(json.dumps(app.openapi(), indent=2, ensure_ascii=False))"
	cd frontend && npm run gen:api

# --- Docker --------------------------------------------------------------
# Los targets de abajo no usan $(PY): corren docker en el host.

docker-build:
	docker build --target serve -t blindside:serve .

docker-build-full:
	docker build --target full -t blindside:full .

docker-up:
	docker compose up -d --build
	@echo ""
	@echo "  API  -> http://127.0.0.1:8000/docs"
	@echo "  App  -> http://127.0.0.1:8501"
	@echo ""
	@echo "  Los puertos estan atados a 127.0.0.1: la API no tiene autenticacion."

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api app

docker-ps:
	docker compose ps

docker-shell:
	docker compose --profile pipeline run --rm --entrypoint bash pipeline

docker-test:
	docker compose --profile pipeline run --rm --entrypoint pytest pipeline -m "not slow" -q

# Prepara las capas de datos dentro del contenedor, sin depender del entorno
# local. Es el camino que conviene para reproducir en otra maquina.
docker-data:
	docker compose --profile pipeline run --rm pipeline data
	docker compose --profile pipeline run --rm pipeline recover
