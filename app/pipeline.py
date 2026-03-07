from __future__ import annotations

from app.agents.companies_house_agent import CompaniesHouseAgent
from app.agents.ownership_type_agent import OwnershipTypeAgent
from app.agents.web_research_agent import WebResearchAgent
from app.models import PipelineOutput


class OwnershipPipeline:
    def __init__(self) -> None:
        self.web_agent = WebResearchAgent()
        self.ch_agent = CompaniesHouseAgent()
        self.ownership_agent = OwnershipTypeAgent()

    def run(self, company_name: str) -> PipelineOutput:
        web_result = self.web_agent.run(company_name)
        ch_result = self.ch_agent.run(company_name)
        decision = self.ownership_agent.run(web_result, ch_result)
        return PipelineOutput(web_research=web_result, companies_house=ch_result, final_decision=decision)
