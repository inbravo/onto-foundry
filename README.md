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

## Quickstart

Requires [Ollama](https://ollama.com) running locally with a tool-capable model:

```bash
ollama pull llama3.2
```

```bash
make run
```

`make run` creates the venv, installs deps, builds the context graph, and runs the agent.

To ask a custom question:

```bash
.venv/bin/python insurance/04-agent-query/agent.py "What is the net loss ratio for Property?"
```

To change the model, edit `MODEL` at the top of `insurance/04-agent-query/agent.py`.
Models known to support tool calls: `llama3.2`, `qwen2.5`, `mistral-nemo`.
