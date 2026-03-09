from app.models import CHAgentOutput, WebAgentOutput
from app.pipeline import OwnershipPipeline


class FakeWeb:
    def run(self, company_name: str):
        return WebAgentOutput(company=company_name, domain="example.com", legal_entity="Example Ltd", website_company_numbers=["12345678"])


class FakeCH:
    def run(self, web_output: WebAgentOutput):
        assert web_output.website_company_numbers == ["12345678"]
        return CHAgentOutput(
            ch_evidence_pack={
                "companies": [
                    {
                        "company_number": "12345678",
                        "profile": {"company_name": "Example Ltd"},
                        "pscs": {"items": [{"kind": "individual-person-with-significant-control", "name": "John Owner", "natures_of_control": ["ownership-of-shares-75-to-100-percent"]}]},
                        "psc_statements": {"items": []},
                        "downloaded_pdfs": [],
                    }
                ]
            },
            ch_citations=["https://ch/12345678"],
        )


def test_pipeline_sequence():
    pipe = OwnershipPipeline.__new__(OwnershipPipeline)
    pipe.web_agent = FakeWeb()
    pipe.ch_agent = FakeCH()
    result = pipe.run("Demo Co")
    assert result.ownership_output.ownership_type in {"Individual(s)", "Needs Review"}
