 # DeleteBench

 DeleteBench is a benchmark harness for evaluating whether a coding model or agent can
 remove a feature from a repository cleanly, preserve adjacent behavior, and avoid
 leaving behind residue such as stale flags, dead tests, or placeholder stubs.

 This repository implements a v0 benchmark framework plus a generated 12-task starter
 suite of Python microrepos.

 ## What this repository contains

 - A Python benchmark harness:
   - task loading
   - task validation
   - agent execution
   - evaluation
   - scoring
   - reporting
   - CLI entrypoints
- A generated v0 task suite under `tasks/`
- Tests for the harness itself under `tests/`

 ## Current benchmark scope

 The current task pack is a purpose-built v0 microrepo suite with:

 - 3 UI-only removal tasks
 - 3 full-stack feature removal tasks
 - 2 feature-flag sunset tasks
 - 2 shared abstraction pruning tasks
 - 2 legacy cleanup tasks

 This is intended as a trusted local benchmark starter suite, not yet a realism-heavy
 historical benchmark corpus.

 ## Trust and security assumptions

 This repository is currently designed for trusted local use.

 It is safe for:

 - locally-authored tasks
 - local experiments
 - controlled internal benchmarking

 It is not hardened for:

 - untrusted community task packs
 - arbitrary third-party hidden eval scripts
 - remote multi-tenant execution without sandboxing

 Reasons:

 - task hidden eval executes local Python
 - the command agent can run arbitrary shell commands
 - subprocess command strings may use the shell

 If you want to use this with untrusted task packs, add sandboxing or containerization
 first.

 ## Requirements

 - Python 3.11+

 No third-party runtime dependencies are required for the current v0 harness.

 ## Setup

 You can run the CLI directly with Python:

 ```bash
 python3 -m deletebench.cli --help
 ```

 Or install the package in editable mode:

 ```bash
 pip install -e .
 deletebench --help
 ```

 ## Common CLI commands

 ### Generate the canonical task pack

 ```bash
 python3 -m deletebench.cli generate-tasks --tasks-root tasks --force
 ```

 This regenerates the 12-task v0 suite.

 ### Validate tasks

 ```bash
 python3 -m deletebench.cli validate-tasks --tasks-root tasks
 ```

 Use this before benchmarking to make sure the task pack is well-formed.

 ### List tasks

 ```bash
 python3 -m deletebench.cli list-tasks --tasks-root tasks
 ```

 ### Show a task

 ```bash
 python3 -m deletebench.cli show-task deletebench_004 --tasks-root tasks
 ```

 This prints the public task manifest and prompt.

 ### Run one task

 ```bash
 python3 -m deletebench.cli run-task deletebench_004 \
   --tasks-root tasks \
   --agent reference \
   --output-dir results
 ```

 ### Run the full suite

 ```bash
 python3 -m deletebench.cli run-suite \
   --tasks-root tasks \
   --agent reference \
   --output-dir results
 ```

 ### Summarize saved results

 ```bash
 python3 -m deletebench.cli summarize --results-dir results
 ```

 ## Available agent modes

 ### `reference`

 Applies the hidden reference solution to the workspace.

 Use this to verify:

 - generated tasks are internally coherent
 - hidden probes are satisfiable
 - the benchmark harness is behaving correctly

 ### `noop`

 Leaves the workspace unchanged.

 Use this as a negative control to make sure the benchmark catches obvious failure.

 ### `command`

 Runs your own command inside the task workspace.

 This is the path for benchmarking real models today.

## Is this ready to benchmark real models?

Yes.

This repository now includes a built-in OpenAI wrapper script at:

- `scripts/run_openai_deletebench.py`

It defaults to:

- model: `gpt-5.4-mini`

That means:

- the benchmark harness is ready now
- the scoring pipeline is ready now
- the task suite is ready now
- OpenAI benchmarking is ready now
- for non-OpenAI providers, you still need a thin wrapper script

## How to benchmark a real model right now

 The runner sets these environment variables for the `command` agent:

 - `DELETEBENCH_TASK_ID`
 - `DELETEBENCH_PROMPT`
 - `DELETEBENCH_TASK_PATH`
 - `DELETEBENCH_WORKSPACE`

 Your script should:

 1. read the prompt and workspace path
 2. call your model or agent
 3. edit files inside `DELETEBENCH_WORKSPACE`
 4. exit successfully when done

### OpenAI quick start for `gpt-5.4-mini`

Install the optional dependency:

```bash
pip install -e ".[openai]"
```

Set your API key:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

Run one task with the built-in OpenAI wrapper:

```bash
python3 -m deletebench.cli run-task deletebench_004 \
  --tasks-root tasks \
  --agent command \
  --agent-command "python3 scripts/run_openai_deletebench.py" \
  --output-dir results/openai-gpt-5_4-mini
```

Run the full suite:

