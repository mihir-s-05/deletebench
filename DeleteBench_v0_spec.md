# DeleteBench v0 — Spec, Data Generation, and Reference Implementation

## DeleteBench: Benchmarking Subtractive Engineering in LLM Coding Agents

### Purpose

DeleteBench evaluates whether a coding model or agent can **remove a feature from a real codebase cleanly** rather than merely hiding it, stubbing it, or leaving residue behind.

Most coding benchmarks overweight additive behavior: write a function, add a feature, make a test pass. DeleteBench instead measures whether a model can:

- identify the true blast radius of a feature
- remove it across code, tests, config, docs, flags, schemas, and UX
- preserve adjacent behavior
- leave the repository in a coherent, simplified state

---

## 1. Core task definition

Each task consists of:

- a repository snapshot
- a natural-language removal request
- optional constraints
- a hidden evaluation bundle
- a scoring function

The model receives the repo and the task prompt. It produces a patch or edited repo state.

### Canonical task prompt

```text
Remove feature X from this repository.

Requirements:
- Remove the feature completely.
- Do not leave placeholder stubs, fake deprecation notices, or "not implemented" paths unless explicitly requested.
- Remove or update tests that only exist for the deleted feature.
- Keep unrelated functionality working.
- Clean up dead code, comments, docs, config, and flags related to the feature where appropriate.
```

---

## 2. Success criteria

A good solution satisfies all of the following:

### A. Removal completeness
The feature is genuinely gone across all relevant surfaces.

### B. Regression safety
Unrelated features still work.

### C. Residue cleanup
No stale tests, comments, docs, flags, config, or dead branches remain.

### D. Coherent repo state
Build, typecheck, lint, and surviving tests pass.

### E. Focused changes
The diff is not an unrelated rewrite.

---

## 3. Benchmark modes

DeleteBench should report two separate tracks.

### Mode 1: Pure Deletion
The task is structured so the feature can be removed with deletions and minimal local edits.

This measures whether the model can precisely excise code without inventing scaffolding.

### Mode 2: Deletion-with-Repair
The task requires refactoring surviving code after the feature is removed.

This measures whether the model understands shared abstractions and can simplify the system after deletion.

These should be scored separately because they test different skills.

---

## 4. Task categories

A balanced v0 benchmark should include several deletion patterns.

### 4.1 UI-only removal
Examples:
- remove a settings toggle
- remove a page or modal
- remove a menu item

### 4.2 Full-stack feature removal
Examples:
- remove notifications
- remove CSV export
- remove team invites

### 4.3 Feature-flag sunset
Examples:
- remove a feature behind `ENABLE_X`
- delete both flag plumbing and dead branch

### 4.4 API or CLI decommission
Examples:
- remove a deprecated endpoint
- remove an obsolete CLI command

### 4.5 Shared abstraction pruning
Examples:
- remove one auth method but keep the others
- remove one plugin or provider while preserving the abstraction

### 4.6 Legacy-path cleanup
Examples:
- remove a fallback parser
- remove legacy migration compatibility logic
- remove a caching layer and simplify the call graph

---

## 5. How to get data or generate it

This is the most important practical question. DeleteBench should not depend on exact gold diffs. It should instead build tasks whose outcomes can be evaluated with hidden checks.

There are three good data sources.

### 5.1 Source A: Reconstructed real deletion PRs

Start from open-source repositories that have real feature-removal commits or PRs.

#### Process
1. Find a deletion PR or commit.
2. Identify the parent commit immediately before the deletion.
3. Reconstruct the task starting from that pre-deletion snapshot.
4. Write a natural-language prompt that describes the intended removal.
5. Build hidden checks based on the feature that was removed and the neighboring functionality that should survive.
6. Store the original human patch only as a reference artifact, not as the grading target.

#### Advantages
- realistic dependency structure
- realistic messiness
- authentic blast radius

#### Risks
- sometimes the human patch includes unrelated cleanup
- some removals depend on product context that is not obvious from code
- hidden checks take real labor to build

#### Good use
Use reconstructed real deletions for medium and hard tasks.

---

### 5.2 Source B: Synthetic injected features

Take a clean benchmark repo and deliberately inject a removable feature, then later benchmark its deletion.

