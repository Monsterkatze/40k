from __future__ import annotations

import concurrent.futures
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from PIL import Image, ImageDraw, ImageFont

from cell_classification import ClassifiedRecord, MIXED, NUTRITION
from nutrition_parser import TARGET_FIELDS
from validation_status import STATUS_OK, STATUS_OK_WITH_WARNINGS


CANVAS_SIZE = (1200, 1200)
BACKGROUND_COLOR = "white"
TEXT_COLOR = "black"
PLACEHOLDER_VALUE = "—"
JPG_QUALITY = 92
INGREDIENTS_PLACEHOLDER = "Keine Angaben"
INGREDIENTS_BLOCK_HEIGHT = 226
INGREDIENTS_FONT_MAX_SIZE = 30
INGREDIENTS_FONT_MIN_SIZE = 6
INGREDIENTS_LINE_GAP = 3

RENDERABLE_STATUSES: tuple[str, ...] = (STATUS_OK, STATUS_OK_WITH_WARNINGS)
RENDERABLE_CATEGORIES: tuple[str, ...] = (NUTRITION, MIXED)

FIELD_LABELS: dict[str, str] = {
    "kJ": "Energie (kJ)",
    "kcal": "Energie (kcal)",
    "fat_g": "Fett",
    "satfat_g": "davon ges. Fettsäuren",
    "carbs_g": "Kohlenhydrate",
    "sugar_g": "davon Zucker",
    "protein_g": "Eiweiß",
    "salt_g": "Salz",
    "fiber_g": "Ballaststoffe",
}

FIELD_UNITS: dict[str, str] = {
    "kJ": "kJ",
    "kcal": "kcal",
    "fat_g": "g",
    "satfat_g": "g",
    "carbs_g": "g",
    "sugar_g": "g",
    "protein_g": "g",
    "salt_g": "g",
    "fiber_g": "g",
}


@dataclass(frozen=True)
class RenderFailure:
    product_id: str
    error: str


@dataclass(frozen=True)
class RenderBatchResult:
    rendered_paths: tuple[Path, ...]
    skipped_ids: tuple[str, ...]
    failures: tuple[RenderFailure, ...]


@dataclass(frozen=True)
class RenderPipelineResult:
    rendered_paths: tuple[Path, ...]
    skipped_non_renderable_ids: tuple[str, ...]
    skipped_existing_ids: tuple[str, ...]
    failures: tuple[RenderFailure, ...]
    total_eligible_count: int


@dataclass(frozen=True)
class _RenderJob:
    index: int
    product_id: str
    output_path: Path
    record: ClassifiedRecord


def render_nutrition_jpgs(
    records: Iterable[ClassifiedRecord],
    output_dir: Path,
    include_statuses: tuple[str, ...] = RENDERABLE_STATUSES,
    placeholder: str = PLACEHOLDER_VALUE,
) -> RenderBatchResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    rendered_paths: list[Path] = []
    skipped_ids: list[str] = []
    failures: list[RenderFailure] = []

    for record in records:
        product_id = record.product_id.strip() or f"row_{record.row_number}"
        if not _is_renderable(record, include_statuses):
            skipped_ids.append(product_id)
            continue

        output_path = output_dir / f"{_safe_filename(record.product_id)}.jpg"
        try:
            render_nutrition_jpg(
                output_path=output_path,
                product_id=record.product_id,
                product_name=record.product_name,
                ingredients_text=record.ingredients_text,
                extracted_nutrition=record.extracted_nutrition,
                status=record.status,
                parsed_fields_count=record.parsed_fields_count,
                placeholder=placeholder,
            )
            rendered_paths.append(output_path)
        except Exception as exc:
            failures.append(RenderFailure(product_id=product_id, error=str(exc)))

    return RenderBatchResult(
        rendered_paths=tuple(rendered_paths),
        skipped_ids=tuple(skipped_ids),
        failures=tuple(failures),
    )


