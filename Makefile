.PHONY: help setup data sample lint format test backtest app api clean

help:
	@echo "setup     - instala dependencias fijas + el paquete en modo editable"
	@echo "data      - descarga y submuestrea FreshRetailNet-50K a data/interim/"
	@echo "sample    - genera data/sample/ (commiteado) desde data/interim/"
	@echo "lint      - ruff check"
	@echo "format    - ruff format"
	@echo "test      - pytest (excluye los marcados slow)"
	@echo "backtest  - corre el arnes de backtesting y escribe reports/metrics.md"
	@echo "app       - levanta el dashboard Streamlit en localhost"
	@echo "api       - levanta la API FastAPI en localhost"
	@echo "clean     - borra caches y artefactos intermedios"

setup:
	pip install -r requirements.txt
	pip install -e .

data:
	python -m dfcore.data.freshretail --out data/interim --seed 42

sample:
	python -m dfcore.data.freshretail --make-sample --out data/sample --seed 42

lint:
	ruff check src tests api app

format:
	ruff format src tests api app

test:
	pytest -m "not slow"

backtest:
	python -m dfcore.evaluate.backtest --out reports/metrics.md

app:
	streamlit run app/streamlit_app.py --server.address 127.0.0.1

api:
	uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

clean:
	python -c "import shutil,pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import shutil; [shutil.rmtree(d, ignore_errors=True) for d in ('.pytest_cache','.ruff_cache','.mypy_cache')]"
