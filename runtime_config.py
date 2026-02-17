from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile


class RuntimeConfigError(ValueError):
    pass


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    truthy = {"1", "true", "t", "yes", "y", "on"}
    falsy = {"0", "false", "f", "no", "n", "off"}
    if normalized in truthy:
        return True
    if normalized in falsy:
        return False
    raise RuntimeConfigError(
        f"Invalid boolean value for --resume: '{value}'. Use true/false."
    )


@dataclass(frozen=True)
class RuntimeConfig:
    input_path: Path
    output_dir: Path
    workers: int
    resume: bool
    limit: int | None

    def startup_summary(self) -> str:
        return (
            "Runtime configuration: "
            f"input='{self.input_path}', "
            f"output='{self.output_dir}', "
            f"workers={self.workers}, "
            f"resume={self.resume}, "
            f"limit={self.limit if self.limit is not None else 'none'}"
        )


def resolve_runtime_config(
    input_arg: str,
    output_arg: str,
    workers: int,
    resume: bool,
    limit: int | None,
) -> RuntimeConfig:
    input_path = Path(input_arg).expanduser().resolve()
    output_dir = Path(output_arg).expanduser().resolve()

    _validate_input_path(input_path)
    _validate_workers(workers)
    _validate_limit(limit)
    _validate_output_dir(output_dir)

    return RuntimeConfig(
        input_path=input_path,
        output_dir=output_dir,
        workers=workers,
        resume=resume,
        limit=limit,
    )


def _validate_input_path(input_path: Path) -> None:
    if not input_path.exists():
        raise RuntimeConfigError(f"Input file not found: {input_path}")
    if not input_path.is_file():
        raise RuntimeConfigError(f"Input path must be a file: {input_path}")


def _validate_workers(workers: int) -> None:
    if workers < 1:
        raise RuntimeConfigError("--workers must be a positive integer.")


def _validate_limit(limit: int | None) -> None:
    if limit is not None and limit < 1:
        raise RuntimeConfigError("--limit must be a positive integer when provided.")


def _validate_output_dir(output_dir: Path) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise RuntimeConfigError(
            f"Output path exists but is not a directory: {output_dir}"
        )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeConfigError(
            f"Could not create output directory: {output_dir}. {exc}"
        ) from exc

    try:
        with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".write_test_", delete=True):
            pass
    except OSError as exc:
        raise RuntimeConfigError(
            f"Output directory is not writable: {output_dir}. {exc}"
        ) from exc
