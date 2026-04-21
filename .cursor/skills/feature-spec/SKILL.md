---
name: feature-spec
description: Spec-Driven Development entrypoint for BelemConverse. Determines the work type (roadmap phase, ad-hoc feature, bugfix, spike), assigns a semver-like phase version, creates the branch, runs an iterative clarify-loop interview, and writes a spec directory under specs/ containing spec.md, plan.md, tasks.md, and validation.md. Trigger when the user says "feature spec", "next phase", "start the next feature", "new spec", or invokes /feature-spec.
---

# Feature Spec (BelemConverse SDD)

This skill drives a **standard Spec-Driven Development (SDD)** workflow for the
BelemConverse monorepo (FastAPI + `belem_converse` Python lib + Flutter
frontend + data pipeline). It is opinionated: it always separates **WHAT/WHY**
(`spec.md`) from **HOW** (`plan.md`), enforces a **constitution gate**, and
emits a **TDD-ordered `tasks.md`** with `[P]` parallel markers.

Prerequisites the skill expects to find under `specs/`:
- `specs/constitution.md` — invariant tenets every spec must pass.
- `specs/mission.md` — product mission used to keep specs aligned.
- `specs/tech-stack.md` — observed stack, used to scope plans correctly.
- `specs/roadmap.md` — phased roadmap; may be empty for ad-hoc work.

If any prerequisite is missing, **stop and tell the user** before running
the workflow. Do not silently bootstrap them.

## Workflow

### 1. Determine the work type

Ask the user (single `AskQuestion` call) which kind of work this is:

- **roadmap** — implements the next incomplete phase from `specs/roadmap.md`.
- **feature** — ad-hoc product feature not yet on the roadmap.
- **bugfix** — corrects defective behavior in an existing feature/phase.
- **spike** — time-boxed investigation; produces findings, not necessarily code.

This choice drives versioning, tasks discipline, and validation defaults.

### 2. Compute the phase version

Versions are **semver-like** (`phase-N.M.K`), with **no kebab name** in the branch.

- **roadmap**: `phase-N` where `N` is the next free top-level integer (read
  existing `phase-*` branches via `git branch --list 'phase-*'` and existing
  `specs/phase-*` directories; take `max(N) + 1`).
- **feature**: sub-feature of an existing phase → `phase-N.M` (next free `M`
  under the parent `N`). If no parent phase is implied, treat as a new top-level
  phase and use `phase-N`.
- **bugfix** / **spike**: `phase-N.M.K` off the most recently relevant
  `phase-N.M` (next free `K`).

**Auto-bump on collision.** If the computed version already exists as a branch
or `specs/` directory, increment the rightmost component until it is free.
Always confirm the final version to the user before continuing.

### 3. Create the branch

```bash
git checkout -b phase-N[.M[.K]]
```

The branch name carries no slug. Slugs live in the spec directory name only.

### 4. Read the gates

Read `specs/constitution.md`, `specs/mission.md`, `specs/tech-stack.md`, and
`specs/roadmap.md` before drafting anything. The constitution is binding: if
any tenet would be violated, the skill must surface it and ask the user to
either narrow scope or document an explicit exception inside `spec.md`.

### 5. Initial interview — BEFORE writing any files

Use `AskQuestion` with exactly **3 questions in one call**:

| Header | Question focus |
|--------|----------------|
| **Scope** | What the feature does for the user; surfaces touched (api / lib / pipeline / frontend); fields/data shape if applicable |
| **Decisions** | Product-level choices only (visibility, defaults, UX pattern, copy tone). Tech decisions belong in the plan. |
| **Context** | Constraints, related specs/ADRs in `docs/spec/`, open questions |

Do **not** write any files until the user has answered all three.

### 6. Draft `spec.md` (WHAT/WHY only)

Create the spec directory: `specs/phase-N[.M[.K]]-<short-slug>/` where
`<short-slug>` is a 1–3 word kebab summary of the feature (used only for human
scanning; the branch stays slug-less).

`spec.md` template:

```markdown
# phase-N.M.K — <Title>

**Status**: draft  ·  **Type**: roadmap | feature | bugfix | spike
**Branch**: phase-N.M.K  ·  **Spec dir**: specs/phase-N.M.K-<slug>/

## Goal
One paragraph: the user-visible outcome and why it matters.

## User stories (prioritized)
- **P1** — As a <role>, I want <capability> so that <benefit>.
- **P2** — …
- **P3** — …

## Acceptance criteria
For each story, Given/When/Then triples:
- **Given** <precondition>, **When** <action>, **Then** <observable outcome>.

## Success metrics
Measurable signals (latency budget, retrieval@k, test coverage delta, etc.).

## Out of scope
What this spec deliberately does not cover.

## Open questions
- [NEEDS CLARIFICATION: <question>]
```

WHAT/WHY only. Do **not** name files, classes, libraries, or endpoints here.
If a required answer is unknown, insert a `[NEEDS CLARIFICATION: ...]` marker
inline and continue drafting.

