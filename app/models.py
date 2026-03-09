from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class WebAgentOutput:
    company: str
    search_query: str = ""
    evidence_text: str = ""
    candidate_domains: list[str] = field(default_factory=list)
    domain_probe_results: dict[str, Any] = field(default_factory=dict)
    site_pages_checked: list[str] = field(default_factory=list)
    website_company_numbers: list[str] = field(default_factory=list)
    website_trading_disclosures: list[str] = field(default_factory=list)
    website_legal_name_snippets: list[str] = field(default_factory=list)
    domain: str = ""
    legal_entity: str = ""
    citations: list[str] = field(default_factory=list)
    confidence: float = 0.0
    notes: str = ""
    conflicts: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CHAgentOutput:
    ch_evidence_pack: dict[str, Any] = field(default_factory=dict)
    ch_citations: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DomainResolutionResult:
    official_domain: str = ""
    domain_confidence: float = 0.0
    domain_evidence: list[str] = field(default_factory=list)


@dataclass
class EntityResolutionResult:
    legal_entity_name: str = ""
    company_number: str = ""
    entity_role: str = ""
    entity_confidence: float = 0.0
    entity_evidence: list[str] = field(default_factory=list)


@dataclass
class OwnershipFacts:
    psc_type: str = ""
    psc_name: str = ""
    control_band: str = ""
    parent_entities: list[str] = field(default_factory=list)
    listed_parent: bool = False
    private_equity_signal: bool = False
    family_signal: bool = False
    no_registrable_psc: bool = False
    conflicting_evidence: bool = False


@dataclass
class OwnershipEvidenceResult:
    ownership_facts: OwnershipFacts = field(default_factory=OwnershipFacts)
    ownership_evidence: list[str] = field(default_factory=list)
    source_ranked_evidence: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OwnershipOutput:
    company_name: str
    official_domain: str
    legal_entity_name: str
    company_number: str
    ownership_type: str
    confidence: float
    needs_review: bool
    review_reason: str
    reasoning_summary: str
    ownership_facts: dict[str, Any] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def domain(self) -> str:
        return self.official_domain

    @property
    def legal_entity(self) -> str:
        return self.legal_entity_name

    @property
    def ownership_type_label(self) -> str:
        return self.ownership_type

    @property
    def rationale(self) -> str:
        return self.reasoning_summary

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineOutput:
    web_agent_output: WebAgentOutput
    ch_agent_output: CHAgentOutput
    ownership_output: OwnershipOutput

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)
