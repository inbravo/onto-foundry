"""
Claude tool-call agent: NL question → SPARQL over insurance context graph → answer.

Run:  ANTHROPIC_API_KEY=... python insurance/04-agent-query/agent.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anthropic
from rdflib import Graph

# ── paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).resolve().parents[2]
TTL     = ROOT / "insurance" / "03-context-graph" / "insurance-context.ttl"
SCHEMA  = ROOT / "insurance" / "02-ontology" / "insurance.ttl"

INS_PREFIX = "PREFIX ins: <http://ontology-foundry.io/insurance#>"
DATA_PREFIX = "PREFIX data: <http://ontology-foundry.io/insurance/data#>"
PREFIXES = f"{INS_PREFIX}\n{DATA_PREFIX}\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"


# ── graph ─────────────────────────────────────────────────────────────────────

def load_graph() -> Graph:
    if not TTL.exists():
        print("Context graph not found — run build_graph.py first.")
        sys.exit(1)
    g = Graph()
    g.parse(TTL, format="turtle")
    return g


# ── tools ─────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_ontology_schema",
        "description": (
            "Returns the ontology in Turtle format so the agent can discover "
            "class names, properties, and SKOS concept URIs before writing SPARQL."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "run_sparql",
        "description": (
            "Executes a SPARQL SELECT query against the insurance context graph. "
            "Returns rows as a JSON list of dicts. "
            "Use get_ontology_schema first to verify correct property URIs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A valid SPARQL SELECT query. Standard prefixes (ins:, data:, xsd:) are injected automatically.",
                }
            },
            "required": ["query"],
        },
    },
]


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


# ── agent loop ────────────────────────────────────────────────────────────────

SYSTEM = """\
You are an insurance analytics agent.
You answer questions by querying an RDF knowledge graph via SPARQL.
Always call get_ontology_schema first so you use correct URIs.
Incurred LR = (paid loss + case reserve) / earned premium.
Ultimate LR adds IBNR to the numerator.
Express ratios as percentages rounded to one decimal place in your final answer.
"""


def ask(question: str, graph: Graph) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    messages = [{"role": "user", "content": question}]

    while True:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )

        # collect any text blocks for the final answer
        text_blocks = [b.text for b in response.content if b.type == "text"]

        if response.stop_reason == "end_turn":
            return "\n".join(text_blocks)

        if response.stop_reason != "tool_use":
            return "\n".join(text_blocks) or "(no response)"

        # process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "get_ontology_schema":
                result = get_ontology_schema()
            elif block.name == "run_sparql":
                result = run_sparql(graph, block.input["query"])
            else:
                result = json.dumps({"error": f"unknown tool: {block.name}"})

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user",      "content": tool_results})


# ── entry point ───────────────────────────────────────────────────────────────

DEMO_QUESTIONS = [
    "What is the incurred loss ratio for Marine in Q3 2026?",
    "Which line of business has the highest ultimate loss ratio in Q3 2026?",
    "List all open claims with their paid losses.",
]

if __name__ == "__main__":
    graph = load_graph()
    questions = sys.argv[1:] or DEMO_QUESTIONS

    for q in questions:
        print(f"\n── Q: {q}")
        answer = ask(q, graph)
        print(f"   A: {answer}")
