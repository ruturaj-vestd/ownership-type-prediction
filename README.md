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

## Run CLI

```bash
python run_pipeline.py "First Light Fusion"
```