### 7. Clarify loop

If `spec.md` contains any `[NEEDS CLARIFICATION: ...]` markers, run a
follow-up `AskQuestion` round (one call, batched) covering all open markers.
Patch the spec with the answers, remove the markers, and re-check. Repeat
until none remain. Cap at 3 clarify rounds; if markers persist, escalate to
the user as a blocker rather than guessing.

### 8. Constitution check

Re-read `specs/constitution.md` and verify the spec does not violate any
tenet. If a violation is unavoidable, add a **Constitution exception** section
to `spec.md` documenting the tenet, the reason, and the mitigation. Get the
user's explicit go-ahead before continuing.

### 9. Draft `plan.md` (HOW)

```markdown
# Plan — phase-N.M.K

## Tech context
Per surface touched, list the concrete tech and patterns used.
- **api/** (FastAPI): routes, schemas, dependencies, contract impact on docs/spec/05-openapi.yaml.
- **belem_converse/** (lib): modules, classes, data structures, retriever/ranking impact.
- **data/** (pipeline): ingestion paths, JSONL/Chroma impact, sample-data smoke approach.
- **frontend/** (Flutter): pages, widgets, state, BLoC/provider usage, routing.

## Architecture sketch
Diagram or bullet flow showing how requests/data move end-to-end for this feature.

## Data model deltas
New/changed fields, JSONL/Chroma schema impact, migrations.

## API contract deltas
New/changed endpoints, request/response shapes; reference `docs/spec/05-openapi.yaml`.

## Risks and trade-offs
Known risks, performance implications, fallback behavior.

## Constitution alignment
One line per relevant tenet confirming compliance, or pointing to the exception in spec.md.
```

### 10. Draft `tasks.md` (strict TDD, [P] parallel markers, dependency arrows)

```markdown
# Tasks — phase-N.M.K

Conventions:
- IDs: T01, T02, …
- `[P]` = parallelizable with any other `[P]` task at the same level.
- `→ depends on T0X` lists hard dependencies.
- TDD discipline: every implementation task is preceded by a failing-test task on the same line of code.

## API (api/)
- T01 [P] Write failing test: <pytest path> asserts <behavior>.
- T02 Implement <change> to make T01 pass. → depends on T01

## Library (belem_converse/)
- T03 [P] Write failing test: <pytest path>.
- T04 Implement <change>. → depends on T03

## Data pipeline
- T05 [P] Write failing test or smoke fixture.
- T06 Implement pipeline change. → depends on T05

## Frontend (frontend/)
- T07 Manual checklist or widget test (see validation.md).

## Wiring & docs
- T0N Update `docs/spec/` if contract changed; update README if user-facing.
```

Rules:
1. No implementation task may appear before its corresponding failing-test task.
2. Tasks the constitution requires (e.g., type-checking, error handling) must appear explicitly.
3. Group by surface; mark cross-surface dependencies via `→ depends on`.

### 11. Draft `validation.md`

`pytest` is the **only required automated gate** (per project decision).
Everything else is **recommended** and listed for whichever surfaces the
feature touches.

```markdown
# Validation — phase-N.M.K

## Required gates
- `pytest` passes from the repo root with no new skips. New tests cover all P1 acceptance criteria.

## Recommended (per surface touched)
- `ruff check .` and `mypy belem_converse api` if Python code changed.
- `cd frontend && flutter test` and `flutter analyze` if frontend changed.
- Pipeline smoke run on a sample CSV via `POST /api/ingest/csv` if the pipeline changed.
- OpenAPI diff against `docs/spec/05-openapi.yaml` if API contract changed.

## Manual walkthrough
Step-by-step user actions, expected outcomes, and screenshots/log captures
required for each P1 story.

## Definition of done
- All P1 acceptance criteria verified by automated tests.
- Required gate passes.
- spec.md has no `[NEEDS CLARIFICATION]` markers.
- Constitution check is clean (or has a recorded exception).
- Branch is rebased on `main` with no merge conflicts.
- PR opened following the commit/PR convention below.
```

### 12. Commit and PR convention (binding)

- **Commit prefix**: every commit on the branch starts with `phase-N.M.K:`
  (e.g., `phase-2.1: add tour planner cache`).
- **PR title**: `phase-N.M.K — <summary>`.
- **PR body**: must link to the spec dir (e.g.,
  `Spec: specs/phase-2.1-osm-cache/`) and summarize the validation evidence.

The skill does not create commits or PRs by itself; it records the convention
in `spec.md` and `validation.md` so the implementing session enforces it.

## Idempotency / resume

If `git checkout -b phase-N.M.K` fails because the branch exists, **auto-bump**
to the next free version (see step 2) and inform the user. Same for
`specs/phase-N.M.K-*/` directories. Never overwrite an existing spec dir.

## Tool note

Use the `AskQuestion` tool for all interview steps. Always batch related
questions into a single call. Never write files before required answers
have been received.
