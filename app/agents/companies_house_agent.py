from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote_plus

from app.models import CompaniesHouseResult, EvidenceItem
from app.utils.http import get_text

CH_BASE = "https://find-and-update.company-information.service.gov.uk"


class CompaniesHouseAgent:
    """Finds best matching legal entity and pulls ownership-relevant snippets."""

    def run(self, company_name: str) -> CompaniesHouseResult:
        search_url = f"{CH_BASE}/search/companies?q={quote_plus(company_name)}"
        try:
            search_html = get_text(search_url)
        except Exception as exc:  # noqa: BLE001
            return CompaniesHouseResult(
                queried_name=company_name,
                evidence=[EvidenceItem(source="Companies House search", detail=f"Failed search: {exc}", url=search_url)],
            )

        match = re.search(r'<li class="type-company">.*?<a href="(?P<href>/company/[^"]+)".*?>(?P<name>.*?)</a>', search_html, re.S)
        if match is None:
            return CompaniesHouseResult(
                queried_name=company_name,
                evidence=[EvidenceItem(source="Companies House search", detail="No company match found", url=search_url)],
            )

        href = unescape(match.group("href"))
        matched_name = self._clean(match.group("name"))
        company_url = f"{CH_BASE}{href}"
        company_number = self._extract_company_number(href)

        result = CompaniesHouseResult(
            queried_name=company_name,
            matched_company_name=matched_name,
            company_number=company_number,
            company_url=company_url,
            evidence=[EvidenceItem(source="Companies House search", detail=f"Matched {matched_name}", url=search_url)],
        )

        self._collect_page_snippets(result, company_url, "Company profile")
        self._collect_page_snippets(result, f"{company_url}/officers", "Officers")
        self._collect_page_snippets(result, f"{company_url}/persons-with-significant-control", "PSC")
        self._collect_page_snippets(result, f"{company_url}/filing-history", "Filing History")
        return result

    @staticmethod
    def _extract_company_number(path: str) -> str | None:
        m = re.search(r"/company/([^/?#]+)", path)
        return m.group(1) if m else None

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"<.*?>", " ", text)
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    def _collect_page_snippets(self, result: CompaniesHouseResult, url: str, label: str) -> None:
        try:
            html = get_text(url)
        except Exception as exc:  # noqa: BLE001
            result.evidence.append(EvidenceItem(source=label, detail=f"Could not fetch: {exc}", url=url))
            return

        text_chunks = re.findall(r"<(?:p|dd|td|span)[^>]*>(.*?)</(?:p|dd|td|span)>", html, re.S)
        snippets = []
        for chunk in text_chunks:
            cleaned = self._clean(chunk)
            if cleaned and len(cleaned) > 25:
                snippets.append(cleaned)

        snippets = list(dict.fromkeys(snippets))[:10]

        if label == "PSC":
            result.psc_snippets.extend(snippets)
        elif label == "Filing History":
            result.filing_snippets.extend(snippets)
        elif label == "Officers":
            result.officers_snippets.extend(snippets)

        if snippets:
            result.evidence.append(EvidenceItem(source=label, detail=snippets[0], url=url))
        else:
            result.evidence.append(EvidenceItem(source=label, detail="No structured snippets extracted", url=url))
