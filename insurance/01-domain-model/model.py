"""
Insurance domain model — core entities for loss ratio analysis.
Covers: Party, Policy, Claim, LossRatioRecord.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


# ── enumerations ──────────────────────────────────────────────────────────────

class LineOfBusiness(str, Enum):
    MARINE      = "Marine"
    PROPERTY    = "Property"
    LIABILITY   = "Liability"
    MOTOR       = "Motor"


class ClaimStatus(str, Enum):
    OPEN    = "Open"
    CLOSED  = "Closed"
    IBNR    = "IBNR"


class LossRatioVariant(str, Enum):
    PAID        = "Paid"        # paid losses / earned premium
    INCURRED    = "Incurred"    # (paid + case reserve) / earned premium
    ULTIMATE    = "Ultimate"    # (incurred + IBNR) / earned premium
    ATTRITIONAL = "Attritional" # excluding cat events
    NET         = "Net"         # after reinsurance recovery


# ── entities ──────────────────────────────────────────────────────────────────

@dataclass
class Party:
    party_id: str
    name: str
    role: str           # Insured | Broker | Reinsurer | Claimant


@dataclass
class Policy:
    policy_id: str
    insured: Party
    line_of_business: LineOfBusiness
    inception_date: date
    expiry_date: date
    earned_premium: Decimal


@dataclass
class Claim:
    claim_id: str
    policy: Policy
    status: ClaimStatus
    reported_date: date
    paid_loss: Decimal
    case_reserve: Decimal
    ibnr_reserve: Decimal = Decimal("0")

    @property
    def incurred_loss(self) -> Decimal:
        return self.paid_loss + self.case_reserve

    @property
    def ultimate_loss(self) -> Decimal:
        return self.incurred_loss + self.ibnr_reserve


@dataclass
class LossRatioRecord:
    """Computed loss ratio for a cohort (line + period)."""
    line_of_business: LineOfBusiness
    period: str                     # e.g. "2026-Q3"
    variant: LossRatioVariant
    numerator: Decimal
    denominator: Decimal            # earned premium for the cohort

    @property
    def ratio(self) -> Decimal:
        if self.denominator == 0:
            return Decimal("0")
        return (self.numerator / self.denominator).quantize(Decimal("0.0001"))


# ── seed data ─────────────────────────────────────────────────────────────────

def seed_data() -> tuple[list[Policy], list[Claim]]:
    """Returns a small but realistic portfolio for three lines."""

    broker  = Party("P-BRK-01", "Marsh Ltd",         "Broker")
    marine1 = Party("P-INS-01", "Acme Shipping Co",  "Insured")
    prop1   = Party("P-INS-02", "Riverside Warehouses","Insured")
    liab1   = Party("P-INS-03", "TechCorp Ltd",       "Insured")

    policies = [
        Policy("POL-MAR-001", marine1, LineOfBusiness.MARINE,
               date(2026, 1, 1), date(2026, 12, 31), Decimal("1_200_000")),
        Policy("POL-MAR-002", marine1, LineOfBusiness.MARINE,
               date(2026, 4, 1), date(2027, 3, 31),  Decimal("800_000")),
        Policy("POL-PRP-001", prop1,   LineOfBusiness.PROPERTY,
               date(2026, 1, 1), date(2026, 12, 31), Decimal("2_500_000")),
        Policy("POL-LIB-001", liab1,   LineOfBusiness.LIABILITY,
               date(2026, 1, 1), date(2026, 12, 31), Decimal("600_000")),
    ]

    claims = [
        Claim("CLM-001", policies[0], ClaimStatus.OPEN,
              date(2026, 7, 10), Decimal("320_000"), Decimal("80_000")),
        Claim("CLM-002", policies[0], ClaimStatus.CLOSED,
              date(2026, 8, 5),  Decimal("150_000"), Decimal("0")),
        Claim("CLM-003", policies[1], ClaimStatus.OPEN,
              date(2026, 9, 1),  Decimal("95_000"),  Decimal("55_000"), Decimal("30_000")),
        Claim("CLM-004", policies[2], ClaimStatus.OPEN,
              date(2026, 7, 20), Decimal("800_000"), Decimal("400_000")),
        Claim("CLM-005", policies[3], ClaimStatus.IBNR,
              date(2026, 9, 15), Decimal("0"),       Decimal("0"),      Decimal("120_000")),
    ]

    return policies, claims
