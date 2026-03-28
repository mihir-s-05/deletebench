from __future__ import annotations

import difflib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping


EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}


@dataclass(slots=True)
class DiffStats:
    diff_text: str
    files_changed: list[str]
    added_lines: int
    deleted_lines: int
    touched_directories: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _should_skip(relative_path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in relative_path.parts)


def snapshot_directory(root: str | Path) -> dict[str, str]:
    root_path = Path(root)
    snapshot: dict[str, str] = {}
    if not root_path.exists():
        return snapshot

    for file_path in sorted(root_path.rglob("*")):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(root_path)
        if _should_skip(relative_path):
            continue
        try:
            snapshot[str(relative_path)] = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return snapshot


def load_reference_snapshot(reference_solution_path: str | Path) -> dict[str, str]:
    payload = json.loads(Path(reference_solution_path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "files" in payload:
        return {str(path): str(content) for path, content in payload["files"].items()}
    return {str(path): str(content) for path, content in payload.items()}


def diff_snapshots(before: Mapping[str, str], after: Mapping[str, str]) -> DiffStats:
    diff_chunks: list[str] = []
    files_changed: list[str] = []
    added_lines = 0
    deleted_lines = 0
    touched_directories: set[str] = set()

    for relative_path in sorted(set(before) | set(after)):
        old_text = before.get(relative_path)
        new_text = after.get(relative_path)
        if old_text == new_text:
            continue

        files_changed.append(relative_path)
        touched_directories.add(str(Path(relative_path).parent))
        old_lines = [] if old_text is None else old_text.splitlines(keepends=True)
        new_lines = [] if new_text is None else new_text.splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{relative_path}",
                tofile=f"b/{relative_path}",
            )
        )
        for line in diff_lines:
            if line.startswith(("---", "+++", "@@")):
                continue
            if line.startswith("+"):
                added_lines += 1
            elif line.startswith("-"):
                deleted_lines += 1
        diff_chunks.append("".join(diff_lines))

    normalized_directories = sorted("." if item == "." else item for item in touched_directories)
    diff_text = "\n".join(chunk.rstrip() for chunk in diff_chunks if chunk).rstrip()
    if diff_text:
        diff_text += "\n"

    return DiffStats(
        diff_text=diff_text,
        files_changed=files_changed,
        added_lines=added_lines,
        deleted_lines=deleted_lines,
        touched_directories=normalized_directories,
    )


def diff_directories(before_dir: str | Path, after_dir: str | Path) -> DiffStats:
    return diff_snapshots(snapshot_directory(before_dir), snapshot_directory(after_dir))
