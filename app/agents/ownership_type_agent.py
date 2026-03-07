from __future__ import annotations

from collections import defaultdict

from app.models import CompaniesHouseResult, EvidenceItem, OwnershipDecision, WebResearchResult


TYPE_RULES: dict[str, list[str]] = {
    "Private Equity": ["private equity", "capital partners", "acquired by", "portfolio company", "bidco", "holdco"],
    "Publicly Listed": ["plc", "listed", "stock exchange", "nasdaq", "nyse", "lse"],
    "Government/State": ["government", "council", "ministry", "crown", "state-owned"],
    "Family": ["family", "brothers", "sisters", "spouse", "daughter", "son"],
    "Trust/Foundation": ["trust", "foundation", "charitable", "trustee"],
    "Management/Employee": ["employee-owned", "management buyout", "esop"],
    "Corporate": ["subsidiary", "ultimate parent", "holdings", "group"],
    "Individual": ["person with significant control", "individual", "sole shareholder"],
}


class OwnershipTypeAgent:
    """Determines ownership type using deterministic, auditable rules."""

    def run(self, web: WebResearchResult, ch: CompaniesHouseResult) -> OwnershipDecision:
        corpus = "\n".join(web.findings + web.probable_owner_signals + ch.psc_snippets + ch.filing_snippets + ch.officers_snippets).lower()

        scores = defaultdict(int)
        evidence = []

        for ownership_type, phrases in TYPE_RULES.items():
            for phrase in phrases:
                if phrase in corpus:
                    scores[ownership_type] += 1
                    evidence.append(
                        EvidenceItem(
                            source="Rule hit",
                            detail=f"Matched phrase '{phrase}' => {ownership_type}",
                        )
                    )

        if not scores:
            return OwnershipDecision(
                ownership_type="Unknown",
                confidence=0.2,
                rationale=["No high-confidence ownership indicators found in web or Companies House snippets."],
                evidence=evidence,
            )

        best_type, best_score = sorted(scores.items(), key=lambda x: x[1], reverse=True)[0]
        total = sum(scores.values())
        confidence = round(min(0.95, 0.45 + (best_score / max(total, 1)) * 0.5), 2)

        rationale = [
            f"Top ownership signal category: {best_type}.",
            f"Rule hits: {best_score} of {total} total matched ownership signals.",
            "Decision is based on extracted web and Companies House snippets, with transparent phrase matches.",
        ]

        return OwnershipDecision(
            ownership_type=best_type,
            confidence=confidence,
            rationale=rationale,
            evidence=evidence,
        )
