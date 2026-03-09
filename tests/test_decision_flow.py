from app.decision_flow import (
    classify_ownership_type,
    extract_ownership_evidence,
    resolve_official_domain,
    resolve_legal_entity,
    run_staged_decision,
    validate_row,
)
from app.models import CHAgentOutput, OwnershipEvidenceResult, OwnershipFacts, WebAgentOutput


def make_web(**kwargs):
    base = WebAgentOutput(company="Acme", domain="acme.com", legal_entity="Acme Limited", confidence=0.7)
    for k, v in kwargs.items():
        setattr(base, k, v)
    return base


def make_ch(companies):
    return CHAgentOutput(ch_evidence_pack={"companies": companies}, ch_citations=["https://ch"], log=[])


def test_group_site_vs_operating_company_site_flags_review_when_mismatch():
    web = make_web(domain="group-holdings.com", legal_entity="Acme Trading Ltd")
    ch = make_ch([{"company_number": "12345678", "profile": {"company_name": "Acme Operations Limited"}, "pscs": {"items": []}, "psc_statements": {"items": []}, "downloaded_pdfs": []}])
    out = run_staged_decision("Acme", web, ch)
    assert out.needs_review is True


def test_registry_domain_rejected():
    web = make_web(domain="find-and-update.company-information.service.gov.uk")
    res = resolve_official_domain("Acme", web)
    assert res.official_domain == ""


def test_wrong_legal_entity_fuzzy_choice_is_downgraded_without_company_number():
    web = make_web(legal_entity="Acme Maybe Ltd")
    ch = make_ch([])
    out = run_staged_decision("Acme", web, ch)
    assert out.needs_review is True
    assert "Company number" in out.review_reason or "unresolved" in out.review_reason.lower()


def test_corporate_psc_not_individual_label():
    extracted = OwnershipEvidenceResult(ownership_facts=OwnershipFacts(psc_type="corporate-entity-person-with-significant-control", psc_name="BidCo Ltd", control_band="75-100%"))
    label, _, _ = classify_ownership_type(extracted)
    assert label in {"Private Equity", "Other / Special Structures"}


def test_no_registrable_psc_maps_diverse():
    extracted = OwnershipEvidenceResult(ownership_facts=OwnershipFacts(no_registrable_psc=True))
    label, _, _ = classify_ownership_type(extracted)
    assert label == "Diverse"


def test_mixed_public_private_conflict_forces_needs_review():
    extracted = OwnershipEvidenceResult(ownership_facts=OwnershipFacts(listed_parent=True, private_equity_signal=True, conflicting_evidence=True))
    label, conf, _ = classify_ownership_type(extracted)
    needs_review, _, _ = validate_row("Acme", resolve_official_domain("Acme", make_web()), resolve_legal_entity("Acme", "acme.com", make_web(), make_ch([])), extracted, label, conf)
    assert needs_review is True


def test_conflicting_psc_api_and_pdf_returns_needs_review():
    company = {
        "company_number": "12345678",
        "profile": {"company_name": "Acme Limited"},
        "pscs": {"items": [{"kind": "corporate-entity-person-with-significant-control", "name": "Parent A", "natures_of_control": ["ownership-of-shares-75-to-100-percent"]}]},
        "psc_statements": {"items": []},
        "downloaded_pdfs": [{"psc_facts": {"psc_entity_name": "Parent B"}}],
    }
    ev = extract_ownership_evidence("Acme Limited", "12345678", "acme.com", make_ch([company]))
    label, _, _ = classify_ownership_type(ev)
    assert ev.ownership_facts.conflicting_evidence is True
    assert label == "Needs Review"


def test_listed_parent_rule():
    extracted = OwnershipEvidenceResult(ownership_facts=OwnershipFacts(listed_parent=True, psc_name="Acme Group PLC"))
    label, _, _ = classify_ownership_type(extracted)
    assert label == "Listed Parent"
