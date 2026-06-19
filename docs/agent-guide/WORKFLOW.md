# Agent Workflow

## Before a Task

1. Read the required guide documents from `README.md`.
2. Inspect the repository, current implementation, tests, and working-tree state.
3. Identify affected requirements, security invariants, and accepted decisions.
4. Separate verified facts from assumptions and open questions.
5. Propose an ADR before making any unaccepted high-impact technical decision.
6. Define focused acceptance criteria and a verification approach.

High-impact decisions include the core stack, database/queue technology, authentication design, public interfaces, data retention, deployment topology, real connectors, LLM/tool execution, and any external side effect.

## During a Task

- Keep changes scoped to the requested outcome and existing architectural boundaries.
- Preserve correlation, idempotency, policy, mode, audit, and failure behavior end to end.
- Add tests proportional to the risk and include negative/security cases where relevant.
- Never weaken a guardrail merely to make a test or demonstration pass.
- Do not overwrite unrelated user changes.
- Record newly verified reusable knowledge in `KNOWLEDGE.md`.

## Before Completion

1. Run the narrowest relevant checks, then broader checks when shared behavior changed.
2. Confirm no secret, credential, personal data, or unsafe default was introduced.
3. Verify dashboard and audit visibility for changed lifecycle behavior.
4. Update the owning guide documents and decision status when behavior changed.
5. Report implemented behavior, verification performed, and any residual risk or unrun check.

## Documentation Classification

- `Confirmed requirement`: explicitly fixed by the owner; belongs in `PROJECT_BRIEF.md`.
- `Accepted decision`: approved or implemented architectural choice; belongs in `DECISIONS.md`.
- `Proposed`: recommended but not approved or implemented.
- `Assumption`: temporary premise needed to make progress; state validation conditions.
- `Open question`: unresolved product or technical choice that materially affects delivery.
- `Verified knowledge`: observed repository or runtime fact; belongs in `KNOWLEDGE.md` with evidence.
