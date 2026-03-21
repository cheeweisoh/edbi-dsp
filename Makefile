.PHONY: install bootstrap dev test lint streamlit all stop

install:
	uv pip install -r backend/requirements.txt

bootstrap:
	cd backend && uv run python -m app.db.bootstrap

dev:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest

lint:
	cd backend && uv run pylint $$(git ls-files '*.py') && uv run mypy . --ignore-missing-imports

streamlit:
	cd frontend && uv run streamlit run app.py

all: bootstrap
	@echo "Starting Ollama service..."
	@if ! ollama ps >/dev/null 2>&1; then \
		ollama serve > ollama.log 2>&1 & \
		sleep 2; \
		echo "Started local Ollama daemon"; \
	else \
		echo "Ollama daemon already running"; \
	fi
	@echo "Ensuring Ollama model is available: mistral-large-3:675b-cloud"
	@ollama pull mistral-large-3:675b-cloud
	@echo "Starting backend (uvicorn) and frontend (streamlit) concurrently..."
	@(cd backend && sh -c 'exec uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000' > uvicorn.log 2>&1 &)
	@(cd frontend && sh -c 'exec uv run streamlit run app.py' > streamlit.log 2>&1 &)
	@echo "Processes started. Logs: ollama.log, backend/uvicorn.log, frontend/streamlit.log"

stop:
	@echo "Stopping backend/frontend/ollama by process name..."
	@pids=`pgrep -f "uv run uvicorn app.main:app|uvicorn app.main:app"`; if [ -n "$$pids" ]; then for pid in $$pids; do kill $$pid 2>/dev/null || true; done; fi
	@pids=`pgrep -f "uv run streamlit run app.py|streamlit run app.py"`; if [ -n "$$pids" ]; then for pid in $$pids; do kill $$pid 2>/dev/null || true; done; fi
	@ollama stop mistral-large-3:675b-cloud >/dev/null 2>&1 || true
	@pids=`pgrep -f "ollama serve"`; if [ -n "$$pids" ]; then for pid in $$pids; do kill $$pid 2>/dev/null || true; done; fi
	@echo "Stopped all managed processes."
