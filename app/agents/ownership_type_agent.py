from __future__ import annotations

import math
from typing import Any

from app.models import CHAgentOutput, OwnershipOutput, WebAgentOutput
from app.utils.docx import read_docx_text
from app.utils.openai_client import openai_responses_text, safe_json_parse_strict

CLASSIFIER_SYSTEM = """
You are an ownership classification auditor.
- Use ONLY provided Companies House evidence for ownership determination.
- Do not guess.
- Output strict JSON only.
""".strip()


def clamp01(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return max(0.0, min(1.0, v))
    except Exception:
        return default


def extract_ch_primary_signals(ch_evidence_pack: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"companies": [], "global_flags": []}
    companies = (ch_evidence_pack or {}).get("companies") or []
    if not companies:
        out["global_flags"].append("ch_evidence_pack_missing_companies")
        return out
    for c in companies:
        prof = c.get("profile") or {}
        pscs = c.get("pscs") or {}
        stmts = c.get("psc_statements") or {}
        offs = c.get("officers") or {}
        filings = c.get("filings") or {}
        pdfs = c.get("downloaded_pdfs") or []
        out["companies"].append(
            {
                "company_number": c.get("company_number"),
                "profile": {
                    "company_name": prof.get("company_name"),
                    "company_status": prof.get("company_status"),
                    "type": prof.get("type"),
                    "date_of_creation": prof.get("date_of_creation"),
                },
                "pscs": {"total_results": pscs.get("total_results"), "items": (pscs.get("items") or [])[:25]},
                "psc_statements": {"total_results": stmts.get("total_results"), "items": (stmts.get("items") or [])[:25]},
                "officers": {"total_results": offs.get("total_results"), "items": (offs.get("items") or [])[:15]},
                "filings_summary": {"total_count": filings.get("total_count"), "top_items": (filings.get("items") or [])[:20]},
                "supplemental_pdf_psc_facts": [
                    {"document_id": p.get("document_id"), "type": p.get("type"), "date": p.get("date"), "psc_facts": p.get("psc_facts")}
                    for p in pdfs[:6]
                    if (p.get("psc_facts") or {}).get("psc_entity_name")
                    or (p.get("psc_facts") or {}).get("psc_registration_number")
                    or (p.get("psc_facts") or {}).get("control_signals")
                ],
            }
        )
    return out


class OwnershipTypeAgent:
    def __init__(self, model: str = "gpt-5.2", taxonomy_docx_path: str = "./Controlling Ownership - Types and Definition .docx"):
        self.model = model
        self.taxonomy_text = read_docx_text(taxonomy_docx_path)

    def run(self, web_output: WebAgentOutput, ch_output: CHAgentOutput) -> OwnershipOutput:
        ch_primary_signals = extract_ch_primary_signals(ch_output.ch_evidence_pack)
        ch_flags = [s for s in ch_output.log if isinstance(s, str) and ("error" in s.lower() or "empty" in s.lower() or "warn" in s.lower())]

        user_prompt = f"""
Classify ownership using taxonomy below.
TAXONOMY:\n{self.taxonomy_text}
company_name: {web_output.company}
domain: {web_output.domain}
legal_entity: {web_output.legal_entity}
COMPANIES HOUSE EVIDENCE SUMMARY:
{ch_primary_signals}
web_citations: {web_output.citations}
ch_citations: {ch_output.ch_citations}
web_flags: {web_output.flags}
ch_flags: {ch_flags}
Return strict JSON:
{{
  "ownership_type": "string",
  "rationale": "string",
  "confidence": number,
  "conflicts": ["string"],
  "flags": ["string"]
}}
""".strip()

        cls = safe_json_parse_strict(
            openai_responses_text(
                model=self.model,
                messages=[{"role": "system", "content": CLASSIFIER_SYSTEM}, {"role": "user", "content": user_prompt}],
            )
        )

        ownership_type = str(cls.get("ownership_type") or "Unknown").strip() or "Unknown"
        rationale = str(cls.get("rationale") or "").strip()
        confidence = clamp01(cls.get("confidence"), 0.0)
        cls_conflicts = [str(x).strip() for x in (cls.get("conflicts") or []) if str(x).strip()]
        cls_flags = [str(x).strip() for x in (cls.get("flags") or []) if str(x).strip()]

        if "ch_evidence_pack_missing_companies" in ch_primary_signals.get("global_flags", []):
            ownership_type = "Unknown"
            confidence = min(confidence, 0.35)
            rationale = rationale or "Companies House evidence pack did not include any companies; cannot determine ownership."

        citations = list(dict.fromkeys(ch_output.ch_citations + [x for x in web_output.citations if x not in ch_output.ch_citations]))
        conflicts = list(dict.fromkeys(web_output.conflicts + cls_conflicts))
        flags = list(dict.fromkeys(web_output.flags + ch_primary_signals.get("global_flags", []) + ch_flags + cls_flags))

        if not web_output.domain:
            flags.append("domain_missing_in_final")
            confidence = min(confidence, 0.4)
        if web_output.legal_entity in ("", "[unverified]"):
            flags.append("legal_entity_unverified_in_final")
            confidence = min(confidence, 0.5)

        return OwnershipOutput(
            company_name=web_output.company or "[unverified]",
            official_domain=web_output.domain,
            legal_entity_name=web_output.legal_entity or "[unverified]",
            company_number="",
            ownership_type=ownership_type,
            confidence=confidence,
            needs_review=ownership_type in {"Unknown", "Needs Review"},
            review_reason="" if ownership_type not in {"Unknown", "Needs Review"} else "Legacy classifier uncertainty",
            reasoning_summary=rationale,
            ownership_facts={},
            citations=list(dict.fromkeys(citations)),
            conflicts=list(dict.fromkeys([x for x in conflicts if x])),
            flags=list(dict.fromkeys([x for x in flags if x])),
        )
