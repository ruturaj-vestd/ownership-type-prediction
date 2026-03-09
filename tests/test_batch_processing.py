from app.utils.batch_processing import EXPECTED_EXCEL_COLUMNS, validate_excel_columns


def test_validate_excel_columns_passes_for_exact_match():
    ok, msg = validate_excel_columns(EXPECTED_EXCEL_COLUMNS)
    assert ok is True
    assert msg == "ok"


def test_validate_excel_columns_fails_for_wrong_columns():
    ok, msg = validate_excel_columns(EXPECTED_EXCEL_COLUMNS[:-1])
    assert ok is False
    assert "exactly these 8 columns" in msg
