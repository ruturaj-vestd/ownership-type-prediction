from __future__ import annotations

import json

import streamlit as st

from app.pipeline import OwnershipPipeline

st.set_page_config(page_title="Ownership Type App", layout="wide")
st.title("Ownership Type Determination App")
st.caption("Original architecture: Web agent (OpenAI web_search) → CH agent → Ownership classifier")

company_name = st.text_input("Enter company name", placeholder="e.g. First Light Fusion")

with st.expander("Required environment variables"):
    st.code("export OPENAI_API_KEY='...'; export CH_API_KEY='...'", language="bash")

if st.button("Run full pipeline", type="primary") and company_name.strip():
    with st.spinner("Running web agent, CH agent, and ownership classifier..."):
        output = OwnershipPipeline().run(company_name.strip())

    st.subheader("Final result")
    st.metric("Ownership type", output.ownership_output.ownership_type)
    st.metric("Confidence", f"{output.ownership_output.confidence:.2f}")
    st.write(output.ownership_output.rationale)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Agent 1: Web Evidence")
        st.json(output.web_agent_output.model_dump())
    with c2:
        st.markdown("### Agent 2: Companies House")
        st.json(output.ch_agent_output.model_dump())
    with c3:
        st.markdown("### Agent 3: Ownership")
        st.json(output.ownership_output.model_dump())

    with st.expander("Combined JSON"):
        st.code(json.dumps(output.model_dump(), indent=2), language="json")