#### Process
1. Start with a baseline repo.
2. Add a feature with multiple dependency surfaces:
   - UI entrypoint
   - config or flag
   - test coverage
   - docs or copy
   - API or background logic
3. Save the baseline as the task repo.
4. Save the injected version as the starting point for the deletion task.
5. Build hidden checks from the injection manifest.

#### Advantages
- full control over difficulty
- easy to create precise hidden checks
- easy to create blast-radius labels
- easier to balance task categories

#### Risks
- can become too synthetic if overused
- may reward benchmark-specific heuristics

#### Good use
Use synthetic injections for early-stage benchmark development and pathology-focused tasks.

---

### 5.3 Source C: Purpose-built microrepos

Create small apps whose only job is to test specific deletion failure modes.

Examples:
- one repo for feature-flag cleanup
- one repo for shared abstraction pruning
- one repo for UI removal with analytics residue
- one repo for backend worker + UI coupling

#### Advantages
- fastest way to bootstrap v0
- very easy to create hidden checks
- great for failure analysis

#### Risks
- less realistic than historical repos
- easier for agents to overfit to patterns

#### Good use
Use microrepos for the initial 10–20 tasks.

---

### 5.4 Recommended v0 dataset mix

A strong v0 mix is:

- 40% purpose-built microrepos
- 35% synthetic injected features
- 25% reconstructed real deletion PRs

This yields enough control to get reliable evaluation while still preserving realism.

---

### 5.5 How to find real deletion candidates

Search for commits or PRs containing terms such as:

- remove feature
- deprecate and remove
- drop support for
- delete legacy path
- sunset feature flag
- remove endpoint
- remove provider
- remove notifications
- remove CLI command

Then manually filter for tasks with these properties:

- the feature boundary is legible
- the feature has at least two dependency surfaces
- adjacent functionality still exists
- the repo can still be built or tested
- the deletion is nontrivial but not hopelessly entangled

Avoid tasks where:
- the entire repository is archived or broken
- the deletion depends mostly on external infrastructure
- the removal is just deleting one isolated file

---

### 5.6 How to generate synthetic tasks programmatically

For scalable data generation, define a **feature injection schema**.

Example conceptual schema:

```json
{
  "feature_name": "email_notifications",
  "surfaces": {
    "ui": ["settings page", "toggle", "help text"],
    "backend": ["send pipeline", "queue worker", "template renderer"],
    "config": ["EMAIL_NOTIFICATIONS_ENABLED"],
    "tests": ["settings test", "worker test", "integration test"],
    "docs": ["notifications section"]
  },
  "shared_dependencies": {
    "must_preserve": ["in_app_notifications", "generic_email_sender"]
  },
  "removal_requirements": [
    "remove feature entirely",
    "do not leave deprecation notice",
    "preserve in-app notifications"
  ]
}
```

Then write generators that:
- insert the feature into a target repo
- emit the starting repo snapshot
- emit hidden checks derived from the injection manifest
- emit allowed alternative outcomes
- emit banned residue patterns

This makes it possible to scale the benchmark without writing every task by hand.

---

### 5.7 Difficulty knobs for task generation

To make easier or harder tasks, vary:

- **surface count**: how many places the feature touches
- **indirection depth**: direct calls vs layered abstractions
- **shared utility overlap**: standalone feature vs shared infrastructure
- **test visibility**: obvious public tests vs hidden probes only
- **naming clarity**: easy names vs generic helpers
- **flag complexity**: one flag vs multi-branch flag plumbing
- **docs/config coupling**: code only vs code + docs + config + analytics

A simple difficulty rubric:

#### Easy
- 2–3 surfaces
- mostly local names
- minimal shared abstractions

#### Medium
- 4–6 surfaces
- some indirection
- some shared code that must survive

#### Hard
- multiple services or layers
- misleading names
- cross-cutting config/tests/docs/analytics
- shared abstraction requires repair

---

## 6. What the benchmark should store per task

Each task should have a machine-readable spec.

### Suggested task manifest

