from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


OwnershipType = Literal[
    "Individual",
    "Family",
    "Private Equity",
    "Corporate",
    "Publicly Listed",
    "Government/State",
    "Trust/Foundation",
    "Management/Employee",
    "Unknown",
]


@dataclass
class EvidenceItem:
    source: str
    detail: str
    url: str | None = None

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class WebResearchResult:
    company_name: str
    findings: list[str] = field(default_factory=list)
    probable_owner_signals: list[str] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class CompaniesHouseResult:
    queried_name: str
    matched_company_name: str | None = None
    company_number: str | None = None
    company_url: str | None = None
    psc_snippets: list[str] = field(default_factory=list)
    filing_snippets: list[str] = field(default_factory=list)
    officers_snippets: list[str] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class OwnershipDecision:
    ownership_type: OwnershipType
    confidence: float
    rationale: list[str] = field(default_factory=list)
    evidence: list[EvidenceItem] = field(default_factory=list)

    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class PipelineOutput:
    web_research: WebResearchResult
    companies_house: CompaniesHouseResult
    final_decision: OwnershipDecision

    def model_dump(self) -> dict:
        return asdict(self)
