.PHONY: install install-browser dev-backend dev-frontend migrate migration-status explore explore-full research-mercari research-mercari-browser test lint typecheck check

install:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
	pnpm --dir frontend install

install-browser:
	.venv/bin/python -m playwright install chromium

dev-backend:
	./scripts/dev-backend.sh

dev-frontend:
	./scripts/frontend.sh dev

migrate:
	.venv/bin/python scripts/migrate.py apply

migration-status:
	.venv/bin/python scripts/migrate.py status

explore:
	./scripts/explore.sh incremental

explore-full:
	./scripts/explore.sh full

research-mercari:
	./scripts/research-mercari.sh $(ARGS)

research-mercari-browser:
	./scripts/research-mercari-browser.sh $(ARGS)

test:
	.venv/bin/pytest
	./scripts/frontend.sh test

lint:
	.venv/bin/ruff check backend worker
	./scripts/frontend.sh lint

typecheck:
	.venv/bin/mypy
	./scripts/frontend.sh typecheck

check: lint typecheck test
