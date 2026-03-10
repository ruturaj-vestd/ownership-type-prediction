# Ownership Type Prediction App

This app runs a staged 3-agent ownership enrichment flow:

1. **Web Evidence Agent** (OpenAI Responses API + `web_search`) for factual domain/entity hints.
2. **Companies House Agent** (CH API + filings + PDF parsing + PSC extraction).
3. **Deterministic Decision Flow** (domain resolution -> legal-entity resolution -> ownership evidence extraction -> rule-based ownership classification -> validation).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set API keys:

```bash
export OPENAI_API_KEY="your-openai-key"
export CH_API_KEY="your-companies-house-api-key"
```

## Run UI

```bash
streamlit run streamlit_app.py
```

The UI supports:
- **Single company** mode
- **Excel upload** mode (`.xlsx`) with exactly these 8 columns in order:
  1. Company Name
  2. Job Title
  3. No. of Employees
  4. Employees Based
  5. BU Size
  6. Domain Name
  7. Legal Entity
  8. Ownership Type

Excel processing is row-by-row. Output fills and adds:
- Domain Name
- Legal Entity
- Ownership Type
- company_number
- confidence
- needs_review
- review_reason
- reasoning_summary
- Ownership Reasoning (Structured)

## Decision flow (auditable)

The final ownership label is NOT chosen from freeform model text.

Stages:
1. `resolve_official_domain(company_input)`
2. `resolve_legal_entity(company_input, official_domain)`
3. `extract_ownership_evidence(legal_entity, company_number, official_domain)`
4. `classify_ownership_type(extracted_evidence)` (deterministic rules)
5. `validate_row(enrichment_result)` (contradiction checks -> flags)

Source ranking priority:
1. Companies House PSC / filings
2. Official company website
3. Parent company official website
4. High-quality corporate sources
5. Search snippets

## Ownership labels

Deterministic labels used:
- Individual(s)
- Family
- Private Equity
- Listed Parent
- Diverse
- Other / Special Structures

When evidence conflicts or resolution is weak, the pipeline deterministically falls back to **Other / Special Structures** while surfacing flags.

## Assumptions

- Companies House evidence is treated as highest authority.
- If domain/entity alignment is weak or company number is missing, the row is flagged and downgraded.
- Reliability is prioritized over coverage.

## Run CLI

```bash
python run_pipeline.py "First Light Fusion"
```
