# BelemConverse Roadmap

The `feature-spec` skill consumes this file when the work type is **roadmap**.
Each phase below is a top-level unit of work that produces a `phase-N` branch
and a `specs/phase-N-<short-slug>/` spec directory. Sub-features become
`phase-N.M`; bugfixes/spikes off a sub-feature become `phase-N.M.K`.

## How to read this file

- A phase is **available** when all its checklist items are `[ ]`.
- A phase is **in progress** when at least one item is `[x]` and at least
  one is `[ ]`.
- A phase is **done** when all items are `[x]`. The skill skips done phases.

The "next phase" is the first phase from top to bottom whose items are all
`[ ]`.

## Phase template (copy when adding a phase)

```markdown
## phase-N — <Title>

**Goal**: one-sentence outcome.
**Surfaces**: api | belem_converse | data | frontend | docs (multi).

- [ ] Item 1
- [ ] Item 2
- [ ] Item 3
```

## Phases

<!--
No phases authored yet. Add phases above following the template.
Until at least one phase exists, the `feature-spec` skill should be invoked
with work type "feature", "bugfix", or "spike" rather than "roadmap".
-->
