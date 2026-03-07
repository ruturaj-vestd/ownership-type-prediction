# Ownership Type Prediction App

This repository now includes a runnable 3-agent pipeline in Python:

1. **WebResearchAgent**: fetches ownership signals from web snippets.
2. **CompaniesHouseAgent**: resolves the company and pulls ownership-relevant snippets from Companies House pages.
3. **OwnershipTypeAgent**: applies transparent, auditable rules to classify ownership type.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Then enter a company name in the UI.

## CLI mode

```bash
python run_pipeline.py "Company Name"
```

This prints full JSON including each agent's output and rationale for the final ownership decision.
