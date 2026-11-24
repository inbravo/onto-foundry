"""
Ollama tool-call agent: NL question → SPARQL over insurance context graph → answer.
Requires a locally running Ollama instance with a tool-capable model.

Run:  make run
  or: .venv/bin/python insurance/04-agent-query/agent.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import ollama
from rdflib import Graph

# ── config ────────────────────────────────────────────────────────────────────

MODEL   = "qwen2.5"           # swap for llama3.1, mistral-nemo, etc.
ROOT    = Path(__file__).resolve().parents[2]
TTL     = ROOT / "insurance" / "03-context-graph" / "insurance-context.ttl"
SCHEMA  = ROOT / "insurance" / "02-ontology" / "insurance.ttl"

PREFIXES = """\
PREFIX ins:  <http://ontology-foundry.io/insurance#>
PREFIX data: <http://ontology-foundry.io/insurance/data#>
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
"""

# ── graph ─────────────────────────────────────────────────────────────────────

def _check_model() -> None:
    global MODEL
    # Ollama tags models as "name:tag"; match on base name
    models    = ollama.list().models
    available = [m.model for m in models]
    base_map  = {m.model.split(":")[0]: m.model for m in models}
    if MODEL not in available and MODEL not in base_map:
        names = "\n  ".join(available)
        print(f"Model '{MODEL}' not found.\nInstalled:\n  {names}\nSet MODEL at top of agent.py or run: ollama pull {MODEL}")
        sys.exit(1)
    MODEL = base_map.get(MODEL, MODEL)  # expand "qwen2.5" → "qwen2.5:latest"


def load_graph() -> Graph:
    if not TTL.exists():
        print("Context graph not found — run:  make build")
        sys.exit(1)
    g = Graph()
    g.parse(TTL, format="turtle")
    return g


# ── tool definitions (Ollama / OpenAI schema) ─────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_ontology_schema",
            "description": (
                "Returns the ontology in Turtle format. "
                "Call this first to discover class names, property URIs, "
                "and SKOS concept URIs before writing any SPARQL."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sparql",
            "description": (
                "Executes a SPARQL SELECT query against the insurance context graph. "
                "Returns rows as a JSON list of dicts. "
                "Standard prefixes ins:, data:, xsd: are injected automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A valid SPARQL SELECT query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


# ── tool implementations ───────────────────────────────────────────────────────

def get_ontology_schema() -> str:
    return SCHEMA.read_text()


def run_sparql(graph: Graph, query: str) -> str:
    full_query = PREFIXES + "\n" + query
    try:
        results = graph.query(full_query)
        rows = [
            {str(var): str(row[var]) for var in results.vars if row[var] is not None}
            for row in results
        ]
        return json.dumps(rows, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def dispatch(name: str, args: dict, graph: Graph) -> str:
    if name == "get_ontology_schema":
        return get_ontology_schema()
    if name == "run_sparql":
        return run_sparql(graph, args.get("query", ""))
    return json.dumps({"error": f"unknown tool: {name}"})


# ── agent loop ────────────────────────────────────────────────────────────────

SYSTEM = """\
You are an insurance analytics agent.
Answer questions by querying an RDF knowledge graph via SPARQL.
Always call get_ontology_schema first to verify correct property URIs.
Incurred LR = (paid loss + case reserve) / earned premium.
Ultimate LR adds IBNR to the numerator.
Express ratios as percentages rounded to one decimal place.
"""


def ask(question: str, graph: Graph) -> str:
    messages = [
        {"role": "system",  "content": SYSTEM},
        {"role": "user",    "content": question},
    ]

    while True:
        response = ollama.chat(model=MODEL, messages=messages, tools=TOOLS)
        msg = response.message

        # no tool calls → final answer
        if not msg.tool_calls:
            return msg.content or "(no response)"

        # append assistant turn
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})

        # process each tool call
        for call in msg.tool_calls:
            fn   = call.function
            args = fn.arguments if isinstance(fn.arguments, dict) else json.loads(fn.arguments)
            result = dispatch(fn.name, args, graph)
            messages.append({
                "role":    "tool",
                "content": result,
            })


# ── entry point ───────────────────────────────────────────────────────────────

DEMO_QUESTIONS = [
    "What is the incurred loss ratio for Marine in Q3 2026?",
    "Which line of business has the highest ultimate loss ratio in Q3 2026?",
    "List all open claims with their paid losses.",
]

if __name__ == "__main__":
    _check_model()
    graph = load_graph()
    questions = sys.argv[1:] or DEMO_QUESTIONS

    for q in questions:
        print(f"\n── Q: {q}")
        answer = ask(q, graph)
        print(f"   A: {answer}")
