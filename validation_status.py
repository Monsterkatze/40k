from __future__ import annotations

import math
from dataclasses import dataclass

from cell_classification import ClassifiedRecord, MISSING, UNKNOWN
from nutrition_parser import TARGET_FIELDS


STATUS_OK = "OK"
STATUS_OK_WITH_WARNINGS = "OK_WITH_WARNINGS"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_FAILED = "FAILED"

MIN_REVIEW_FIELD_THRESHOLD = 3

PLAUSIBILITY_RANGES: dict[str, tuple[float, float]] = {
    "kcal": (0.0, 900.0),
    "kJ": (0.0, 3800.0),
    "fat_g": (0.0, 100.0),
    "sugar_g": (0.0, 100.0),
    "salt_g": (0.0, 15.0),
}


@dataclass(frozen=True)
class ValidationStatusResult:
    parsed_fields_count: int
    validation_warnings: tuple[str, ...]
    status: str
    status_reasons: tuple[str, ...]
    hard_failure_reasons: tuple[str, ...]


def assign_validation_status(record: ClassifiedRecord) -> ValidationStatusResult:
    extracted = record.extracted_nutrition if isinstance(record.extracted_nutrition, dict) else {}

    hard_failure_reasons = _collect_hard_failure_reasons(record)
    parsed_fields_count = _count_valid_parsed_fields(extracted)
    validation_warnings = _collect_validation_warnings(record, extracted)

    status_reasons: list[str] = []
    if hard_failure_reasons:
        status = STATUS_FAILED
        status_reasons.extend(hard_failure_reasons)
    elif parsed_fields_count < MIN_REVIEW_FIELD_THRESHOLD:
        if _is_acceptably_minimal_profile(parsed_fields_count, extracted):
            status = STATUS_OK_WITH_WARNINGS
            status_reasons.append("minimal_profile_ok")
        elif _is_single_energy_only_profile(parsed_fields_count, extracted):
            status = STATUS_NEEDS_REVIEW
            status_reasons.append("minimal_profile_energy_only")
        else:
            status = STATUS_NEEDS_REVIEW
            status_reasons.append(
                f"insufficient_parsed_fields:{parsed_fields_count}<{MIN_REVIEW_FIELD_THRESHOLD}"
            )
    elif validation_warnings or record.parser_warnings:
        status = STATUS_OK_WITH_WARNINGS
        status_reasons.append("warnings_present")
    else:
        status = STATUS_OK
        status_reasons.append("all_checks_passed")

    return ValidationStatusResult(
        parsed_fields_count=parsed_fields_count,
        validation_warnings=validation_warnings,
        status=status,
        status_reasons=tuple(status_reasons),
        hard_failure_reasons=hard_failure_reasons,
    )


def _count_valid_parsed_fields(extracted: dict[str, float | None]) -> int:
    valid_count = 0
    for field_name in TARGET_FIELDS:
        value = extracted.get(field_name)
        if _is_valid_non_negative_number(value):
            valid_count += 1
    return valid_count


def _collect_validation_warnings(
    record: ClassifiedRecord,
    extracted: dict[str, float | None],
) -> tuple[str, ...]:
    warnings: list[str] = []

    for field_name, (minimum, maximum) in PLAUSIBILITY_RANGES.items():
        value = extracted.get(field_name)
        if value is None:
            continue
        if not _is_valid_non_negative_number(value):
            continue
        if not (minimum <= value <= maximum):
            warnings.append(
                f"plausibility_out_of_range:{field_name}:{value} not in [{minimum}, {maximum}]"
            )

    kcal = extracted.get("kcal")
    kj = extracted.get("kJ")
    if _is_valid_non_negative_number(kcal) and _is_valid_non_negative_number(kj):
        expected_kj = float(kcal) * 4.184
        if abs(float(kj) - expected_kj) > 120.0:
            warnings.append(
                f"energy_mismatch:kJ={kj} inconsistent_with_kcal={kcal}"
            )

    if record.category in (MISSING, UNKNOWN):
        warnings.append(f"low_confidence_category:{record.category}")

    return tuple(warnings)


def _collect_hard_failure_reasons(record: ClassifiedRecord) -> tuple[str, ...]:
    reasons: list[str] = []

    if not record.product_id.strip():
        reasons.append("missing_product_id")
    if not record.product_name.strip():
        reasons.append("missing_product_name")
    if not record.nutrition_raw_text.strip():
        reasons.append("missing_nutrition_raw_text")

    extracted = record.extracted_nutrition
    if not isinstance(extracted, dict):
        reasons.append("invalid_extracted_nutrition_payload")
    else:
        for field_name in TARGET_FIELDS:
            value = extracted.get(field_name)
            if value is None:
                continue
            if not isinstance(value, (int, float)):
                reasons.append(f"invalid_numeric_type:{field_name}")
                continue
            float_value = float(value)
            if not math.isfinite(float_value):
                reasons.append(f"non_finite_value:{field_name}")
            elif float_value < 0:
                reasons.append(f"negative_value:{field_name}")

    return tuple(sorted(set(reasons)))


def _is_valid_non_negative_number(value: float | int | None) -> bool:
    if value is None or not isinstance(value, (int, float)):
        return False
    float_value = float(value)
    if not math.isfinite(float_value):
        return False
    return float_value >= 0


def _is_acceptably_minimal_profile(
    parsed_fields_count: int,
    extracted: dict[str, float | None],
) -> bool:
    if parsed_fields_count != 2:
        return False

    has_energy = _is_valid_non_negative_number(extracted.get("kJ")) or _is_valid_non_negative_number(
        extracted.get("kcal")
    )
    has_macro = any(
        _is_valid_non_negative_number(extracted.get(field_name))
        for field_name in (
            "fat_g",
            "satfat_g",
            "carbs_g",
            "sugar_g",
            "protein_g",
            "salt_g",
            "fiber_g",
        )
    )
    return has_energy and has_macro


def _is_single_energy_only_profile(
    parsed_fields_count: int,
    extracted: dict[str, float | None],
) -> bool:
    if parsed_fields_count != 1:
        return False

    has_kj = _is_valid_non_negative_number(extracted.get("kJ"))
    has_kcal = _is_valid_non_negative_number(extracted.get("kcal"))
    return has_kj ^ has_kcal
