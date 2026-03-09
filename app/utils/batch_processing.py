from __future__ import annotations

EXPECTED_EXCEL_COLUMNS = [
    "Company Name",
    "Job Title",
    "No. of Employees",
    "Employees Based",
    "BU Size",
    "Domain Name",
    "Legal Entity",
    "Ownership Type",
]

REASONING_COLUMN = "Ownership Reasoning (Structured)"


def validate_excel_columns(columns: list[str]) -> tuple[bool, str]:
    if columns != EXPECTED_EXCEL_COLUMNS:
        return (
            False,
            "Excel must contain exactly these 8 columns in order: " + ", ".join(EXPECTED_EXCEL_COLUMNS),
        )
    return True, "ok"