```json
{
  "task_id": "deletebench_023",
  "repo_name": "kanban-lite",
  "entry_commit": "abc123",
  "mode": "deletion_with_repair",
  "category": "full_stack_feature_removal",
  "difficulty": "medium",
  "instruction": "Remove the notification center feature completely. Do not leave deprecation messages or placeholder implementations. Keep all other settings functionality working.",
  "public_metadata": {
    "languages": ["TypeScript"],
    "frameworks": ["React", "Node"],
    "approx_loc": 18000
  },
  "hidden_eval": {
    "commands": {
      "install": "npm ci",
      "build": "npm run build",
      "test": "npm test",
      "lint": "npm run lint",
      "typecheck": "npm run typecheck"
    },
    "removal_probes": [
      "notifications route absent",
      "notification worker absent",
      "notification config flag absent"
    ],
    "regression_probes": [
      "settings page still works",
      "comments still work"
    ],
    "residue_checks": [
      "no notification docs section",
      "no notification analytics event",
      "no placeholder stubs"
    ]
  }
}
```

The model sees everything except the hidden evaluation details.

---

## 7. How to implement the benchmark in code

The key principle is:

**grade the final repository state, not similarity to a reference patch.**

A good implementation has six layers.

### 7.1 Task packaging layer

Responsibilities:
- store repos or repo snapshots
- restore clean starting states
- expose the task prompt
- define environment requirements

Typical layout:

```text
deletebench/
  tasks/
    deletebench_001/
      repo/
      task.json
      public_prompt.txt
      hidden_eval/
        eval.py
        residue_rules.yaml
        probes/
    deletebench_002/
      ...
```

---

### 7.2 Agent runner layer

Responsibilities:
- clone or copy the starting repo into a temp workspace
- present the task prompt to the model or agent
- let the model edit files
- collect the final patch and logs
- enforce time and tool limits if desired

The runner should not care how the agent works internally. It only needs a standard interface.

### Standard runner interface
The runner should accept:
- task path
- model identifier
- max wall-clock time
- max tool calls, if applicable
- output directory

And produce:
- final repo state
- patch or diff
- stdout/stderr logs
- metadata such as runtime and files changed

---

### 7.3 Evaluation harness layer

Responsibilities:
- run build/test/typecheck/lint
- run hidden behavior probes
- run residue checks
- compute sub-scores
- assign failure labels

This should operate on the final repo state only.

---

### 7.4 Probe layer

Each task should define probes of multiple types.

#### Behavior probes
Examples:
- route no longer exists
- CLI command removed
- API endpoint removed
- worker no longer runs
- feature no longer visible in UI

#### Regression probes
Examples:
- neighboring features still work
- shared utility still functions
- surviving providers still pass

#### Residue probes
Examples:
- banned strings absent
- config keys absent
- stale docs absent
- removed tests updated or deleted
- no placeholder stubs

A probe returns structured results such as:

```json
{
  "probe_id": "notifications_route_absent",
  "status": "fail",
  "message": "The /notifications route is still registered in router.ts"
}
```

---

### 7.5 Scoring layer

Recommended v0 weighting:

- Removal completeness: 35
- Regression safety: 25
- Residue cleanup: 20
- Diff hygiene: 10
- Spec compliance: 10

The scoring code should support:
- partial credit
- task-level fail tags
- per-category aggregation
- benchmark-level summaries

---

### 7.6 Reporting layer

For each run, store:
- total score
- component scores
- pass/fail of each hidden probe
- failure taxonomy labels
- runtime
- diff stats
- raw logs

The most useful benchmark output is not just one score. It is the combination of:
- overall score
- category breakdown
- failure pattern distribution

---

## 8. A practical reference implementation design

A simple Python implementation is enough for v0.

### 8.1 Suggested repository structure

```text
deletebench/
  README.md
  pyproject.toml
  deletebench/
    __init__.py
    runner.py
    evaluator.py
    scoring.py
    reporting.py
    models/
      base.py
    tasks/
      loader.py
      schemas.py
    utils/
      git_utils.py
      subprocess_utils.py
      residue.py
      diff_utils.py
  tasks/
    deletebench_001/
      repo/
      task.json
      public_prompt.txt
      hidden_eval/
        eval.py
        residue_rules.yaml
    deletebench_002/
      ...
  results/
```

---

### 8.2 Minimal Python abstractions

