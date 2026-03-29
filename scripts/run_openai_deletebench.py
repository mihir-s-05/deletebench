from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field


MAX_FILE_BYTES = 16_000
MAX_FILES = 200


class FileEdit(BaseModel):
    path: str = Field(description="Path relative to the workspace root.")
    action: Literal["write", "delete"]
    content: str | None = Field(
        default=None,
        description="Required when action is write; omitted for delete.",
    )


class BenchmarkEdits(BaseModel):
    summary: str
    edits: list[FileEdit]


def collect_workspace_snapshot(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    count = 0
    for file_path in sorted(root.rglob("*")):
        if count >= MAX_FILES:
            break
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(root)
        if any(part in {".git", "__pycache__", ".pytest_cache", ".mypy_cache"} for part in relative.parts):
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if len(text.encode("utf-8")) > MAX_FILE_BYTES:
            text = text[:MAX_FILE_BYTES] + "\n...<truncated>..."
        snapshot[str(relative)] = text
        count += 1
    return snapshot


def apply_edits(workspace: Path, edits: list[FileEdit]) -> None:
    for edit in edits:
        target = workspace / edit.path
        if edit.action == "delete":
            if target.exists():
                target.unlink()
            continue

        if edit.content is None:
            raise ValueError(f"Write edit for {edit.path} is missing content.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(edit.content, encoding="utf-8")


def build_prompt(task_id: str, prompt: str, snapshot: dict[str, str]) -> str:
    files_block = "\n\n".join(
        f"FILE: {path}\n```\n{content}\n```" for path, content in snapshot.items()
    )
    return (
        "You are editing a local coding-task workspace for DeleteBench.\n"
        "Return only the minimal file operations required to satisfy the task.\n"
        "Prefer precise deletions and localized edits over rewrites.\n"
        "Paths must be relative to the workspace root.\n"
        "Do not invent placeholder stubs, deprecation banners, or TODO removals.\n\n"
        f"TASK ID: {task_id}\n\n"
        "USER TASK:\n"
        f"{prompt}\n\n"
        "WORKSPACE FILES:\n"
        f"{files_block}\n"
    )


def main() -> int:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required.")

    model = os.environ.get("DELETEBENCH_OPENAI_MODEL", "gpt-5.4-mini")
    reasoning_effort = os.environ.get("DELETEBENCH_OPENAI_REASONING_EFFORT", "medium")
    verbosity = os.environ.get("DELETEBENCH_OPENAI_VERBOSITY", "low")

    task_id = os.environ["DELETEBENCH_TASK_ID"]
    prompt = os.environ["DELETEBENCH_PROMPT"]
    workspace = Path(os.environ["DELETEBENCH_WORKSPACE"])

    snapshot = collect_workspace_snapshot(workspace)
    request_prompt = build_prompt(task_id, prompt, snapshot)

    client = OpenAI(api_key=api_key)
    response = client.responses.parse(
        model=model,
        input=request_prompt,
        reasoning={"effort": reasoning_effort},
        text={"verbosity": verbosity},
        text_format=BenchmarkEdits,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("Model did not return a structured response.")

    apply_edits(workspace, parsed.edits)
    print(json.dumps({"summary": parsed.summary, "edit_count": len(parsed.edits)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
