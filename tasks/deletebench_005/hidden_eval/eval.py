import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path


def _all_text(repo_root: Path) -> str:
    chunks = []
    for file_path in sorted(repo_root.rglob("*")):
        if not file_path.is_file():
            continue
        try:
            chunks.append(file_path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    return "\n".join(chunks)


def _run_probe(probe: dict[str, object], repo_root: Path) -> dict[str, object]:
    kind = str(probe["kind"])
    detail = ""
    passed = False

    if kind == "path_absent":
        relative_path = Path(str(probe["path"]))
        passed = not (repo_root / relative_path).exists()
        detail = f"Expected {relative_path} to be absent."
    elif kind == "path_present":
        relative_path = Path(str(probe["path"]))
        passed = (repo_root / relative_path).exists()
        detail = f"Expected {relative_path} to be present."
    elif kind in {"string_absent", "string_present"}:
        path = probe.get("path")
        target = str(probe["text"])
        if path is None:
            haystack = _all_text(repo_root)
        else:
            target_path = repo_root / str(path)
            if not target_path.exists():
                if kind == "string_absent":
                    haystack = ""
                    detail = f"File {target_path.relative_to(repo_root)} is absent, which satisfies string_absent."
                else:
                    detail = f"Expected file {target_path.relative_to(repo_root)} to exist."
                    haystack = None
            else:
                haystack = target_path.read_text(encoding="utf-8")
        if haystack is None:
            present = False
            passed = False
        else:
            present = target in haystack
            passed = not present if kind == "string_absent" else present
            if kind == "string_absent":
                detail = f"Expected string {target!r} to be absent."
            else:
                detail = f"Expected string {target!r} to be present."
    elif kind == "python_call":
        sys.path.insert(0, str(repo_root))
        module = importlib.import_module(str(probe["module"]))
        target = getattr(module, str(probe["callable"]))
        actual = target(*probe.get("args", []), **probe.get("kwargs", {}))
        expected = probe.get("expected")
        passed = actual == expected
        detail = f"Expected {expected!r}, got {actual!r}."
    elif kind == "command_success":
        completed = subprocess.run(
            str(probe["command"]),
            cwd=str(repo_root / str(probe.get("cwd", "."))),
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        passed = completed.returncode == 0
        detail = (completed.stdout + completed.stderr).strip()
    else:
        raise ValueError(f"Unsupported probe kind: {kind}")

    message = str(probe.get("message", "Probe passed." if passed else detail))
    if not passed and detail and detail not in message:
        message = f"{message} {detail}".strip()
    return {
        "probe_id": str(probe["probe_id"]),
        "passed": passed,
        "category": str(probe["category"]),
        "message": message,
        "weight": float(probe.get("weight", 1.0)),
        "failure_tags": [str(tag) for tag in probe.get("failure_tags", [])],
        "metadata": {"detail": detail},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    task_dir = Path(__file__).resolve().parent
    checks = json.loads((task_dir / "checks.json").read_text(encoding="utf-8"))
    repo_root = Path(args.repo).resolve()
    payload = {"probes": [_run_probe(probe, repo_root) for probe in checks["probes"]]}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
