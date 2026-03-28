from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from deletebench.tasks.schemas import Task
from deletebench.utils.subprocess_utils import run_command


@dataclass(slots=True)
class AgentExecution:
    runtime_seconds: float
    logs_path: str
    model_id: str
    metadata: dict[str, object] = field(default_factory=dict)


class Agent(ABC):
    model_id: str

    @abstractmethod
    def run(
        self,
        task: Task,
        workspace: Path,
        output_dir: Path,
        *,
        timeout: int | None = None,
    ) -> AgentExecution:
        raise NotImplementedError


class NoOpAgent(Agent):
    model_id = "noop"

    def run(
        self,
        task: Task,
        workspace: Path,
        output_dir: Path,
        *,
        timeout: int | None = None,
    ) -> AgentExecution:
        logs_path = output_dir / "agent.log"
        logs_path.write_text("NoOpAgent left the repository unchanged.\n", encoding="utf-8")
        return AgentExecution(runtime_seconds=0.0, logs_path=str(logs_path), model_id=self.model_id)


class ReferenceAgent(Agent):
    model_id = "reference"

    def run(
        self,
        task: Task,
        workspace: Path,
        output_dir: Path,
        *,
        timeout: int | None = None,
    ) -> AgentExecution:
        payload = json.loads(task.reference_solution_path.read_text(encoding="utf-8"))
        files = payload["files"] if isinstance(payload, dict) and "files" in payload else payload
        desired_paths = {Path(relative_path) for relative_path in files}

        for file_path in sorted(workspace.rglob("*"), reverse=True):
            if not file_path.exists():
                continue
            if file_path.is_file():
                relative_path = file_path.relative_to(workspace)
                if relative_path not in desired_paths:
                    file_path.unlink()
            elif file_path.is_dir() and not any(file_path.iterdir()):
                file_path.rmdir()

        for relative_path, content in files.items():
            destination = workspace / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")

        for dir_path in sorted([path for path in workspace.rglob("*") if path.is_dir()], reverse=True):
            if not any(dir_path.iterdir()):
                dir_path.rmdir()

        logs_path = output_dir / "agent.log"
        logs_path.write_text(
            "ReferenceAgent applied the hidden reference solution snapshot.\n",
            encoding="utf-8",
        )
        return AgentExecution(runtime_seconds=0.0, logs_path=str(logs_path), model_id=self.model_id)


class CommandAgent(Agent):
    def __init__(self, command: str) -> None:
        if not command.strip():
            raise ValueError("Command agent requires a non-empty command.")
        self.command = command
        self.model_id = "command"

    def run(
        self,
        task: Task,
        workspace: Path,
        output_dir: Path,
        *,
        timeout: int | None = None,
    ) -> AgentExecution:
        logs_path = output_dir / "agent.log"
        env = os.environ.copy()
        env.update(
            {
                "DELETEBENCH_TASK_ID": task.task_id,
                "DELETEBENCH_PROMPT": task.prompt,
                "DELETEBENCH_TASK_PATH": str(task.task_path),
                "DELETEBENCH_WORKSPACE": str(workspace),
            }
        )
        result = run_command(self.command, cwd=workspace, timeout=timeout, env=env)
        logs_path.write_text(
            f"$ {self.command}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n",
            encoding="utf-8",
        )
        return AgentExecution(
            runtime_seconds=result.runtime_seconds,
            logs_path=str(logs_path),
            model_id=self.model_id,
            metadata={"command": self.command, "returncode": result.returncode},
        )


def resolve_agent(model_id: str, *, command: str | None = None) -> Agent:
    if model_id == "reference":
        return ReferenceAgent()
    if model_id == "noop":
        return NoOpAgent()
    if model_id == "command":
        if command is None:
            raise ValueError("The command agent requires --agent-command.")
        return CommandAgent(command)
    raise ValueError(f"Unsupported agent model: {model_id}")
