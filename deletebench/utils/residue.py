from __future__ import annotations

import json
import re
from pathlib import Path

from deletebench.tasks.schemas import ProbeResult


TEXT_EXCLUDES = {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_residue_rules(path: str | Path) -> dict[str, list[str]]:
    raw_text = Path(path).read_text(encoding="utf-8").strip()
    if not raw_text:
        return {}
    if raw_text.startswith("{"):
        payload = json.loads(raw_text)
        if not isinstance(payload, dict):
            raise ValueError("Residue rules JSON must be an object mapping rule groups to lists.")
        return {str(key): [str(item) for item in value] for key, value in payload.items()}

    rules: dict[str, list[str]] = {}
    current_key: str | None = None
    for raw_line in raw_text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not raw_line.startswith((" ", "\t")):
            key, _, remainder = line.partition(":")
            current_key = key.strip()
            rules.setdefault(current_key, [])
            remainder = remainder.strip()
            if remainder:
                rules[current_key].append(_strip_quotes(remainder))
        else:
            stripped = line.strip()
            if current_key is None or not stripped.startswith("- "):
                continue
            rules[current_key].append(_strip_quotes(stripped[2:].strip()))
    return rules


def iter_text_files(repo_path: str | Path) -> list[tuple[str, str]]:
    root = Path(repo_path)
    results: list[tuple[str, str]] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(root)
        if any(part in TEXT_EXCLUDES for part in relative_path.parts):
            continue
        try:
            results.append((str(relative_path), file_path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    return results


def run_residue_checks(repo_path: str | Path, rules: dict[str, list[str]]) -> list[ProbeResult]:
    files = iter_text_files(repo_path)
    probes: list[ProbeResult] = []

    for index, pattern in enumerate(rules.get("banned_patterns", []), start=1):
        regex = re.compile(pattern)
        matches: list[str] = []
        for relative_path, text in files:
            match = regex.search(text)
            if match:
                matches.append(f"{relative_path}: matched {match.group(0)!r}")
        probes.append(
            ProbeResult(
                probe_id=f"residue_banned_pattern_{index}",
                passed=not matches,
                category="residue_cleanup",
                message=(
                    f"Pattern {pattern!r} is absent as expected."
                    if not matches
                    else f"Pattern {pattern!r} still appears in the repo."
                ),
                failure_tags=["dead_residue"],
                metadata={"pattern": pattern, "matches": matches[:5]},
            )
        )

    for index, symbol in enumerate(rules.get("forbidden_symbols", []), start=1):
        matches = [relative_path for relative_path, text in files if symbol in text]
        probes.append(
            ProbeResult(
                probe_id=f"residue_forbidden_symbol_{index}",
                passed=not matches,
                category="residue_cleanup",
                message=(
                    f"Symbol {symbol!r} is absent as expected."
                    if not matches
                    else f"Forbidden symbol {symbol!r} still appears in the repo."
                ),
                failure_tags=["dead_residue", "under_deletion"],
                metadata={"symbol": symbol, "matches": matches[:5]},
            )
        )

    for index, forbidden_path in enumerate(rules.get("forbidden_paths", []), start=1):
        exists = (Path(repo_path) / forbidden_path).exists()
        probes.append(
            ProbeResult(
                probe_id=f"residue_forbidden_path_{index}",
                passed=not exists,
                category="residue_cleanup",
                message=(
                    f"Path {forbidden_path!r} has been removed."
                    if not exists
                    else f"Path {forbidden_path!r} still exists."
                ),
                failure_tags=["dead_residue", "under_deletion"],
                metadata={"path": forbidden_path},
            )
        )

    return probes
