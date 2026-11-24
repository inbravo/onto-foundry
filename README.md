# ontology-foundry

Domain model → ontology → context graph → agent query, by industry vertical.

## Stack

- [`rdflib`](https://rdflib.readthedocs.io/) — OWL/Turtle authoring and SPARQL
- [`owlready2`](https://owlready2.readthedocs.io/) — Python-native OWL class mapping
- [`anthropic`](https://github.com/anthropics/anthropic-sdk-python) — Claude tool-call agent

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
04-agent-query/    agent.py   — Claude tool-call: NL → SPARQL → answer
```

## Quickstart

```bash
pip install rdflib owlready2 anthropic
python insurance/03-context-graph/build_graph.py   # builds + validates
python insurance/04-agent-query/agent.py            # ask "What is the incurred LR for Marine Q3?"
```
