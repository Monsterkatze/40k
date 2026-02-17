from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from csv_ingestion import NormalizedRecord


MISSING = "MISSING"
INGREDIENTS = "INGREDIENTS"
NUTRITION = "NUTRITION"
MIXED = "MIXED"
UNKNOWN = "UNKNOWN"

CATEGORY_ORDER = (MISSING, INGREDIENTS, NUTRITION, MIXED, UNKNOWN)


INGREDIENT_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("zutaten", re.compile(r"\bzutaten\b", re.IGNORECASE)),
    ("inhaltsstoffe", re.compile(r"\binhalts?stoffe\b", re.IGNORECASE)),
    ("zusammensetzung", re.compile(r"\bzusammensetzung\b", re.IGNORECASE)),
    ("allergene", re.compile(r"\ballergene?\b", re.IGNORECASE)),
    ("spuren", re.compile(r"\bspuren\b", re.IGNORECASE)),
    ("enthaelt", re.compile(r"\benthaelt\b", re.IGNORECASE)),
    ("ingredients", re.compile(r"\bingredients?\b", re.IGNORECASE)),
    ("contains", re.compile(r"\bcontains\b", re.IGNORECASE)),
)

NUTRITION_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("energie", re.compile(r"\benergie\b", re.IGNORECASE)),
    ("brennwert", re.compile(r"\bbrennwert\b", re.IGNORECASE)),
    ("kcal", re.compile(r"\bkcal\b", re.IGNORECASE)),
    ("kj", re.compile(r"\bkj\b", re.IGNORECASE)),
    ("fett", re.compile(r"\bfett\b", re.IGNORECASE)),
    ("kohlenhydrate", re.compile(r"\bkohlenhydrat(?:e|en)?\b", re.IGNORECASE)),
    ("zucker", re.compile(r"\bzucker\b", re.IGNORECASE)),
    ("protein", re.compile(r"\b(?:eiweiss|protein)\b", re.IGNORECASE)),
    ("salz", re.compile(r"\bsalz\b", re.IGNORECASE)),
    ("gesaettigte_fettsaeuren", re.compile(r"\bgesaettigte(?:n)?\b", re.IGNORECASE)),
    ("ballaststoffe", re.compile(r"\bballaststoffe\b", re.IGNORECASE)),
    ("per_100", re.compile(r"\b(?:pro|per)\s*100\s*(?:g|ml)\b", re.IGNORECASE)),
    ("unit_amount", re.compile(r"\b\d+(?:[\.,]\d+)?\s*(?:g|mg|kj|kcal|ml)\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class ClassificationDiagnostics:
    ingredient_signals: tuple[str, ...]
    nutrition_signals: tuple[str, ...]
    ingredient_signal_count: int
    nutrition_signal_count: int
    rule_applied: str


@dataclass(frozen=True)
class ClassifiedRecord:
    product_id: str
    product_name: str
    nutrition_raw_text: str
    ingredients_text: str | None
    nutrition_normalized_text: str
    nutrition_search_text: str
    row_number: int
    category: str
    normalization_warnings: tuple[str, ...]
    diagnostics: ClassificationDiagnostics
    extracted_nutrition: dict[str, float | None] = field(default_factory=dict)
    parser_warnings: tuple[str, ...] = ()
    parser_basis: str = "full_text"
    parsed_fields_count: int = 0
    validation_warnings: tuple[str, ...] = ()
    status: str = "NEEDS_REVIEW"
    status_reasons: tuple[str, ...] = ()
    hard_failure_reasons: tuple[str, ...] = ()

    def to_json_line(self) -> str:
        return json.dumps(
            {
                "product_id": self.product_id,
                "product_name": self.product_name,
                "nutrition_raw_text": self.nutrition_raw_text,
                "ingredients_text": self.ingredients_text,
                "nutrition_normalized_text": self.nutrition_normalized_text,
                "nutrition_search_text": self.nutrition_search_text,
                "row_number": self.row_number,
                "category": self.category,
                "normalization_warnings": list(self.normalization_warnings),
                "extracted_nutrition": self.extracted_nutrition,
                "parser_warnings": list(self.parser_warnings),
                "parser_basis": self.parser_basis,
                "parsed_fields_count": self.parsed_fields_count,
                "validation_warnings": list(self.validation_warnings),
                "status": self.status,
                "status_reasons": list(self.status_reasons),
                "hard_failure_reasons": list(self.hard_failure_reasons),
                "diagnostics": {
                    "ingredient_signals": list(self.diagnostics.ingredient_signals),
                    "nutrition_signals": list(self.diagnostics.nutrition_signals),
                    "ingredient_signal_count": self.diagnostics.ingredient_signal_count,
                    "nutrition_signal_count": self.diagnostics.nutrition_signal_count,
                    "rule_applied": self.diagnostics.rule_applied,
                },
            },
            ensure_ascii=False,
        )


def classify_record(
    record: NormalizedRecord,
    nutrition_normalized_text: str | None = None,
    nutrition_search_text: str | None = None,
    normalization_warnings: tuple[str, ...] = (),
    extracted_nutrition: dict[str, float | None] | None = None,
    parser_warnings: tuple[str, ...] = (),
    parser_basis: str = "full_text",
    parsed_fields_count: int = 0,
    validation_warnings: tuple[str, ...] = (),
    status: str = "NEEDS_REVIEW",
    status_reasons: tuple[str, ...] = (),
    hard_failure_reasons: tuple[str, ...] = (),
) -> ClassifiedRecord:
    normalized_source = nutrition_normalized_text or record.nutrition_raw_text
    normalized_text = _normalize_text(normalized_source)
    search_text = nutrition_search_text or normalized_text

    ingredient_signals = _extract_signals(normalized_text, INGREDIENT_SIGNAL_PATTERNS)
    nutrition_signals = _extract_signals(normalized_text, NUTRITION_SIGNAL_PATTERNS)

    has_ingredient_signal = len(ingredient_signals) > 0
    has_nutrition_signal_minimum = len(nutrition_signals) >= 2

    if not normalized_text:
        category = MISSING
        rule_applied = "missing_text"
    elif has_ingredient_signal and has_nutrition_signal_minimum:
        category = MIXED
        rule_applied = "mixed_ingredient_plus_nutrition_min2"
    elif has_nutrition_signal_minimum:
        category = NUTRITION
        rule_applied = "nutrition_min2"
    elif has_ingredient_signal:
        category = INGREDIENTS
        rule_applied = "ingredient_only_or_weak_nutrition"
    else:
        category = UNKNOWN
        rule_applied = "no_reliable_signals"

    diagnostics = ClassificationDiagnostics(
        ingredient_signals=ingredient_signals,
        nutrition_signals=nutrition_signals,
        ingredient_signal_count=len(ingredient_signals),
        nutrition_signal_count=len(nutrition_signals),
        rule_applied=rule_applied,
    )

    return ClassifiedRecord(
        product_id=record.product_id,
        product_name=record.product_name,
        nutrition_raw_text=record.nutrition_raw_text,
        ingredients_text=record.ingredients_text,
        nutrition_normalized_text=normalized_text,
        nutrition_search_text=search_text,
        row_number=record.row_number,
        category=category,
        normalization_warnings=normalization_warnings,
        extracted_nutrition=extracted_nutrition or {},
        parser_warnings=parser_warnings,
        parser_basis=parser_basis,
        parsed_fields_count=parsed_fields_count,
        validation_warnings=validation_warnings,
        status=status,
        status_reasons=status_reasons,
        hard_failure_reasons=hard_failure_reasons,
        diagnostics=diagnostics,
    )


def write_classified_records(output_path: Path, records: list[ClassifiedRecord]) -> None:
    with output_path.open("w", encoding="utf-8") as file_handle:
        for record in records:
            file_handle.write(record.to_json_line())
            file_handle.write("\n")


def _extract_signals(
    normalized_text: str,
    signal_patterns: tuple[tuple[str, re.Pattern[str]], ...],
) -> tuple[str, ...]:
    found: list[str] = []
    for marker, pattern in signal_patterns:
        if pattern.search(normalized_text):
            found.append(marker)
    return tuple(sorted(found))


def _normalize_text(value: str) -> str:
    lowered = value.strip().lower()
    if not lowered:
        return ""

    lowered = (
        lowered.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("Ã¤", "ae")
        .replace("Ã¶", "oe")
        .replace("Ã¼", "ue")
    )
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_diacritics = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    collapsed = re.sub(r"\s+", " ", without_diacritics)
    return collapsed