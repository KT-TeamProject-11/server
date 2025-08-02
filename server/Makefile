PYTHON   = python
UVICORN  = uvicorn
APP      = app.main:app
PORT     = 8555
HOST     = 0.0.0.0
ENV      ?= .env

.PHONY: install ingest run test clean

install:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -r requirements.txt

ingest:
	$(PYTHON) scripts/ingest.py

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8555 --reload --env-file $(ENV)

test:
	curl -s http://localhost:$(PORT)/health && echo

clean:
	find . -type f -name '*.py[co]' -delete
