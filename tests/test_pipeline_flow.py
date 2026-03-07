from app.models import CHAgentOutput, OwnershipOutput, WebAgentOutput
from app.pipeline import OwnershipPipeline


class FakeWeb:
    def run(self, company_name: str):
        return WebAgentOutput(company=company_name, domain="example.com", legal_entity="Example Ltd", website_company_numbers=["12345678"])


class FakeCH:
    def run(self, web_output: WebAgentOutput):
        assert web_output.website_company_numbers == ["12345678"]
        return CHAgentOutput(ch_evidence_pack={"companies": [{"company_number": "12345678"}]}, ch_citations=["https://ch/12345678"])


class FakeOwn:
    def run(self, web_output: WebAgentOutput, ch_output: CHAgentOutput):
        return OwnershipOutput(
            company_name=web_output.company,
            domain=web_output.domain,
            legal_entity=web_output.legal_entity,
            ownership_type="Corporate",
            rationale="test",
            confidence=0.8,
            citations=ch_output.ch_citations,
        )


def test_pipeline_sequence(monkeypatch):
    pipe = OwnershipPipeline.__new__(OwnershipPipeline)
    pipe.web_agent = FakeWeb()
    pipe.ch_agent = FakeCH()
    pipe.ownership_agent = FakeOwn()
    result = pipe.run("Demo Co")
    assert result.ownership_output.ownership_type == "Corporate"
