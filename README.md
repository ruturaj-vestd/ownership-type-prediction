# Ownership Type Prediction App

This app keeps your original 3-agent architecture and runs them sequentially:

1. **Web Evidence Agent** (OpenAI Responses API + `web_search`) with deterministic website probing.
2. **Companies House Agent** (CH API + filing/PDF extraction + PSC fact extraction).
3. **Ownership Determination Agent** (OpenAI classifier using CH evidence as primary source).

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

The UI supports two modes:
- **Single company** input
- **Excel upload** (`.xlsx`) with exactly these 8 columns (same order):
  1. Company Name
  2. Job Title
  3. No. of Employees
  4. Employees Based
  5. BU Size
  6. Domain Name
  7. Legal Entity
  8. Ownership Type

For Excel mode, the app processes rows one-by-one and fills:
- Domain Name
- Legal Entity
- Ownership Type
- Extra reasoning column: **Ownership Reasoning (Structured)**

## Run CLI

```bash
python run_pipeline.py "First Light Fusion"
```
