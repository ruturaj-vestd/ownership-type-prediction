from __future__ import annotations

import re
from html import unescape

from app.models import EvidenceItem, WebResearchResult
from app.utils.http import get_text

KEYWORDS = [
    "private equity",
    "listed",
    "stock exchange",
    "family owned",
    "founder-owned",
    "subsidiary",
    "government-owned",
    "employee-owned",
    "trust",
]


class WebResearchAgent:
    """Collects high-signal web snippets about ownership."""

    def run(self, company_name: str) -> WebResearchResult:
        query = f"{company_name} ownership parent company investors"
        url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"

        try:
            html = get_text(url)
        except Exception as exc:  # noqa: BLE001
            return WebResearchResult(
                company_name=company_name,
                evidence=[EvidenceItem(source="Web search", detail=f"Failed to fetch results: {exc}", url=url)],
            )

        findings: list[str] = []
        evidence: list[EvidenceItem] = []

        pattern = re.compile(r'<a rel="nofollow" class="result__a" href="(?P<href>[^"]+)">(?P<title>.*?)</a>.*?<a class="result__snippet".*?>(?P<snippet>.*?)</a>', re.S)

        for m in pattern.finditer(html):
            title = self._clean(m.group("title"))
            snippet = self._clean(m.group("snippet"))
            link = unescape(m.group("href"))
            combined = " - ".join([p for p in [title, snippet] if p])
            if combined:
                findings.append(combined)
                evidence.append(EvidenceItem(source="Web search", detail=combined[:450], url=link))
            if len(findings) >= 8:
                break

        probable_owner_signals = []
        joined = "\n".join(findings).lower()
        for keyword in KEYWORDS:
            if keyword in joined:
                probable_owner_signals.append(f"Detected keyword '{keyword}' in web snippets")

        return WebResearchResult(company_name=company_name, findings=findings, probable_owner_signals=probable_owner_signals, evidence=evidence)

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"<.*?>", " ", text)
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()