#### Task
```python
class Task:
    task_id: str
    repo_path: str
    prompt: str
    manifest: dict
```

#### AgentResult
```python
class AgentResult:
    final_repo_path: str
    diff_text: str
    runtime_seconds: float
    files_changed: list[str]
    logs_path: str
```

#### ProbeResult
```python
class ProbeResult:
    probe_id: str
    passed: bool
    category: str
    message: str
    weight: float
```

#### EvaluationResult
```python
class EvaluationResult:
    task_id: str
    total_score: float
    sub_scores: dict
    probes: list[ProbeResult]
    failure_tags: list[str]
```

---

### 8.3 Example runner flow

1. Load task manifest.
2. Copy task repo into a temporary working directory.
3. Invoke the target model or agent on the prompt.
4. Wait for completion or timeout.
5. Capture final repo state and diff.
6. Run the evaluator.
7. Save structured results.

Pseudo-flow:

```python
task = load_task(task_id)
workspace = prepare_workspace(task.repo_path)
agent_result = run_agent(model, task.prompt, workspace)
evaluation = evaluate_task(task, agent_result.final_repo_path, agent_result)
save_result(evaluation)
```

---

### 8.4 Example evaluator flow

The evaluator should run these steps:

1. sanity-check repo exists
2. run install command if needed
3. run build/lint/typecheck/test commands
4. run custom hidden probes
5. run residue checks
6. compute diff hygiene metrics
7. assign scores and failure labels

Pseudo-flow:

```python
def evaluate_task(task, repo_path, agent_result):
    probe_results = []
    probe_results += run_build_checks(task, repo_path)
    probe_results += run_behavior_probes(task, repo_path)
    probe_results += run_regression_probes(task, repo_path)
    probe_results += run_residue_probes(task, repo_path)
    probe_results += run_diff_hygiene_checks(task, agent_result.diff_text)
    return score_probe_results(task, probe_results)
```

---

## 9. How to write hidden evaluation checks

Hidden checks are what make the benchmark real.

A good task should mix three kinds of checks.

### 9.1 Build and test checks
Examples:
- `npm ci`
- `npm run build`
- `npm run test`
- `pytest`
- `cargo test`

These catch broad breakage.

### 9.2 Custom behavior probes
Write task-specific scripts that assert:
- the deleted feature is actually gone
- specific adjacent functionality still works

Examples:
- send an HTTP request to a removed endpoint and expect 404
- render a settings page and assert a toggle is absent
- run CLI help and assert a subcommand is absent
- assert other commands still work

### 9.3 Residue checks
Static or semantic checks for leftover artifacts.

Examples:
- banned strings not present in source or docs
- removed config key absent
- removed analytics event absent
- no `throw new Error("Not implemented")`
- no added `TODO remove later`

Static checks are useful, but do not rely on them alone. Combine them with behavior checks.

---

## 10. Residue checking implementation details

Residue scoring is one of the benchmark’s main contributions.

### 10.1 Things to penalize
- placeholder stubs
- deprecation banners added instead of deletion
- dead tests left behind
- skipped or xfailed tests added to dodge failures
- stale comments mentioning removed behavior
- stale docs
- stale config flags
- unreachable branches that only served the deleted feature
- unused imports or symbols introduced by partial deletion

### 10.2 How to implement
Use a mix of:
- regex rules
- AST-based checks where practical
- grep-like banned token checks
- unused symbol tooling
- framework-specific route or command introspection

Example residue rules file:

```yaml
banned_patterns:
  - 'Not implemented'
  - 'feature has been deprecated'
  - 'TODO.*remove'
  - 'deprecated.*notifications'
forbidden_symbols:
  - 'ENABLE_NOTIFICATIONS'
  - 'NotificationCenter'
forbidden_paths:
  - 'docs/notifications.md'
```

This should be task-specific, not global only.

---

## 11. Diff hygiene scoring

Diff hygiene should matter, but not dominate.

### Reward
- focused diff
- few unrelated files touched
- mostly deletions or localized edits
- no giant speculative refactor

### Penalize
- huge unrelated changes
- broad rewrites outside feature blast radius
- scaffolding added to simulate removal

