from __future__ import annotations

import math
import re
from typing import Any

from app.models import WebAgentOutput
from app.utils.docx import read_docx_text
from app.utils.http import http_get_text
from app.utils.openai_client import openai_responses_text, safe_json_parse_strict

OPENAI_MODEL = "gpt-5.2"
PROTOCOL_DOCX_PATH = "./Research Protocol Checklist — v6.docx"

COMMON_PATHS = [
    "/",
    "/policies/",
    "/privacy/",
    "/privacy-policy/",
    "/terms/",
    "/terms-and-conditions/",
    "/legal/",
    "/legal-notice/",
    "/imprint/",
    "/about/",
    "/contact/",
]


def clamp01(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return default
        return max(0.0, min(1.0, v))
    except Exception:
        return default


def normalize_domain(domain: str) -> str:
    d = (domain or "").strip()
    d = re.sub(r"^https?://", "", d, flags=re.I)
    d = d.split("/")[0].strip().lower().strip(".")
    if not d:
        return ""
    if not re.search(r"[a-z0-9-]+\.[a-z]{2,}$", d):
        return ""
    return d


def extract_domains_from_text(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s)>\]]+", text or "", flags=re.I)
    bare = re.findall(r"\b(?![\w\.-]+@)([a-z0-9][a-z0-9\-\.]+\.[a-z]{2,})\b", text or "", flags=re.I)
    out: list[str] = []
    seen = set()
    for token in [*urls, *bare]:
        d = normalize_domain(token)
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out


def is_probably_social_or_directory(domain: str) -> bool:
    bad = {
        "facebook.com",
        "linkedin.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "wikipedia.org",
        "companieshouse.gov.uk",
        "find-and-update.company-information.service.gov.uk",
        "document-api.company-information.service.gov.uk",
        "opencorporates.com",
        "bloomberg.com",
        "crunchbase.com",
        "dnb.com",
    }
    return any(domain == b or domain.endswith("." + b) for b in bad)


def extract_company_numbers_uk(text: str) -> list[str]:
    pats = [r"\b(\d{8})\b", r"\b(SC\d{6})\b", r"\b(NI\d{6})\b", r"\b(OC\d{5})\b"]
    found: list[str] = []
    for p in pats:
        found.extend(re.findall(p, text or "", flags=re.I))
    out: list[str] = []
    seen = set()
    for x in found:
        y = re.sub(r"\s+", "", x).upper()
        if y not in seen:
            seen.add(y)
            out.append(y)
    return out


def extract_trading_name_disclosures(text: str) -> list[str]:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        l = raw.strip()
        if re.search(r"\btrading name of\b", l, flags=re.I) or re.search(r"\bis a trading name of\b", l, flags=re.I):
            lines.append(l[:400])
    if not lines:
        m = re.search(r"(.{0,200}\btrading name of\b.{0,400})", text or "", flags=re.I | re.S)
        if m:
            lines.append(re.sub(r"\s+", " ", m.group(1)).strip()[:600])
    return lines


def extract_legal_name_candidates(text: str) -> list[str]:
    candidates = []
    blocks = re.findall(r"(.{0,180}(Company\s*Number|Registered\s*Number).{0,220})", text or "", flags=re.I | re.S)
    for b, _ in blocks:
        candidates.append(re.sub(r"\s+", " ", b).strip()[:500])
    name_like = re.findall(r"\b([A-Z][A-Z0-9&',\.\-\s]{2,80}\b(?:LIMITED|LTD|LLP|PLC))\b", text or "")
    for n in name_like:
        candidates.append(re.sub(r"\s+", " ", n).strip())
    out: list[str] = []
    seen = set()
    for c in candidates:
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out[:12]


def sanitize_trading_disclosures(disclosures: list[str]) -> list[str]:
    out = []
    for d in disclosures:
        cleaned = re.sub(r"\s+", " ", d or "").strip()
        if cleaned:
            out.append(cleaned)
    return out


def extract_company_numbers_from_disclosure(disclosure: str) -> list[str]:
    return extract_company_numbers_uk(disclosure or "")


def probe_domain_for_legal(domain: str, company_hint: str) -> dict[str, Any]:
    base = f"https://{domain}"
    checked, all_text = [], ""
    reachable = 0
    for path in COMMON_PATHS:
        url = base + path
        code, txt = http_get_text(url)
        checked.append(url)
        if code and 200 <= code < 400 and txt:
            reachable += 1
            all_text += "\n\n" + txt[:120000]
    company_numbers = extract_company_numbers_uk(all_text)
    trading = extract_trading_name_disclosures(all_text)
    legal_snips = extract_legal_name_candidates(all_text)
    hint_hits = min((all_text.lower().count((company_hint or "").lower()) if company_hint else 0), 20)
    score = min(reachable, 4) + min(hint_hits, 10) * 0.2 + (2.5 if company_numbers else 0) + (2.0 if trading else 0) + (0.8 if legal_snips else 0)
    return {
        "domain": domain,
        "checked_pages": checked,
        "reachable_pages": reachable,
        "company_numbers": company_numbers,
        "trading_disclosures": trading,
        "legal_name_snippets": legal_snips,
        "hint_hits": hint_hits,
        "score": score,
    }


