from __future__ import annotations

import re
from dataclasses import asdict

from app.models import (
    CHAgentOutput,
    DomainResolutionResult,
    EntityResolutionResult,
    OwnershipEvidenceResult,
    OwnershipFacts,
    OwnershipOutput,
    WebAgentOutput,
)

BLOCKED_DOMAIN_SUFFIXES = {
    "find-and-update.company-information.service.gov.uk",
    "document-api.company-information.service.gov.uk",
    "companieshouse.gov.uk",
    "linkedin.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "instagram.com",
    "wikipedia.org",
}


def _source_item(rank: int, source: str, detail: str) -> dict:
    return {"rank": rank, "source": source, "detail": detail}


def resolve_official_domain(company_input: str, web_output: WebAgentOutput) -> DomainResolutionResult:
    domain = (web_output.domain or "").strip().lower()
    evidence = []
    conf = min(max(web_output.confidence, 0.0), 1.0)

    if web_output.citations:
        evidence.append(f"Web citations count={len(web_output.citations)}")
    if web_output.site_pages_checked:
        evidence.append(f"Website pages checked={len(web_output.site_pages_checked)}")

    if not domain:
        return DomainResolutionResult("", 0.0, evidence + ["No candidate domain returned"]) 

    blocked = any(domain == b or domain.endswith("." + b) for b in BLOCKED_DOMAIN_SUFFIXES)
    if blocked:
        return DomainResolutionResult("", 0.05, evidence + [f"Rejected non-official domain '{domain}'"])

    return DomainResolutionResult(domain, max(conf, 0.5), evidence + [f"Accepted official domain '{domain}'"])


def resolve_legal_entity(company_input: str, official_domain: str, web_output: WebAgentOutput, ch_output: CHAgentOutput) -> EntityResolutionResult:
    companies = (ch_output.ch_evidence_pack or {}).get("companies") or []
    legal_entity = (web_output.legal_entity or "").strip()
    company_number = ""
    entity_role = "Operating Company"
    evidence = []
    confidence = 0.4

    if companies:
        top = companies[0]
        profile = top.get("profile") or {}
        ch_name = (profile.get("company_name") or "").strip()
        company_number = str(top.get("company_number") or "").strip()
        if ch_name:
            legal_entity = ch_name
            confidence = 0.85
            evidence.append(f"Resolved from Companies House profile '{ch_name}'")
        if company_number:
            evidence.append(f"Company number resolved '{company_number}'")

    if not legal_entity:
        legal_entity = "[unverified]"
        evidence.append("Legal entity unresolved")
        confidence = min(confidence, 0.25)

    if official_domain and legal_entity and legal_entity != "[unverified]":
        dn = official_domain.split(".")[0]
        if dn and dn not in legal_entity.lower().replace(" ", ""):
            evidence.append("Domain and legal entity lexical mismatch detected")
            confidence = min(confidence, 0.55)

    return EntityResolutionResult(
        legal_entity_name=legal_entity,
        company_number=company_number,
        entity_role=entity_role,
        entity_confidence=confidence,
        entity_evidence=evidence,
    )


def _extract_control_band(natures: list[str]) -> str:
    text = " ".join(natures).lower()
    if "75" in text:
        return "75-100%"
    if "50" in text:
        return "50-75%"
    if "25" in text:
        return "25-50%"
    return "Unknown"


def extract_ownership_evidence(legal_entity: str, company_number: str, official_domain: str, ch_output: CHAgentOutput) -> OwnershipEvidenceResult:
    companies = (ch_output.ch_evidence_pack or {}).get("companies") or []
    facts = OwnershipFacts()
    evidence: list[str] = []
    ranked: list[dict] = []

    if not companies:
        facts.conflicting_evidence = True
        evidence.append("No Companies House companies found")
        ranked.append(_source_item(1, "Companies House", "No records in evidence pack"))
        return OwnershipEvidenceResult(facts, evidence, ranked)

    top = companies[0]
    pscs = ((top.get("pscs") or {}).get("items") or [])
    statements = ((top.get("psc_statements") or {}).get("items") or [])
    pdfs = top.get("downloaded_pdfs") or []

    ranked.append(_source_item(1, "Companies House PSC/API", f"PSC items={len(pscs)}; statements={len(statements)}"))

    if pscs:
        best = pscs[0]
        facts.psc_type = str(best.get("kind") or "")
        facts.psc_name = str(best.get("name") or "")
        natures = [str(x) for x in (best.get("natures_of_control") or [])]
        facts.control_band = _extract_control_band(natures)
        facts.parent_entities = [facts.psc_name] if facts.psc_name else []

        psc_name_lower = facts.psc_name.lower()
        facts.listed_parent = any(x in psc_name_lower for x in ["plc", "group plc", "holdings plc"])
        facts.private_equity_signal = any(x in psc_name_lower for x in ["bidco", "holdco", "capital", "partners", "equity"])
        facts.family_signal = any(x in psc_name_lower for x in ["family", "brothers", "sisters"])

        evidence.append(f"Primary PSC name='{facts.psc_name}', type='{facts.psc_type}', control='{facts.control_band}'")
    else:
        no_psc_statement = any("no registrable" in str(x.get("statement") or "").lower() for x in statements)
        facts.no_registrable_psc = bool(no_psc_statement)
        evidence.append("No PSC items present")

    pdf_signal = None
    for p in pdfs:
        pf = p.get("psc_facts") or {}
        if pf.get("psc_entity_name"):
            pdf_signal = pf
            break
    if pdf_signal:
        ranked.append(_source_item(1, "Companies House PSC/PDF", f"Extracted PSC entity '{pdf_signal.get('psc_entity_name')}'"))
        if facts.psc_name and str(pdf_signal.get("psc_entity_name")).strip().lower() != facts.psc_name.strip().lower():
            facts.conflicting_evidence = True
            evidence.append("PSC API and PSC PDF entity mismatch")

    return OwnershipEvidenceResult(facts, evidence, ranked)


