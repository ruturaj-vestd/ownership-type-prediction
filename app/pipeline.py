from __future__ import annotations

from app.agents.companies_house_agent import CompaniesHouseAgent
from app.agents.web_research_agent import WebResearchAgent
from app.decision_flow import run_staged_decision
from app.models import PipelineOutput


class OwnershipPipeline:
    def __init__(self) -> None:
        self.web_agent = WebResearchAgent()
        self.ch_agent = CompaniesHouseAgent()

    def run(self, company_name: str) -> PipelineOutput:
        web = self.web_agent.run(company_name)
        ch = self.ch_agent.run(web)
        own = run_staged_decision(company_name, web, ch)
        return PipelineOutput(web_agent_output=web, ch_agent_output=ch, ownership_output=own)
