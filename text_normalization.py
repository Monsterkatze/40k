from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


_NBSP_RE = re.compile(r"\u00a0")
_WHITESPACE_RE = re.compile(r"\s+")
_QUOTE_RE = re.compile(r"[\"'“”„‟’‘‚‛`´]")
_GERMAN_THOUSANDS_RE = re.compile(r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b")
_GERMAN_DECIMAL_RE = re.compile(r"\b\d+,\d+\b")
_NUMERIC_FRAGMENT_RE = re.compile(r"\b\d[\d\.,]*\b")
_TOKEN_RE = re.compile(r"[a-z]+|\d+(?:\.\d+)?")


@dataclass(frozen=True)
class NutritionNormalizationResult:
    normalized_text: str
    search_text: str
    tokens: tuple[str, ...]
    warnings: tuple[str, ...]


def normalize_nutrition_text(value: str) -> NutritionNormalizationResult:
    warnings: list[str] = []

    cleaned_text = _basic_cleanup(value)
    number_normalized_text = _normalize_german_numbers(cleaned_text, warnings)

    lowered = number_normalized_text.lower()
    lowered = _apply_umlaut_fallbacks(lowered)
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_diacritics = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    canonical = _WHITESPACE_RE.sub(" ", without_diacritics).strip()

    tokens = tuple(_TOKEN_RE.findall(canonical))
    search_text = " ".join(tokens)

    return NutritionNormalizationResult(
        normalized_text=canonical,
        search_text=search_text,
        tokens=tokens,
        warnings=tuple(warnings),
    )


def _basic_cleanup(value: str) -> str:
    text = _NBSP_RE.sub(" ", value)
    text = text.replace("\t", " ")
    text = _QUOTE_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _normalize_german_numbers(value: str, warnings: list[str]) -> str:
    converted_spans: list[tuple[int, int]] = []

    def convert_thousands(match: re.Match[str]) -> str:
        fragment = match.group(0)
        converted_spans.append(match.span())
        if "," in fragment:
            integer_part, decimal_part = fragment.split(",", 1)
            integer_part = integer_part.replace(".", "")
            return f"{integer_part}.{decimal_part}"
        return fragment.replace(".", "")

    text = _GERMAN_THOUSANDS_RE.sub(convert_thousands, value)

    def convert_decimal(match: re.Match[str]) -> str:
        fragment = match.group(0)
        converted_spans.append(match.span())
        return fragment.replace(",", ".")

    text = _GERMAN_DECIMAL_RE.sub(convert_decimal, text)

    for fragment_match in _NUMERIC_FRAGMENT_RE.finditer(value):
        start, end = fragment_match.span()
        if _is_inside_converted_span(start, end, converted_spans):
            continue

        fragment = fragment_match.group(0)
        if _looks_ambiguous_numeric(fragment):
            warnings.append(f"unparseable_numeric_fragment:{fragment}")

    return text


def _is_inside_converted_span(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start >= span_start and end <= span_end for span_start, span_end in spans)


def _looks_ambiguous_numeric(fragment: str) -> bool:
    if "," in fragment and "." in fragment:
        return True
    if fragment.count(",") > 1:
        return True
    if fragment.count(".") > 1:
        return True
    if fragment.endswith(",") or fragment.endswith("."):
        return True
    return False


def _apply_umlaut_fallbacks(value: str) -> str:
    return (
        value.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("Ã¤", "ae")
        .replace("Ã¶", "oe")
        .replace("Ã¼", "ue")
    )