class WebResearchAgent:
    def __init__(self, model: str = OPENAI_MODEL, protocol_docx_path: str = PROTOCOL_DOCX_PATH):
        self.model = model
        rules = read_docx_text(protocol_docx_path, keep_blank_lines=True)
        self.system_guardrails = (
            "You must follow the Research Protocol Checklist below EXACTLY.\n"
            "- Extract facts only.\n- Do not guess.\n- Prefer primary sources.\n"
            "- Return strict JSON only.\n\n"
            f"RESEARCH PROTOCOL CHECKLIST:\n{rules}"
        )

    def run(self, company: str) -> WebAgentOutput:
        single_prompt = (
            "Use web_search and return STRICT JSON ONLY for official domain + legal entity fact extraction. "
            "Never choose registry/document-host/social URLs as official domain. "
            f"Company: {company}. "
            "Schema: {\"search_query\":\"string\",\"domain\":\"string\",\"legal_entity\":\"string\",\"citations\":[\"url\"],\"confidence\":number,\"notes\":\"string\"}"
        )

        extracted = safe_json_parse_strict(
            openai_responses_text(
                model=self.model,
                messages=[{"role": "system", "content": self.system_guardrails}, {"role": "user", "content": single_prompt}],
                tools=[{"type": "web_search"}],
            )
        )

        search_query = str(extracted.get("search_query") or f"{company} official website legal entity legal notice").strip()
        domain = normalize_domain(str(extracted.get("domain") or ""))
        legal_entity = str(extracted.get("legal_entity") or "").strip()
        citations = [str(x).strip() for x in (extracted.get("citations") or []) if str(x).strip()]
        confidence = clamp01(extracted.get("confidence"), 0.0)
        notes = str(extracted.get("notes") or "")

        text_for_domains = "\n".join([domain] + citations + [notes])
        raw_domains = extract_domains_from_text(text_for_domains)
        candidate_domains = [d for d in raw_domains if not is_probably_social_or_directory(d)][:5]
        if domain and domain not in candidate_domains and not is_probably_social_or_directory(domain):
            candidate_domains.insert(0, domain)

        domain_probe_results = {d: probe_domain_for_legal(d, company) for d in candidate_domains}
        best_domain, best_score = "", -1.0
        for d, res in domain_probe_results.items():
            if float(res.get("score", 0)) > best_score:
                best_domain, best_score = d, float(res.get("score", 0))

        site_pages_checked: list[str] = []
        website_company_numbers: list[str] = []
        website_trading_disclosures: list[str] = []
        website_legal_name_snippets: list[str] = []
        if best_domain:
            best_res = domain_probe_results[best_domain]
            site_pages_checked = best_res.get("checked_pages", [])
            website_trading_disclosures = sanitize_trading_disclosures(best_res.get("trading_disclosures", []))
            primary_numbers = extract_company_numbers_from_disclosure(website_trading_disclosures[0]) if website_trading_disclosures else []
            website_company_numbers = primary_numbers or best_res.get("company_numbers", [])
            website_legal_name_snippets = best_res.get("legal_name_snippets", [])

        if best_domain and best_domain != domain:
            domain = best_domain
            confidence = min(max(confidence, 0.6), 0.9)

        if website_trading_disclosures:
            legal_entity = website_trading_disclosures[0] + (
                f" | company_numbers_found={', '.join(website_company_numbers)}" if website_company_numbers else ""
            )
        elif website_company_numbers and legal_entity:
            legal_entity = f"{legal_entity} (company_numbers_found={', '.join(website_company_numbers)})"

        flags = []
        if not domain:
            flags.append("domain_missing_or_invalid")
            confidence = min(confidence, 0.35)
        if not legal_entity:
            legal_entity = "[unverified]"
            flags.append("legal_entity_missing_set_unverified")
            confidence = min(confidence, 0.35)
        if not citations:
            flags.append("no_citations_returned")
            confidence = min(confidence, 0.35)

        return WebAgentOutput(
            company=company,
            search_query=search_query,
            evidence_text=str(extracted),
            candidate_domains=candidate_domains,
            domain_probe_results=domain_probe_results,
            site_pages_checked=site_pages_checked,
            website_company_numbers=website_company_numbers,
            website_trading_disclosures=website_trading_disclosures,
            website_legal_name_snippets=website_legal_name_snippets,
            domain=domain,
            legal_entity=legal_entity,
            citations=citations,
            confidence=confidence,
            notes=notes,
            conflicts=[],
            flags=flags,
            log=[
                "OpenAI calls for web agent: 1",
                f"Best domain: {best_domain or '[none]'} score={best_score:.2f}",
                f"Website company numbers: {website_company_numbers}",
                f"Final domain: {domain}",
            ],
        )
