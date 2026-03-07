from app.agents.companies_house_agent import CompaniesHouseAgent
from app.models import WebAgentOutput


class FakeCHAgent(CompaniesHouseAgent):
    def __init__(self):
        self.api_key = "test"

    def search_companies(self, query: str, items_per_page: int = 10) -> dict:
        if "Acme" in query:
            return {"items": [{"company_number": "11112222", "title": "ACME LIMITED"}]}
        return {"items": []}


def test_resolve_company_numbers_fallback_from_legal_text_and_search():
    agent = FakeCHAgent()
    web = WebAgentOutput(
        company="Acme",
        legal_entity="Acme is a trading name of Acme Limited (12345678)",
        website_company_numbers=[],
    )
    nums, logs = agent.resolve_company_numbers(web)
    assert "12345678" in nums
    assert "11112222" in nums
    assert any("numbers extracted from legal_entity" in line for line in logs)


def test_summarize_highest_holder_prefers_psc_api():
    agent = FakeCHAgent()
    company_record = {
        "pscs": {
            "items": [
                {
                    "name": "Holder A",
                    "kind": "corporate-entity-person-with-significant-control",
                    "natures_of_control": ["ownership-of-shares-75-to-100-percent"],
                },
                {
                    "name": "Holder B",
                    "kind": "individual-person-with-significant-control",
                    "natures_of_control": ["ownership-of-shares-25-to-50-percent"],
                },
            ]
        },
        "downloaded_pdfs": [],
    }
    summary = agent.summarize_highest_holder(company_record)
    assert summary["highest_holder"] == "Holder A"
    assert summary["source"] == "ch_psc_api"
