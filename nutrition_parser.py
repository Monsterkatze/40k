from __future__ import annotations

import re
from dataclasses import dataclass


TARGET_FIELDS: tuple[str, ...] = (
    "kJ",
    "kcal",
    "fat_g",
    "satfat_g",
    "carbs_g",
    "sugar_g",
    "protein_g",
    "salt_g",
    "fiber_g",
)

MACRO_FIELDS: frozenset[str] = frozenset(
    {
        "fat_g",
        "satfat_g",
        "carbs_g",
        "sugar_g",
        "protein_g",
        "salt_g",
        "fiber_g",
    }
)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "kJ": (
        "energie",
        "brennwert",
        "energy",
        "kj",
    ),
    "kcal": (
        "kcal",
        "kalorien",
        "calories",
        "cal",
    ),
    "fat_g": (
        "fett",
        "fat",
    ),
    "satfat_g": (
        "davon gesaettigte fettsaeuren",
        "gesaettigte fettsaeuren",
        "gesaettigte",
        "saturated fat",
        "saturates",
    ),
    "carbs_g": (
        "kohlenhydrate",
        "kohlenhydrat",
        "carbohydrates",
        "carbs",
    ),
    "sugar_g": (
        "davon zucker",
        "zucker",
        "sugars",
        "sugar",
    ),
    "protein_g": (
        "eiweiss",
        "eiweisz",
        "protein",
        "proteine",
    ),
    "salt_g": (
        "salz",
        "salt",
    ),
    "fiber_g": (
        "ballaststoffe",
        "ballaststoff",
        "fiber",
        "fibre",
    ),
}

_VALUE_PATTERN = r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kj|kcal|mg|g)?"


@dataclass(frozen=True)
class NutritionParseResult:
    fields: dict[str, float | None]
    warnings: tuple[str, ...]
    parse_basis: str


def empty_fields() -> dict[str, float | None]:
    return {field_name: None for field_name in TARGET_FIELDS}


def parse_nutrition_fields(normalized_text: str, category: str) -> NutritionParseResult:
    parse_text, parse_basis = _select_parse_text(normalized_text, category)
    values = empty_fields()
    unreadable_candidates: list[str] = []

    for field_name in TARGET_FIELDS:
        aliases = FIELD_ALIASES[field_name]
        parsed = _extract_with_aliases(parse_text, field_name, aliases)
        if parsed is not None:
            values[field_name] = parsed
        elif _alias_present(parse_text, aliases):
            unreadable_candidates.append(field_name)

    if values["kJ"] is None:
        values["kJ"] = _extract_energy_unit_fallback(parse_text, "kj")
    if values["kcal"] is None:
        values["kcal"] = _extract_energy_unit_fallback(parse_text, "kcal")

    warnings = [
        f"unreadable_field:{field_name}"
        for field_name in unreadable_candidates
        if values[field_name] is None
    ]

    return NutritionParseResult(fields=values, warnings=tuple(warnings), parse_basis=parse_basis)


def _select_parse_text(normalized_text: str, category: str) -> tuple[str, str]:
    text = normalized_text.strip()
    if category != "MIXED":
        return text, "full_text"

    marker_match = re.search(r"\b(?:naehrwerte|nahrwerte|nutrition(?:al)?(?: values?)?)\s*:", text)
    if marker_match:
        return text[marker_match.start() :], "mixed_from_marker"

    first_signal_index = _first_nutrition_signal_index(text)
    if first_signal_index is not None:
        return text[first_signal_index:], "mixed_from_first_signal"

    return text, "mixed_full_fallback"


def _first_nutrition_signal_index(text: str) -> int | None:
    trigger_terms = (
        "energie",
        "brennwert",
        "kcal",
        "kj",
        "fett",
        "kohlenhydrat",
        "zucker",
        "protein",
        "eiweiss",
        "salz",
        "ballaststoff",
    )

    found_indices = [
        match.start()
        for term in trigger_terms
        for match in re.finditer(rf"\b{re.escape(term)}\w*\b", text)
    ]
    if not found_indices:
        return None
    return min(found_indices)


def _extract_with_aliases(parse_text: str, field_name: str, aliases: tuple[str, ...]) -> float | None:
    for alias in aliases:
        alias_pattern = re.sub(r"\s+", r"\\s+", re.escape(alias))
        pattern = re.compile(
            rf"\b{alias_pattern}\b\D{{0,40}}{_VALUE_PATTERN}",
            re.IGNORECASE,
        )

        for match in pattern.finditer(parse_text):
            converted = _convert_value(
                field_name=field_name,
                value_text=match.group("value"),
                unit_text=match.group("unit"),
            )
            if converted is not None:
                return converted

    return None


def _extract_energy_unit_fallback(parse_text: str, unit: str) -> float | None:
    unit_pattern = re.compile(rf"\b(?P<value>\d+(?:\.\d+)?)\s*{unit}\b", re.IGNORECASE)
    match = unit_pattern.search(parse_text)
    if not match:
        return None
    return float(match.group("value"))


def _convert_value(field_name: str, value_text: str, unit_text: str | None) -> float | None:
    value = float(value_text)
    unit = (unit_text or "").lower()

    if field_name == "kJ":
        if unit in ("", "kj"):
            return value
        return None

    if field_name == "kcal":
        if unit in ("", "kcal"):
            return value
        return None

    if field_name in MACRO_FIELDS:
        if unit == "mg":
            return round(value / 1000.0, 6)
        if unit in ("", "g"):
            return value
        return None

    return None


def _alias_present(parse_text: str, aliases: tuple[str, ...]) -> bool:
    for alias in aliases:
        alias_pattern = re.sub(r"\s+", r"\\s+", re.escape(alias))
        if re.search(rf"\b{alias_pattern}\b", parse_text, re.IGNORECASE):
            return True
    return False
