from app.utils.batch_processing import EXPECTED_EXCEL_COLUMNS, validate_excel_columns


def test_validate_excel_columns_passes_for_exact_match():
    result = validate_excel_columns(EXPECTED_EXCEL_COLUMNS)
    assert result.ok is True
    assert result.summary == "ok"


def test_validate_excel_columns_fails_for_wrong_columns():
    result = validate_excel_columns(EXPECTED_EXCEL_COLUMNS[:-1])
    assert result.ok is False
    assert "invalid" in result.summary.lower()
    assert result.details