def classify_ownership_type(extracted: OwnershipEvidenceResult) -> tuple[str, float, str]:
    f = extracted.ownership_facts

    if f.conflicting_evidence:
        return "Needs Review", 0.35, "Conflicting evidence guardrail"
    if f.listed_parent:
        return "Listed Parent", 0.85, "Listed parent rule"
    if f.private_equity_signal:
        return "Private Equity", 0.8, "PE signal rule"
    if f.family_signal:
        return "Family", 0.78, "Family signal rule"
    if f.no_registrable_psc:
        return "Diverse", 0.75, "No registrable PSC rule"

    t = (f.psc_type or "").lower()
    if "individual" in t and f.control_band in {"50-75%", "75-100%"}:
        return "Individual(s)", 0.8, "Individual PSC control-band rule"
    if "corporate" in t:
        return "Other / Special Structures", 0.62, "Corporate PSC fallback rule"

    return "Needs Review", 0.3, "Insufficient strong evidence"


def validate_row(
    company_input: str,
    domain_result: DomainResolutionResult,
    entity_result: EntityResolutionResult,
    extracted: OwnershipEvidenceResult,
    label: str,
    confidence: float,
) -> tuple[bool, str, list[str]]:
    issues: list[str] = []

    if not domain_result.official_domain:
        issues.append("Official domain unresolved or blocked")

    if entity_result.legal_entity_name == "[unverified]":
        issues.append("Legal entity unresolved")

    if entity_result.legal_entity_name != "[unverified]" and not entity_result.company_number:
        issues.append("Company number missing while legal entity appears resolved")

    if extracted.ownership_facts.conflicting_evidence:
        issues.append("Ownership evidence conflict detected")

    if confidence < 0.5 and label != "Needs Review":
        issues.append("Weak evidence should not produce a confident non-review label")

    if label == "Individual(s)" and "corporate" in (extracted.ownership_facts.psc_type or "").lower():
        issues.append("Contradiction: corporate PSC with Individual(s) label")

    needs_review = bool(issues) or label == "Needs Review"
    reason = "; ".join(issues) if issues else ("Model uncertainty escalated" if label == "Needs Review" else "")
    return needs_review, reason, issues


def build_reasoning_summary(
    domain_result: DomainResolutionResult,
    entity_result: EntityResolutionResult,
    extracted: OwnershipEvidenceResult,
    applied_rule: str,
) -> str:
    d = "; ".join(domain_result.domain_evidence[:2]) or "no domain evidence"
    e = "; ".join(entity_result.entity_evidence[:2]) or "no entity evidence"
    o = "; ".join(extracted.ownership_evidence[:2]) or "no ownership evidence"
    return f"Domain evidence: {d} | Legal entity evidence: {e} | Ownership evidence: {o} | Rule applied: {applied_rule}"


def run_staged_decision(company_input: str, web_output: WebAgentOutput, ch_output: CHAgentOutput) -> OwnershipOutput:
    domain_result = resolve_official_domain(company_input, web_output)
    entity_result = resolve_legal_entity(company_input, domain_result.official_domain, web_output, ch_output)
    extracted = extract_ownership_evidence(entity_result.legal_entity_name, entity_result.company_number, domain_result.official_domain, ch_output)
    label, conf, rule = classify_ownership_type(extracted)
    needs_review, review_reason, issues = validate_row(company_input, domain_result, entity_result, extracted, label, conf)

    if needs_review:
        label = "Needs Review"
        conf = min(conf, 0.45)

    reasoning_summary = build_reasoning_summary(domain_result, entity_result, extracted, rule)
    flags = issues

    return OwnershipOutput(
        company_name=company_input,
        official_domain=domain_result.official_domain,
        legal_entity_name=entity_result.legal_entity_name,
        company_number=entity_result.company_number,
        ownership_type=label,
        confidence=conf,
        needs_review=needs_review,
        review_reason=review_reason,
        reasoning_summary=reasoning_summary,
        ownership_facts=asdict(extracted.ownership_facts),
        citations=list(dict.fromkeys((ch_output.ch_citations or []) + (web_output.citations or []))),
        conflicts=[x for x in extracted.ownership_evidence if "mismatch" in x.lower() or "conflict" in x.lower()],
        flags=flags,
    )
