from __future__ import annotations

import json

import streamlit as st

from app.pipeline import OwnershipPipeline

st.set_page_config(page_title="Ownership Type Predictor", layout="wide")
st.title("Ownership Type Predictor")
st.caption("Three-agent pipeline: Web research -> Companies House -> Ownership type decision")

company_name = st.text_input("Enter company name", placeholder="e.g., Rolls-Royce Holdings")

if st.button("Run analysis", type="primary") and company_name.strip():
    with st.spinner("Running agents..."):
        pipeline = OwnershipPipeline()
        output = pipeline.run(company_name.strip())

    st.subheader("Final ownership classification")
    st.metric("Ownership type", output.final_decision.ownership_type)
    st.metric("Confidence", f"{output.final_decision.confidence:.2f}")

    st.markdown("### Why this decision?")
    for reason in output.final_decision.rationale:
        st.write(f"- {reason}")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("### Agent 1: Web research output")
        st.write("**Signals**")
        st.json(output.web_research.probable_owner_signals)
        st.write("**Top findings**")
        st.json(output.web_research.findings[:8])

    with c2:
        st.markdown("### Agent 2: Companies House output")
        st.write(
            {
                "matched_company_name": output.companies_house.matched_company_name,
                "company_number": output.companies_house.company_number,
                "company_url": output.companies_house.company_url,
            }
        )
        st.write("**PSC snippets**")
        st.json(output.companies_house.psc_snippets[:8])
        st.write("**Filing snippets**")
        st.json(output.companies_house.filing_snippets[:8])

    with c3:
        st.markdown("### Agent 3: Ownership decision evidence")
        st.json([e.model_dump() for e in output.final_decision.evidence[:20]])

    with st.expander("Raw JSON output"):
        st.code(json.dumps(output.model_dump(), indent=2), language="json")
