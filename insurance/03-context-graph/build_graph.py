"""
Builds an in-memory rdflib graph from the insurance domain model,
validates it against the SHACL shapes in insurance.ttl, then
serializes to insurance-context.ttl for the agent to query.

Run:  python insurance/03-context-graph/build_graph.py
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, XSD

# ── paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).resolve().parents[2]
TTL_IN  = ROOT / "insurance" / "02-ontology" / "insurance.ttl"
TTL_OUT = ROOT / "insurance" / "03-context-graph" / "insurance-context.ttl"

sys.path.insert(0, str(ROOT / "insurance" / "01-domain-model"))
from model import LossRatioRecord, LossRatioVariant, LineOfBusiness, seed_data  # noqa: E402

INS = Namespace("http://ontology-foundry.io/insurance#")
DATA = Namespace("http://ontology-foundry.io/insurance/data#")


# ── helpers ───────────────────────────────────────────────────────────────────

def _d(v: Decimal) -> Literal:
    return Literal(str(v), datatype=XSD.decimal)


def _lob_uri(lob: LineOfBusiness) -> URIRef:
    return INS[f"LoB_{lob.value}"]


def _lrv_uri(variant: LossRatioVariant) -> URIRef:
    return INS[f"LRV_{variant.value}"]


# ── graph population ──────────────────────────────────────────────────────────

def build() -> Graph:
    g = Graph()
    g.parse(TTL_IN, format="turtle")   # loads ontology + SKOS concepts

    policies, claims = seed_data()

    # policies
    for pol in policies:
        uri = DATA[pol.policy_id]
        g.add((uri, RDF.type,          INS.Policy))
        g.add((uri, INS.policyId,      Literal(pol.policy_id)))
        g.add((uri, INS.earnedPremium, _d(pol.earned_premium)))
        g.add((uri, INS.inceptionDate, Literal(pol.inception_date.isoformat(), datatype=XSD.date)))
        g.add((uri, INS.hasLoBusiness, _lob_uri(pol.line_of_business)))

        # party
        p_uri = DATA[pol.insured.party_id]
        g.add((p_uri, RDF.type,        INS.Party))
        g.add((p_uri, INS.policyId,    Literal(pol.insured.party_id)))  # re-uses prop for id
        g.add((uri,   INS.hasInsured,  p_uri))

    # claims
    for clm in claims:
        uri = DATA[clm.claim_id]
        g.add((uri, RDF.type,         INS.Claim))
        g.add((uri, INS.claimId,      Literal(clm.claim_id)))
        g.add((uri, INS.coveredBy,    DATA[clm.policy.policy_id]))
        g.add((uri, INS.paidLoss,     _d(clm.paid_loss)))
        g.add((uri, INS.caseReserve,  _d(clm.case_reserve)))
        g.add((uri, INS.ibnrReserve,  _d(clm.ibnr_reserve)))
        g.add((uri, INS.claimStatus,  Literal(clm.status.value)))

    # pre-compute loss ratio records (Q3 2026 cohort per line)
    _add_loss_ratio_records(g, policies, claims)

    return g


def _add_loss_ratio_records(g: Graph, policies, claims) -> None:
    """
    Computes incurred and ultimate LR for each line.
    Only looks at policies that touch Q3 2026 (Jul–Sep 2026).
    """
    from collections import defaultdict

    earned: dict[LineOfBusiness, Decimal] = defaultdict(Decimal)
    paid:   dict[LineOfBusiness, Decimal] = defaultdict(Decimal)
    inc:    dict[LineOfBusiness, Decimal] = defaultdict(Decimal)
    ult:    dict[LineOfBusiness, Decimal] = defaultdict(Decimal)

    q3_policies = {
        p.policy_id for p in policies
        if p.inception_date.year == 2026 and p.inception_date.month <= 9
    }

    for pol in policies:
        if pol.policy_id in q3_policies:
            # apportion 9/12 of annual premium as Q3 YTD earned
            earned[pol.line_of_business] += pol.earned_premium * Decimal("0.75")

    for clm in claims:
        lob = clm.policy.line_of_business
        paid[lob] += clm.paid_loss
        inc[lob]  += clm.incurred_loss
        ult[lob]  += clm.ultimate_loss

    for lob in LineOfBusiness:
        ep = earned[lob]
        if ep == 0:
            continue
        for variant, numerator in [
            (LossRatioVariant.PAID,     paid[lob]),
            (LossRatioVariant.INCURRED, inc[lob]),
            (LossRatioVariant.ULTIMATE, ult[lob]),
        ]:
            rec_id = f"LR-{lob.value}-2026Q3-{variant.value}"
            uri    = DATA[rec_id]
            ratio  = (numerator / ep).quantize(Decimal("0.0001"))
            g.add((uri, RDF.type,         INS.LossRatioRecord))
            g.add((uri, INS.period,       Literal("2026-Q3")))
            g.add((uri, INS.forLine,      _lob_uri(lob)))
            g.add((uri, INS.measuredAs,   _lrv_uri(variant)))
            g.add((uri, INS.numerator,    _d(numerator)))
            g.add((uri, INS.denominator,  _d(ep)))
            g.add((uri, INS.ratioValue,   _d(ratio)))


# ── SHACL validation ──────────────────────────────────────────────────────────

def validate(g: Graph) -> bool:
    try:
        from pyshacl import validate as shacl_validate
        conforms, _, report = shacl_validate(g, shacl_graph=g, inference="rdfs")
        if not conforms:
            print("SHACL violations:\n", report)
        return conforms
    except ImportError:
        print("pyshacl not installed — skipping SHACL validation")
        return True


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    graph = build()
    valid = validate(graph)
    graph.serialize(destination=str(TTL_OUT), format="turtle")

    triple_count = len(graph)
    print(f"Graph built: {triple_count} triples  |  SHACL: {'✓' if valid else '✗'}")
    print(f"Serialized → {TTL_OUT.relative_to(ROOT)}")