def render_nutrition_jpgs_pipeline(
    records: Iterable[ClassifiedRecord],
    output_dir: Path,
    workers: int,
    resume: bool,
    include_statuses: tuple[str, ...] = RENDERABLE_STATUSES,
    placeholder: str = PLACEHOLDER_VALUE,
) -> RenderPipelineResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[_RenderJob] = []
    skipped_non_renderable_ids: list[str] = []
    skipped_existing_ids: list[str] = []

    for index, record in enumerate(records):
        product_id = record.product_id.strip() or f"row_{record.row_number}"
        if not _is_renderable(record, include_statuses):
            skipped_non_renderable_ids.append(product_id)
            continue

        safe_product_id = _safe_filename(record.product_id) or _safe_filename(product_id)
        shard_prefix = _shard_prefix(safe_product_id)
        output_path = output_dir / shard_prefix / f"{safe_product_id}.jpg"

        if resume and output_path.exists():
            skipped_existing_ids.append(product_id)
            continue

        jobs.append(
            _RenderJob(
                index=index,
                product_id=product_id,
                output_path=output_path,
                record=record,
            )
        )

    rendered_entries: list[tuple[int, Path]] = []
    failure_entries: list[tuple[int, RenderFailure]] = []

    if jobs:
        worker_count = max(1, min(workers, len(jobs)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_job = {
                executor.submit(_render_job, job, placeholder): job
                for job in jobs
            }
            for future in concurrent.futures.as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    rendered_path = future.result()
                    rendered_entries.append((job.index, rendered_path))
                except Exception as exc:
                    failure_entries.append(
                        (
                            job.index,
                            RenderFailure(product_id=job.product_id, error=str(exc)),
                        )
                    )

    rendered_paths = tuple(path for _, path in sorted(rendered_entries, key=lambda item: item[0]))
    failures = tuple(failure for _, failure in sorted(failure_entries, key=lambda item: item[0]))

    return RenderPipelineResult(
        rendered_paths=rendered_paths,
        skipped_non_renderable_ids=tuple(skipped_non_renderable_ids),
        skipped_existing_ids=tuple(skipped_existing_ids),
        failures=failures,
        total_eligible_count=len(jobs) + len(skipped_existing_ids),
    )


def render_nutrition_jpg(
    output_path: Path,
    product_id: str,
    product_name: str,
    ingredients_text: str | None,
    extracted_nutrition: Mapping[str, float | int | None],
    status: str,
    parsed_fields_count: int,
    placeholder: str = PLACEHOLDER_VALUE,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGB", CANVAS_SIZE, BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)
    title_font, header_font, row_font = _load_fonts()

    width, height = CANVAS_SIZE
    outer_margin = 72
    title_y = 72
    draw.text((outer_margin, title_y), "Nährwertangaben", fill=TEXT_COLOR, font=title_font)

    meta_y = title_y + 78
    display_name = (product_name or "Unbenanntes Produkt").strip()
    draw.text((outer_margin, meta_y), display_name, fill=TEXT_COLOR, font=header_font)
    draw.text(
        (outer_margin, meta_y + 44),
        f"ID: {product_id.strip() or '-'}",
        fill=TEXT_COLOR,
        font=row_font,
    )

    ingredients_left = outer_margin
    ingredients_right = width - outer_margin
    ingredients_top = meta_y + 86
    ingredients_bottom = ingredients_top + INGREDIENTS_BLOCK_HEIGHT

    draw.rectangle(
        (ingredients_left, ingredients_top, ingredients_right, ingredients_bottom),
        outline=TEXT_COLOR,
        width=2,
    )
    draw.text(
        (ingredients_left + 16, ingredients_top + 10),
        "Zutaten",
        fill=TEXT_COLOR,
        font=header_font,
    )

    content_top = ingredients_top + 56
    content_width = ingredients_right - ingredients_left - 32
    content_height = ingredients_bottom - content_top - 10
    ingredients_font, wrapped_lines, line_height, _ = _compute_ingredients_layout(
        draw=draw,
        ingredients_text=ingredients_text,
        max_width=content_width,
        max_height=content_height,
    )

    for line_index, line_text in enumerate(wrapped_lines):
        draw.text(
            (ingredients_left + 16, content_top + line_index * (line_height + INGREDIENTS_LINE_GAP)),
            line_text,
            fill=TEXT_COLOR,
            font=ingredients_font,
        )

    table_top = ingredients_bottom + 22
    table_left = outer_margin
    table_right = width - outer_margin
    table_bottom = height - outer_margin
    row_count = len(TARGET_FIELDS) + 1
    row_height = (table_bottom - table_top) / row_count
    split_x = table_left + int((table_right - table_left) * 0.67)

    draw.rectangle((table_left, table_top, table_right, table_bottom), outline=TEXT_COLOR, width=3)
    draw.line((split_x, table_top, split_x, table_bottom), fill=TEXT_COLOR, width=2)

    draw.text((table_left + 20, table_top + 12), "Feld", fill=TEXT_COLOR, font=header_font)
    draw.text((split_x + 20, table_top + 12), "Wert", fill=TEXT_COLOR, font=header_font)

    for index, field_name in enumerate(TARGET_FIELDS, start=1):
        row_top = table_top + int(index * row_height)
        draw.line((table_left, row_top, table_right, row_top), fill=TEXT_COLOR, width=1)

        label = FIELD_LABELS.get(field_name, field_name)
        value = _format_field_value(
            field_name=field_name,
            value=extracted_nutrition.get(field_name),
            placeholder=placeholder,
        )

        text_y = row_top + int((row_height - 32) / 2)
        draw.text((table_left + 20, text_y), label, fill=TEXT_COLOR, font=row_font)
        draw.text((split_x + 20, text_y), value, fill=TEXT_COLOR, font=row_font)

    image.save(output_path, format="JPEG", quality=JPG_QUALITY, optimize=True)


def _is_renderable(record: ClassifiedRecord, include_statuses: tuple[str, ...]) -> bool:
    if record.status not in include_statuses:
        return False
    if record.category not in RENDERABLE_CATEGORIES:
        return False
    return isinstance(record.extracted_nutrition, dict)


def _format_field_value(field_name: str, value: float | int | None, placeholder: str) -> str:
    if value is None or not isinstance(value, (int, float)):
        return placeholder

    numeric = float(value)
    if numeric.is_integer():
        number_text = str(int(numeric))
    else:
        number_text = f"{numeric:.2f}".rstrip("0").rstrip(".")

    unit = FIELD_UNITS.get(field_name, "")
    if unit:
        return f"{number_text} {unit}"
    return number_text


def _safe_filename(product_id: str) -> str:
    candidate = (product_id or "unknown").strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate)
    return cleaned or "unknown"


def _compute_ingredients_layout(
    draw: ImageDraw.ImageDraw,
    ingredients_text: str | None,
    max_width: int,
    max_height: int,
) -> tuple[ImageFont.ImageFont, tuple[str, ...], int, int]:
    normalized = _normalize_ingredients_text(ingredients_text)

    for font_size in range(INGREDIENTS_FONT_MAX_SIZE, INGREDIENTS_FONT_MIN_SIZE - 1, -1):
        font = _load_font_at_size(font_size)
        wrapped = _wrap_text_by_width(
            draw=draw,
            font=font,
            text=normalized,
            max_width=max_width,
        )
        if not wrapped:
            wrapped = [INGREDIENTS_PLACEHOLDER]

        line_height = _measure_line_height(font)
        content_height_used = _measure_content_height(line_height, len(wrapped))
        if content_height_used <= max_height:
            return font, tuple(wrapped), line_height, content_height_used

    fallback_font = _load_font_at_size(INGREDIENTS_FONT_MIN_SIZE)
    fallback_wrapped = _wrap_text_by_width(
        draw=draw,
        font=fallback_font,
        text=normalized,
        max_width=max_width,
    )
    if not fallback_wrapped:
        fallback_wrapped = [INGREDIENTS_PLACEHOLDER]
    fallback_line_height = _measure_line_height(fallback_font)
    fallback_used_height = _measure_content_height(fallback_line_height, len(fallback_wrapped))
    return fallback_font, tuple(fallback_wrapped), fallback_line_height, fallback_used_height


def _normalize_ingredients_text(value: str | None) -> str:
    if value is None:
        return INGREDIENTS_PLACEHOLDER

    normalized = " ".join(str(value).replace("\n", " ").split())
    return normalized if normalized else INGREDIENTS_PLACEHOLDER


def _wrap_text_by_width(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    text: str,
    max_width: int,
) -> list[str]:
    words = text.split(" ")
    if not words:
        return [INGREDIENTS_PLACEHOLDER]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        if draw.textlength(word, font=font) <= max_width:
            current = word
            continue

        split_chunks = _split_long_word(draw=draw, font=font, word=word, max_width=max_width)
        lines.extend(split_chunks[:-1])
        current = split_chunks[-1]

    if current:
        lines.append(current)

    return lines


def _split_long_word(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    word: str,
    max_width: int,
) -> list[str]:
    chunks: list[str] = []
    current = ""
    for char in word:
        candidate = f"{current}{char}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = char

    if current:
        chunks.append(current)
    return chunks or [word]


def _measure_line_height(font: ImageFont.ImageFont) -> int:
    left, top, right, bottom = font.getbbox("Ag")
    height = bottom - top
    return max(1, int(height))


def _measure_content_height(line_height: int, line_count: int) -> int:
    if line_count <= 0:
        return 0
    return line_height * line_count + INGREDIENTS_LINE_GAP * (line_count - 1)


def _load_font_at_size(size: int) -> ImageFont.ImageFont:
    candidates = (
        "arial.ttf",
        "segoeui.ttf",
        "DejaVuSans.ttf",
    )

    for font_name in candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue

    return ImageFont.load_default()


def _shard_prefix(safe_product_id: str) -> str:
    normalized = (safe_product_id or "").strip().lower()
    if len(normalized) >= 2:
        return normalized[:2]
    if len(normalized) == 1:
        return f"{normalized}_"
    return "__"


def _render_job(job: _RenderJob, placeholder: str) -> Path:
    render_nutrition_jpg(
        output_path=job.output_path,
        product_id=job.record.product_id,
        product_name=job.record.product_name,
        ingredients_text=job.record.ingredients_text,
        extracted_nutrition=job.record.extracted_nutrition,
        status=job.record.status,
        parsed_fields_count=job.record.parsed_fields_count,
        placeholder=placeholder,
    )
    return job.output_path


def _load_fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont]:
    candidates = (
        "arial.ttf",
        "segoeui.ttf",
        "DejaVuSans.ttf",
    )

    for font_name in candidates:
        try:
            return (
                ImageFont.truetype(font_name, 52),
                ImageFont.truetype(font_name, 34),
                ImageFont.truetype(font_name, 30),
            )
        except OSError:
            continue

    fallback = ImageFont.load_default()
    return (fallback, fallback, fallback)