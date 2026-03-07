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
class OwnershipOutput:
    company_name: str
    domain: str
    legal_entity: str
    ownership_type: str
    rationale: str
    confidence: float
    citations: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineOutput:
    web_agent_output: WebAgentOutput
    ch_agent_output: CHAgentOutput
    ownership_output: OwnershipOutput

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)
