# ontology-foundry

Domain model → ontology → context graph → agent query, by industry vertical.

## Stack

- [`rdflib`](https://rdflib.readthedocs.io/) — OWL/Turtle authoring and SPARQL
- [`owlready2`](https://owlready2.readthedocs.io/) — Python-native OWL class mapping
- [`ollama`](https://github.com/ollama/ollama-python) — local LLM tool-call agent
- [`pyshacl`](https://github.com/RDFLib/pySHACL) — SHACL validation (optional)

## Verticals

| Folder | Domain | Status |
|--------|--------|--------|
| `insurance/` | Loss ratio, FNOL, reserving | ✅ Wave 1 |
| `banking/` | Credit risk, FIBO | 🔜 |
| `healthcare/` | HL7, claims, episodes | 🔜 |

## Pattern (each vertical)

```
01-domain-model/   dataclasses — the business entities
02-ontology/       .ttl file  — OWL 2 + SKOS + SHACL
03-context-graph/  build_graph.py — populates rdflib in-memory graph
04-agent-query/    agent.py   — Ollama tool-call: NL → SPARQL → answer
```

## Ollama

### Install

```bash
brew install ollama        # macOS
```

For Linux or Windows: [ollama.com/download](https://ollama.com/download).

### Start the server

```bash
ollama serve
```

Runs in the foreground and prints live logs to the terminal. Keep this open while running the agent.

To run as a background service on macOS:

```bash
brew services start ollama
brew services stop ollama
```

### View logs

| Method | Command |
|--------|---------|
| Live (foreground) | `ollama serve` |
| macOS service logs | `tail -f ~/.ollama/logs/server.log` |
| Debug mode | `OLLAMA_DEBUG=1 ollama serve` |
| Linux systemd | `journalctl -u ollama -f` |

### Pull a model

```bash
ollama pull qwen2.5        # recommended — good tool-call support
ollama pull llama3.1       # alternative
ollama list                # see what's installed
```

## Setup

### Using Make

```bash
make install   # creates .venv and pip-installs requirements.txt
make build     # builds the context graph (.ttl)
make run       # runs the agent with demo questions
```

### Manual venv

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
python insurance/03-context-graph/build_graph.py
python insurance/04-agent-query/agent.py
```

Without activating:

```bash
.venv/bin/python insurance/03-context-graph/build_graph.py
.venv/bin/python insurance/04-agent-query/agent.py
```

### Custom question

```bash
.venv/bin/python insurance/04-agent-query/agent.py "What is the net loss ratio for Property?"
```

### Models

Edit `MODEL` at the top of `insurance/04-agent-query/agent.py`.
Models known to support tool calls: `qwen2.5`, `llama3.1`, `mistral-nemo`.
If the model isn't installed the agent lists what's available and exits.
