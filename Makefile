PYTHON  := python3
VENV    := .venv
PIP     := $(VENV)/bin/pip
PY      := $(VENV)/bin/python

.PHONY: venv install build run clean

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip --quiet

install: venv
	$(PIP) install -r requirements.txt --quiet

build: install
	$(PY) insurance/03-context-graph/build_graph.py

run: build
	$(PY) insurance/04-agent-query/agent.py

clean:
	rm -rf $(VENV)
	rm -f insurance/03-context-graph/insurance-context.ttl