```bash
python3 -m deletebench.cli run-suite \
  --tasks-root tasks \
  --agent command \
  --agent-command "python3 scripts/run_openai_deletebench.py" \
  --output-dir results/openai-gpt-5_4-mini
```

Summarize:

```bash
python3 -m deletebench.cli summarize --results-dir results/openai-gpt-5_4-mini
```

### OpenAI wrapper configuration

The built-in wrapper reads:

- `OPENAI_API_KEY` (required)
- `DELETEBENCH_OPENAI_MODEL` (optional, defaults to `gpt-5.4-mini`)
- `DELETEBENCH_OPENAI_REASONING_EFFORT` (optional, defaults to `medium`)
- `DELETEBENCH_OPENAI_VERBOSITY` (optional, defaults to `low`)

Example:

```bash
export OPENAI_API_KEY="your_api_key_here"
export DELETEBENCH_OPENAI_MODEL="gpt-5.4-mini"
export DELETEBENCH_OPENAI_REASONING_EFFORT="medium"
export DELETEBENCH_OPENAI_VERBOSITY="low"
```

### Generic command-agent run

 ```bash
 python3 -m deletebench.cli run-task deletebench_004 \
   --tasks-root tasks \
   --agent command \
   --agent-command "python3 scripts/run_model.py" \
   --output-dir results
 ```

 Or a full suite:

 ```bash
 python3 -m deletebench.cli run-suite \
   --tasks-root tasks \
   --agent command \
   --agent-command "python3 scripts/run_model.py" \
   --output-dir results
 ```

## Minimal wrapper example

Example custom wrapper `scripts/run_model.py`:

 ```python
 import os
 from pathlib import Path

 prompt = os.environ["DELETEBENCH_PROMPT"]
 workspace = Path(os.environ["DELETEBENCH_WORKSPACE"])
 task_id = os.environ["DELETEBENCH_TASK_ID"]

 # Replace this section with your real model call.
 # Your model should inspect the workspace, decide what to delete or edit,
 # and then write changes under `workspace`.

 print(f"Running task {task_id}")
 print(prompt)
 ```

 In practice, your wrapper will usually:

 - collect relevant files from the workspace
 - send them with the prompt to your model
 - parse the model output
 - apply file edits into the workspace

## What the built-in OpenAI wrapper does

`scripts/run_openai_deletebench.py`:

- snapshots the current workspace text files
- sends the task prompt plus workspace contents to OpenAI Responses API
- asks for structured file operations
- applies returned writes/deletes into the workspace

The current implementation is intentionally simple and v0-friendly:

- it operates over text files only
- it truncates very large files
- it relies on structured output for edit application

If you want stronger performance later, likely improvements are:

- multi-turn repair loops
- file selection / retrieval instead of whole-workspace snapshots
- patch-oriented outputs instead of full file rewrites
- model-specific retry logic

 ## What gets scored

 Each run is scored across these components:

 - removal completeness
 - regression safety
 - residue cleanup
 - diff hygiene
 - spec compliance

 Evaluation combines:

 - task build/test commands
 - hidden behavior probes
 - hidden regression probes
 - residue checks
 - global anti-gaming checks
 - soft diff-hygiene budgets

 ## Output structure

 Benchmark outputs are written under your chosen results directory.

 Each run writes a timestamped directory containing:

 - `agent_result.json`
 - `evaluation.json`
 - `task.json`
 - `diff.patch`
 - a copied `workspace/`
 - `agent.log`

 `evaluation.json` contains:

 - total score
 - sub-scores by category
 - all probe results
 - failure tags
 - run metadata

 ## Typical workflow

 1. Generate tasks
 2. Validate tasks
 3. Smoke-test the reference baseline
 4. Run your model through the `command` agent
 5. Summarize results
 6. Compare scores across models or prompts

 Example:

 ```bash
 python3 -m deletebench.cli generate-tasks --tasks-root tasks --force
 python3 -m deletebench.cli validate-tasks --tasks-root tasks
 python3 -m deletebench.cli run-suite --tasks-root tasks --agent reference --output-dir results/reference
 python3 -m deletebench.cli run-suite --tasks-root tasks --agent command --agent-command "python3 scripts/run_model.py" --output-dir results/my-model
 python3 -m deletebench.cli summarize --results-dir results/my-model
 ```

 ## Running tests

 ```bash
 python3 -m unittest discover -s tests -p 'test_*.py'
 ```

 ## Current limitations

 This repo is usable now, but still v0.

 Current limitations include:

 - no built-in OpenAI/Anthropic/etc. model adapters
 - task pack is microrepo-based, not yet historical real-repo deletions
 - trust model is local and trusted-only
 - residue checking is still relatively lightweight

 ## Recommended next extensions

 Good next steps if you want a stronger benchmark:

 - add model-specific adapters under `deletebench/models/`
 - add result export or leaderboard scripts
 - add a second task source based on reconstructed real deletion PRs
 - add stronger residue analysis using AST or ecosystem-specific tooling
 - add sandboxing for untrusted task packs
