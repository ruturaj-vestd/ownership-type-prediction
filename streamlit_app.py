from __future__ import annotations

import json
from io import BytesIO

import pandas as pd
import streamlit as st

from app.pipeline import OwnershipPipeline
from app.utils.batch_processing import (
    EXPECTED_EXCEL_COLUMNS,
    REASONING_COLUMN,
    validate_excel_columns,
    validate_required_row_fields,
)

st.set_page_config(page_title="Ownership Type App", layout="wide")
st.title("Ownership Type Determination App")
st.caption("Staged architecture: domain resolution -> legal entity resolution -> evidence extraction -> deterministic classification")

with st.expander("Required environment variables"):
    st.code("export OPENAI_API_KEY='...'; export CH_API_KEY='...'", language="bash")

mode = st.radio("Choose input mode", ["Single company", "Excel upload"], horizontal=True)

if mode == "Single company":
    company_name = st.text_input("Enter company name", placeholder="e.g. First Light Fusion")

    if st.button("Run full pipeline", type="primary") and company_name.strip():
        with st.spinner("Running web agent, CH agent, and deterministic ownership classifier..."):
            output = OwnershipPipeline().run(company_name.strip())

        st.subheader("Final result")
        st.metric("Ownership type", output.ownership_output.ownership_type)
        st.metric("Confidence", f"{output.ownership_output.confidence:.2f}")
        st.metric("Needs review", str(output.ownership_output.needs_review))
        if output.ownership_output.review_reason:
            st.warning(output.ownership_output.review_reason)
        st.write(output.ownership_output.reasoning_summary)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### Agent 1: Web Evidence")
            st.json(output.web_agent_output.model_dump())
        with c2:
            st.markdown("### Agent 2: Companies House")
            st.json(output.ch_agent_output.model_dump())
        with c3:
            st.markdown("### Final structured decision")
            st.json(output.ownership_output.model_dump())

else:
    st.markdown("### Upload Excel (.xlsx)")
    st.caption("File must contain exactly these 8 columns in this order.")
    st.code(", ".join(EXPECTED_EXCEL_COLUMNS))
    uploaded = st.file_uploader("Upload sheet", type=["xlsx"])

    if uploaded is not None:
        try:
            df = pd.read_excel(uploaded)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not read Excel file: {exc}")
            st.stop()

        cols = [str(c) for c in df.columns.tolist()]
        col_validation = validate_excel_columns(cols)
        if not col_validation.ok:
            st.error(col_validation.summary)
            st.code(
                "Expected columns (exact order):\n"
                + " | ".join(EXPECTED_EXCEL_COLUMNS)
                + "\n\nFound columns:\n"
                + " | ".join(cols)
            )
            st.markdown("### Column issues found")
            for d in col_validation.details:
                st.write(f"- {d}")
            st.stop()

        row_validation = validate_required_row_fields(df)
        if not row_validation.ok:
            st.error(row_validation.summary)
            st.markdown("### Row-level issues found")
            for d in row_validation.details[:200]:
                st.write(f"- {d}")
            if len(row_validation.details) > 200:
                st.warning(f"...and {len(row_validation.details) - 200} more row errors.")
            st.stop()

        if st.button("Run row-by-row enrichment", type="primary"):
            pipeline = OwnershipPipeline()
            working_df = df.copy()
            working_df[REASONING_COLUMN] = ""
            progress = st.progress(0)
            total = len(working_df)

            for i, idx in enumerate(working_df.index, start=1):
                company_name = str(working_df.at[idx, "Company Name"] or "").strip()

                try:
                    output = pipeline.run(company_name)
                    working_df.at[idx, "Domain Name"] = output.ownership_output.official_domain
                    working_df.at[idx, "Legal Entity"] = output.ownership_output.legal_entity_name
                    working_df.at[idx, "Ownership Type"] = output.ownership_output.ownership_type
                    working_df.at[idx, "company_number"] = output.ownership_output.company_number
                    working_df.at[idx, "confidence"] = output.ownership_output.confidence
                    working_df.at[idx, "needs_review"] = output.ownership_output.needs_review
                    working_df.at[idx, "review_reason"] = output.ownership_output.review_reason
                    working_df.at[idx, "reasoning_summary"] = output.ownership_output.reasoning_summary
                    working_df.at[idx, REASONING_COLUMN] = json.dumps(
                        {
                            "company_name": output.ownership_output.company_name,
                            "official_domain": output.ownership_output.official_domain,
                            "legal_entity_name": output.ownership_output.legal_entity_name,
                            "company_number": output.ownership_output.company_number,
                            "ownership_type": output.ownership_output.ownership_type,
                            "confidence": output.ownership_output.confidence,
                            "needs_review": output.ownership_output.needs_review,
                            "review_reason": output.ownership_output.review_reason,
                            "reasoning_summary": output.ownership_output.reasoning_summary,
                            "ownership_facts": output.ownership_output.ownership_facts,
                            "citations": output.ownership_output.citations,
                            "flags": output.ownership_output.flags,
                        },
                        ensure_ascii=False,
                    )
                except Exception as exc:  # noqa: BLE001
                    working_df.at[idx, REASONING_COLUMN] = json.dumps({"status": "error", "reason": str(exc)})

                progress.progress(i / max(total, 1))

            st.success("Completed row-by-row enrichment.")
            st.dataframe(working_df, use_container_width=True)

            out_buffer = BytesIO()
            working_df.to_excel(out_buffer, index=False)
            out_buffer.seek(0)
            st.download_button(
                label="Download enriched Excel",
                data=out_buffer,
                file_name="ownership_enriched.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
