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
