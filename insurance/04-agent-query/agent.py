"""
Ollama tool-call agent: NL question → SPARQL over insurance context graph → answer.
Requires a locally running Ollama instance with a tool-capable model.

Usage:
    make run
    .venv/bin/python insurance/04-agent-query/agent.py
    .venv/bin/python insurance/04-agent-query/agent.py "What is the net LR for Property?"
"""
# ─────────────────────────────────────────────────────
# Author   : Amit Dixit
# GitHub   : https://github.com/inbravo
# Web      : https://inbravo.github.io
# LinkedIn : https://www.linkedin.com/in/inbravo/
# ─────────────────────────────────────────────────────
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import ollama
from rdflib import Graph

# ── paths + logging ───────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]
TTL  = ROOT / "insurance" / "03-context-graph" / "insurance-context.ttl"
SCHEMA = ROOT / "insurance" / "02-ontology" / "insurance.ttl"

sys.path.insert(0, str(ROOT / "_shared"))
import logging_config  # noqa: E402

logging_config.setup()
log = logging.getLogger("ontology.insurance.agent")

# ── config ────────────────────────────────────────────────────────────────────

MODEL    = "qwen2.5"   # swap for llama3.1, mistral-nemo, etc.
MAX_ITER = 6           # prevents infinite tool-call loops on small local models

PREFIXES = (
    "PREFIX ins:  <http://ontology-foundry.io/insurance#>\n"
    "PREFIX data: <http://ontology-foundry.io/insurance/data#>\n"
    "PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>\n"
)

# ── startup checks ────────────────────────────────────────────────────────────

def _check_model() -> None:
    """
    Resolves bare model name to Ollama's tagged form and exits with a helpful
    message if the model isn't installed.
    """
    global MODEL
    models    = ollama.list().models
    available = [m.model for m in models]
    base_map  = {m.model.split(":")[0]: m.model for m in models}
    if MODEL not in available and MODEL not in base_map:
        names = "\n  ".join(available)
        log.error("Model '%s' not found.\nInstalled:\n  %s\nrun: ollama pull %s", MODEL, names, MODEL)
        sys.exit(1)
    MODEL = base_map.get(MODEL, MODEL)
    log.info("model resolved: %s", MODEL)


def load_graph() -> Graph:
    """
    Loads the pre-built insurance context graph.

    Returns:
        Graph: populated rdflib graph
    """
    if not TTL.exists():
        log.error("context graph not found — run: make build")
        sys.exit(1)
    g = Graph()
    g.parse(TTL, format="turtle")
    log.info("context graph loaded: %d triples", len(g))
    return g


# ── tool ──────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_sparql",
            "description": (
                "Execute a SPARQL SELECT query against the insurance context graph. "
                "Returns rows as a JSON list of dicts. "
                "Prefixes ins:, data:, xsd: are injected automatically — do not redeclare them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SPARQL SELECT query body only (no PREFIX lines)."}
                },
                "required": ["query"],
            },
        },
    },
]


def run_sparql(graph: Graph, query: str) -> str:
    """
    Executes a SPARQL SELECT query against the insurance context graph.

    Args:
        graph: rdflib graph to query
        query: SPARQL SELECT body (without PREFIX declarations)

    Returns:
        str: JSON array of result rows, or JSON error object
    """
    full_query = PREFIXES + "\n" + query
    log.debug("SPARQL:\n%s", full_query)
    try:
        results = graph.query(full_query)
        rows = [
            {str(var): str(row[var]) for var in results.vars if row[var] is not None}
            for row in results
        ]
        log.debug("SPARQL result: %d rows", len(rows))
        return json.dumps(rows, indent=2)
    except Exception as exc:
        log.warning("SPARQL error: %s", exc)
        return json.dumps({"error": str(exc)})


# ── system prompt ─────────────────────────────────────────────────────────────

_URI_GUIDE = (
    "URI reference — use these exact URIs in triple patterns, never string labels:\n"
    "  Lines:    ins:LoB_Marine  ins:LoB_Property  ins:LoB_Liability  ins:LoB_Motor\n"
    "  Variants: ins:LRV_Paid  ins:LRV_Incurred  ins:LRV_Ultimate  ins:LRV_Attritional\n"
    '  Period:   literal string "2026-Q3"\n'
)

_EXAMPLES = (
    "Example 1 — incurred LR for Marine Q3 2026:\n"
    "  SELECT ?ratio WHERE {\n"
    "    ?rec a ins:LossRatioRecord ;\n"
    '         ins:period     "2026-Q3" ;\n'
    "         ins:forLine    ins:LoB_Marine ;\n"
    "         ins:measuredAs ins:LRV_Incurred ;\n"
    "         ins:ratioValue ?ratio .\n"
    "  }\n"
    "\n"
    "Example 2 — all Q3 2026 ultimate ratios, highest first:\n"
    "  SELECT ?line ?ratio WHERE {\n"
    "    ?rec a ins:LossRatioRecord ;\n"
    '         ins:period     "2026-Q3" ;\n'
    "         ins:measuredAs ins:LRV_Ultimate ;\n"
    "         ins:forLine    ?line ;\n"
    "         ins:ratioValue ?ratio .\n"
    "  } ORDER BY DESC(?ratio)\n"
    "\n"
    "Example 3 — open claims with paid loss:\n"
    "  SELECT ?claimId ?paid WHERE {\n"
    "    ?c a ins:Claim ;\n"
    '       ins:claimStatus "Open" ;\n'
    "       ins:claimId     ?claimId ;\n"
    "       ins:paidLoss    ?paid .\n"
    "  }\n"
)


def _system_prompt() -> str:
    schema = SCHEMA.read_text()
    return "\n".join([
        "You are an insurance analytics agent. Use run_sparql to answer questions.",
        "Incurred LR = (paid + case reserve) / earned premium.",
        "Ultimate LR adds IBNR. Express ratios as percentages to one decimal place.",
        "",
        _URI_GUIDE,
        _EXAMPLES,
        "Ontology (Turtle):",
        schema,
    ])


# ── agent loop ────────────────────────────────────────────────────────────────

def ask(question: str, graph: Graph) -> str:
    """
    Runs the tool-call loop until the model gives a final text answer.

    Args:
        question: natural language question
        graph: rdflib graph to query

    Returns:
        str: final answer from the model
    """
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user",   "content": question},
    ]
    collected: list[str] = []

    for iteration in range(MAX_ITER):
        response = ollama.chat(model=MODEL, messages=messages, tools=TOOLS)
        msg = response.message

        if msg.content:
            collected.append(msg.content)

        if not msg.tool_calls:
            return msg.content or " ".join(collected) or "(no response)"

        log.debug("iteration %d: %d tool call(s)", iteration + 1, len(msg.tool_calls))
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})

        for call in msg.tool_calls:
            fn     = call.function
            args   = fn.arguments if isinstance(fn.arguments, dict) else json.loads(fn.arguments)
            result = run_sparql(graph, args.get("query", ""))
            messages.append({"role": "tool", "content": result})

    log.warning("max iterations (%d) reached", MAX_ITER)
    return " ".join(collected) or "(max iterations reached)"


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
        log.info("Q: %s", q)
        answer = ask(q, graph)
        print(f"\n── Q: {q}\n   A: {answer}")
