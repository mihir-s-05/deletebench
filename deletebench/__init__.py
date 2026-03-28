"""DeleteBench benchmark harness."""

from deletebench.evaluator import evaluate_task
from deletebench.reporting import summarize_results
from deletebench.runner import run_task
from deletebench.tasks.loader import load_task, load_tasks
from deletebench.tasks.schemas import AgentResult, EvaluationResult, ProbeResult, Task

__version__ = "0.1.0"

__all__ = [
    "AgentResult",
    "EvaluationResult",
    "ProbeResult",
    "Task",
    "evaluate_task",
    "load_task",
    "load_tasks",
    "run_task",
    "summarize_results",
]