Possible metrics:
- number of touched files
- added lines vs deleted lines
- ratio of unrelated files touched
- diff entropy by directory

This is supportive signal, not the main criterion.

---

## 12. Failure taxonomy

Every failed run should be labeled with one or more failure tags.

Recommended taxonomy:

- `surface_only_deletion`
- `backend_only_deletion`
- `stub_substitution`
- `deprecation_instead_of_deletion`
- `dead_residue`
- `under_deletion`
- `over_deletion`
- `shared_abstraction_breakage`
- `unrelated_rewrite`
- `spec_violation`

This is important for research usefulness. It tells you whether a model fails because it is timid, sloppy, destructive, or instruction-insensitive.

---

## 13. Anti-gaming protections

DeleteBench is easy to game if implemented badly.

### Protect against:
1. deleting tests instead of deleting the feature
2. skipping tests with xfail or skip
3. hiding UI while backend remains alive
4. replacing logic with no-op stubs
5. removing neighboring behavior to make probes pass
6. overfitting to grep-only residue checks

### Required protections:
- hidden regression probes
- hidden removal probes
- explicit penalties for skipped tests and stubs
- behavior-based checks, not only string checks
- diff hygiene metrics to catch brute-force rewrites

---

## 14. Recommended v0 build plan

### Phase 1: Tiny but diagnostic
Build 12 tasks.

Suggested mix:
- 3 UI-only
- 3 full-stack
- 2 feature-flag
- 2 shared abstraction
- 2 legacy cleanup

### Phase 2: Reference runner and evaluator
Implement:
- task loader
- workspace manager
- agent runner interface
- evaluation harness
- scoring and report generation

### Phase 3: Expand to 30–40 tasks
Add:
- synthetic injected tasks
- a few real deletion reconstructions
- category-balanced score reporting

### Phase 4: Publish benchmark
Release:
- task manifests
- runner
- evaluator
- baseline model results
- error analysis using failure taxonomy

---

## 15. Example task sheet

### Task: Remove email notifications

#### Prompt
Remove the email notifications feature completely. Do not leave deprecation messages, placeholder implementations, or dead tests. Preserve in-app notifications and all other settings functionality.

#### Feature surfaces
- settings toggle
- backend send pipeline
- email template renderer
- queue worker
- feature flag
- help docs
- analytics event

#### Must preserve
- in-app notifications
- generic email infrastructure used elsewhere
- settings page

#### Hidden checks
- email notifications route absent
- queue worker code path absent
- feature flag absent
- docs section absent
- analytics event absent
- in-app notifications still work
- settings page still renders
- no placeholder stubs

---

## 16. Suggested baseline metrics to publish

For every model or agent, report:

- overall score
- pure deletion score
- deletion-with-repair score
- category breakdown
- failure taxonomy distribution
- average runtime
- average files changed
- average additions/deletions ratio

This gives a much more useful picture than a single leaderboard number.

---

## 17. What makes DeleteBench scientifically interesting

DeleteBench measures a neglected but important capability:

**Can a model identify what is essential, what is contingent, and what can be safely removed?**

That requires:
- codebase understanding
- dependency tracing
- restraint
- cleanup judgment
- abstraction repair

In other words, it is much closer to maintenance engineering than “write function from docstring.”

---

## 18. Strong recommendation for v0

Keep the benchmark small at first, but make the hidden checks excellent.

A 12-task benchmark with:
- precise task construction
- strong behavior probes
- good residue checks
- informative failure taxonomy

is much more valuable than a 200-task benchmark with shallow grading.

---

## 19. Optional future extensions

Future versions can add:
- multi-commit deletion tasks
- tool-budgeted tracks
- human-in-the-loop tracks
- cross-language tasks
- infra/config-only deletions
- DB migration rollback or schema cleanup tasks
- benchmark suites for specific ecosystems such as React, Django, Rust CLI, or monorepos

---

## 20. Summary

DeleteBench should be built around three ideas:

1. **Outcome-based grading** rather than gold diff matching
2. **Mixed data sources**: microrepos, synthetic injections, and reconstructed real deletions
3. **Behavior + residue + regression** evaluation, not just build success

That is the combination that will make it both practical to implement and meaningful as a benchmark.

