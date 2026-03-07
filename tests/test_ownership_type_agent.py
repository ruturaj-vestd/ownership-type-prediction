from app.agents.ownership_type_agent import OwnershipTypeAgent
from app.models import CompaniesHouseResult, WebResearchResult


def test_private_equity_signal_wins():
    agent = OwnershipTypeAgent()
    web = WebResearchResult(
        company_name="Acme Ltd",
        findings=["Acme was acquired by ABC Capital Partners and is a portfolio company."],
        probable_owner_signals=["Detected keyword 'private equity' in web snippets"],
    )
    ch = CompaniesHouseResult(
        queried_name="Acme Ltd",
        psc_snippets=["XYZ BidCo Limited is listed as person with significant control."],
    )
    result = agent.run(web, ch)
    assert result.ownership_type == "Private Equity"
    assert result.confidence >= 0.5


def test_unknown_when_no_signals():
    agent = OwnershipTypeAgent()
    web = WebResearchResult(company_name="NoData")
    ch = CompaniesHouseResult(queried_name="NoData")
    result = agent.run(web, ch)
    assert result.ownership_type == "Unknown"
