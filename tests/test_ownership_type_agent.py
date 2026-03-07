from app.agents.ownership_type_agent import extract_ch_primary_signals


def test_extract_ch_primary_signals_empty():
    result = extract_ch_primary_signals({})
    assert result["companies"] == []
    assert "ch_evidence_pack_missing_companies" in result["global_flags"]


def test_extract_ch_primary_signals_has_company():
    pack = {
        "companies": [
            {
                "company_number": "12345678",
                "profile": {"company_name": "Acme Ltd", "company_status": "active"},
                "pscs": {"total_results": 1, "items": [{"name": "Acme Holdings Ltd"}]},
                "psc_statements": {"total_results": 0, "items": []},
                "officers": {"total_results": 1, "items": [{"name": "Jane Doe"}]},
                "filings": {"total_count": 1, "items": [{"type": "cs01"}]},
                "downloaded_pdfs": [],
            }
        ]
    }
    result = extract_ch_primary_signals(pack)
    assert len(result["companies"]) == 1
    assert result["global_flags"] == []
