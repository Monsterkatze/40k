from __future__ import annotations

import csv
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


ENCODING_FALLBACK_ORDER = ("utf-8-sig", "cp1252", "latin-1")


class CsvIngestionError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedRecord:
    product_id: str
    product_name: str
    nutrition_raw_text: str
    row_number: int


@dataclass(frozen=True)
class RejectedRecord:
    row_number: int
    product_id: str
    product_name: str
    nutrition_raw_text: str
    reason: str


@dataclass
class IngestionStats:
    used_encoding: str
    total_rows: int = 0
    valid_rows: int = 0
    skipped_rows: int = 0
    rejected_records: list[RejectedRecord] = field(default_factory=list)


def iter_records(
    input_path: Path,
    logger: logging.Logger,
    limit: int | None = None,
) -> tuple[Iterator[NormalizedRecord], IngestionStats]:
    encoding = _select_encoding(input_path=input_path, logger=logger)
    stats = IngestionStats(used_encoding=encoding)

    def _generator() -> Iterator[NormalizedRecord]:
        with input_path.open("r", encoding=encoding, newline="") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=";")
            if not reader.fieldnames:
                raise CsvIngestionError("CSV appears to have no header row.")

            mapping = _resolve_header_mapping(reader.fieldnames)
            logger.info(
                "CSV ingestion started with encoding=%s header_map=%s",
                encoding,
                mapping,
            )

            for row_number, row in enumerate(reader, start=2):
                stats.total_rows += 1
                normalized, reason = _normalize_row(row=row, row_number=row_number, mapping=mapping)
                if normalized is None:
                    stats.skipped_rows += 1
                    rejected = RejectedRecord(
                        row_number=row_number,
                        product_id=(row.get(mapping["id"]) or "").strip(),
                        product_name=(row.get(mapping["name"]) or "").strip(),
                        nutrition_raw_text=(row.get(mapping["nutrition_raw_text"]) or "").strip(),
                        reason=reason or "ingestion_rejected",
                    )
                    stats.rejected_records.append(rejected)
                    logger.warning("Skipping row %s: %s", row_number, reason)
                    continue

                stats.valid_rows += 1
                yield normalized

                if limit is not None and stats.valid_rows >= limit:
                    logger.info("Ingestion limit reached (%s valid records)", limit)
                    break

    return _generator(), stats


def _select_encoding(input_path: Path, logger: logging.Logger) -> str:
    decode_errors: list[str] = []

    for encoding in ENCODING_FALLBACK_ORDER:
        try:
            _preflight_decode(input_path=input_path, encoding=encoding)
            return encoding
        except UnicodeDecodeError as exc:
            message = f"Encoding '{encoding}' failed with decode error: {exc}"
            decode_errors.append(message)
            logger.warning(message)

    raise CsvIngestionError(
        "Could not decode CSV with fallback order "
        f"{ENCODING_FALLBACK_ORDER}. Details: {' | '.join(decode_errors)}"
    )


def _preflight_decode(input_path: Path, encoding: str) -> None:
    with input_path.open("r", encoding=encoding, newline="") as csv_file:
        for _ in csv_file:
            pass


def _resolve_header_mapping(fieldnames: list[str]) -> dict[str, str]:
    original_by_normalized = {_normalize_header(name): name for name in fieldnames}

    id_column = _pick_first_match(
        original_by_normalized,
        explicit_aliases={"id", "produktid", "productid", "artikelid", "itemid", "sku", "ean"},
        token_aliases=(("product", "id"), ("artikel", "id"), ("item", "id")),
    )
    name_column = _pick_first_match(
        original_by_normalized,
        explicit_aliases={
            "name",
            "produktname",
            "productname",
            "artikelname",
            "bezeichnung",
            "titel",
            "title",
        },
        token_aliases=(("product", "name"), ("produkt", "name"), ("artikel", "name")),
    )
    nutrition_column = _pick_first_match(
        original_by_normalized,
        explicit_aliases={
            "nahrwerte",
            "naehrwerte",
            "nahrwert",
            "naehrwert",
            "nutrition",
            "nutritiontext",
            "nutritionraw",
            "nutritionrawtext",
            "nutritionalvalues",
            "energiundnahrwerte",
            "brennwertangaben",
        },
        token_aliases=(
            ("nahr", "wert"),
            ("naehr", "wert"),
            ("nutri",),
            ("brennwert",),
            ("energie", "nahr"),
        ),
    )

    missing: list[str] = []
    if id_column is None:
        missing.append("id")
    if name_column is None:
        missing.append("name")
    if nutrition_column is None:
        missing.append("nutrition raw text")
    if missing:
        raise CsvIngestionError(
            "Required header(s) missing after normalization: "
            f"{', '.join(missing)}. Available: {fieldnames}"
        )

    return {
        "id": id_column,
        "name": name_column,
        "nutrition_raw_text": nutrition_column,
    }


def _normalize_row(
    row: dict[str, str | None],
    row_number: int,
    mapping: dict[str, str],
) -> tuple[NormalizedRecord | None, str | None]:
    raw_id = (row.get(mapping["id"]) or "").strip()
    raw_name = (row.get(mapping["name"]) or "").strip()
    raw_nutrition = (row.get(mapping["nutrition_raw_text"]) or "").strip()

    missing_fields: list[str] = []
    if not raw_id:
        missing_fields.append("id")
    if not raw_name:
        missing_fields.append("name")
    if not raw_nutrition:
        missing_fields.append("nutrition_raw_text")

    if missing_fields:
        return None, f"missing required field(s): {', '.join(missing_fields)}"

    return (
        NormalizedRecord(
            product_id=raw_id,
            product_name=raw_name,
            nutrition_raw_text=raw_nutrition,
            row_number=row_number,
        ),
        None,
    )


def _pick_first_match(
    original_by_normalized: dict[str, str],
    explicit_aliases: set[str],
    token_aliases: tuple[tuple[str, ...], ...],
) -> str | None:
    for alias in explicit_aliases:
        if alias in original_by_normalized:
            return original_by_normalized[alias]

    for normalized_name, original in original_by_normalized.items():
        for token_group in token_aliases:
            if all(token in normalized_name for token in token_group):
                return original

    return None


def _normalize_header(value: str) -> str:
    lowered = value.strip().lower()
    lowered = (
        lowered.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("Ã¤", "ae")
        .replace("Ã¶", "oe")
        .replace("Ã¼", "ue")
        .replace("â€“", "-")
    )
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_diacritics = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", without_diacritics)
