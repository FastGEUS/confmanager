PYTHON ?= python

.PHONY: setup run test quality verify init-db create-committee

setup:
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m app.manage setup

run:
	$(PYTHON) -m app.manage run

test:
	$(PYTHON) -m pytest -q

quality:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m bandit -r app -q

verify:
	$(PYTHON) -m app.manage verify

init-db:
	$(PYTHON) -m app.manage init-db

create-committee:
	$(PYTHON) -m app.manage create-committee
