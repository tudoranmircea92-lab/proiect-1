from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    errors: list[str]


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if text == "" or text.lower() in {"null", "nan", "none", "off", "purge"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def validate_process_rows(rows: list[dict], required_columns: list[str]) -> ValidationResult:
    errors: list[str] = []
    if not rows:
        return ValidationResult(False, ["process file has no rows"])
    for col in required_columns:
        if col not in rows[0]:
            errors.append(f"missing required column: {col}")
    for idx, row in enumerate(rows):
        for k, v in row.items():
            if "Gas" in k and "Type" not in k and "nom" in k:
                num = parse_float(v)
                if num is not None and num < 0:
                    errors.append(f"row {idx} has negative gas in {k}")
    return ValidationResult(len(errors) == 0, errors)


def validate_optoplex_rows(rows: list[dict]) -> ValidationResult:
    errors: list[str] = []
    if not rows:
        return ValidationResult(False, ["optoplex file has no usable measurements"])
    devices = {r["device_norm"] for r in rows}
    if "T" not in devices:
        errors.append("missing Transmission(T) measurements")
    positions = {r["position"] for r in rows if r.get("position") is not None}
    if not positions:
        errors.append("missing positions")
    return ValidationResult(len(errors) == 0, errors)
