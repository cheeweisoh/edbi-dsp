.PHONY: install bootstrap dev test lint

PYTHON := .venv/bin/python

install:
	pip install -r backend/requirements.txt

bootstrap:
	cd backend && ../.venv/bin/python -m app.db.bootstrap

dev:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	.venv/bin/pytest

lint:
	cd backend && ../.venv/bin/pylint $$(git ls-files '*.py') && ../.venv/bin/mypy . --ignore-missing-imports

streamlit:
	cd frontend && ../.env/bin/streamlit run app.py

all: bootstrap
	@echo "Starting backend (uvicorn) and frontend (streamlit) concurrently..."
	(cd backend && ../.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &)  
	(cd frontend && ../.venv/bin/streamlit run app.py > streamlit.log 2>&1 &)  
	@echo "Both processes started. Logs: uvicorn.log, streamlit.log"
	@wait


.PHONY: stop

stop:
	pkill -f "uvicorn app.main:app" || true
	pkill -f "streamlit run app.py" || true
	@echo "Backend and Streamlit processes killed."
