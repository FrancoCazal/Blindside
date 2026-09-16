.PHONY: help setup data recover sample lint format test test-leakage backtest models ablation app api clean

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
	@echo "ablation      - ablacion de censura: venta observada vs demanda latente"
	@echo "app           - levanta el dashboard Streamlit en localhost"
	@echo "api           - levanta la API FastAPI en localhost"
	@echo "clean         - borra caches y artefactos intermedios"
	@echo ""
	@echo "Camino critico completo desde cero:  make setup data recover backtest"

setup:
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e . --no-deps

data:
	$(PY) -m dfcore.data.freshretail --out data/interim --seed 42

recover:
	$(PY) -m dfcore.decision recover --method hourly_profile

sample:
	$(PY) -m dfcore.data.freshretail --make-sample --out data/sample --seed 42
	$(PY) -m dfcore.decision recover --method hourly_profile --sample --out data/sample

lint:
	$(PY) -m ruff check src tests api app

format:
	$(PY) -m ruff format src tests api app

test:
	$(PY) -m pytest -m "not slow"

test-leakage:
	$(PY) -m pytest -m leakage -v

backtest:
	$(PY) -m dfcore.evaluate.backtest --out reports/metrics.md \
		--save-result reports/backtest_baselines.parquet

models:
	$(PY) -m dfcore.evaluate.backtest --out reports/metrics.md \
		--models seasonal_naive croston_sba lgbm_global ridge \
		--save-result reports/backtest_models.parquet

ablation:
	$(PY) -m dfcore.evaluate.ablation --out reports/censoring_ablation.md

app:
	$(PY) -m streamlit run app/streamlit_app.py --server.address 127.0.0.1

api:
	$(PY) -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

clean:
	$(PY) -c "import shutil,pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	$(PY) -c "import shutil; [shutil.rmtree(d, ignore_errors=True) for d in ('.pytest_cache','.ruff_cache','.mypy_cache')]"
