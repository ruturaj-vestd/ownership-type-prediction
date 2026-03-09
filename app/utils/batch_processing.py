from __future__ import annotations

from dataclasses import dataclass

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
REQUIRED_FILLED_COLUMNS = [
    "Company Name",
    "Job Title",
    "No. of Employees",
    "Employees Based",
    "BU Size",
]


@dataclass
class UploadValidationResult:
    ok: bool
    summary: str
    details: list[str]


def normalize_column_name(name: str) -> str:
    return str(name).replace("\u00A0", " ").strip()


def validate_excel_columns(columns: list[str]) -> UploadValidationResult:
    actual = [normalize_column_name(c) for c in columns]
    expected = EXPECTED_EXCEL_COLUMNS

    details: list[str] = []
    max_len = max(len(actual), len(expected))
    for i in range(max_len):
        exp = expected[i] if i < len(expected) else "[none]"
        act = actual[i] if i < len(actual) else "[missing]"
        if exp != act:
            details.append(f"Column {i+1}: expected '{exp}' but found '{act}'")

    missing = [c for c in expected if c not in actual]
    extra = [c for c in actual if c not in expected]
    if missing:
        details.append("Missing columns: " + ", ".join(missing))
    if extra:
        details.append("Unexpected columns: " + ", ".join(extra))

    if details:
        return UploadValidationResult(False, "Excel column format is invalid.", details)

    return UploadValidationResult(True, "ok", [])


def _is_blank(v: object) -> bool:
    if v is None:
        return True
    s = str(v).strip()
    return s == "" or s.lower() == "nan"


def validate_required_row_fields(df) -> UploadValidationResult:
    errors: list[str] = []
    for idx in df.index:
        excel_row = int(idx) + 2
        for col in REQUIRED_FILLED_COLUMNS:
            if _is_blank(df.at[idx, col]):
                errors.append(f"Row {excel_row}: '{col}' is empty")

    if errors:
        return UploadValidationResult(False, "Some required row values are missing.", errors)
    return UploadValidationResult(True, "ok", [])
