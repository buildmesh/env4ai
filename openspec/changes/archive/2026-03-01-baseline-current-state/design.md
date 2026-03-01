## Context

The change introduces a durable baseline of the project’s current state so contributors can quickly understand architecture, infrastructure, and developer workflows without reverse engineering the repository. At present, project information is distributed across `README.md`, `aws/` docs, scripts, and OpenSpec artifacts, with no single canonical baseline view. The baseline should be easy to update, clearly scoped, and usable by both new and existing contributors.

## Goals / Non-Goals

**Goals:**
- Define a structured documentation surface that captures current-state architecture, module responsibilities, runtime/deployment topology, and local development workflows.
- Standardize baseline sections and quality criteria so updates remain consistent over time.
- Make baseline docs actionable for onboarding, planning, and impact analysis of future changes.

**Non-Goals:**
- Redesigning architecture or changing runtime behavior.
- Introducing new product features, APIs, or infrastructure.
- Replacing detailed module-level docs where those already exist.

## Decisions

1. Create a dedicated capability spec (`project-baseline-documentation`) that defines required baseline coverage and validation criteria.
Reasoning: The baseline is a repeatable, requirements-level concern, not a one-off document. Encoding requirements in a spec makes maintenance explicit.
Alternative considered: keeping baseline guidance only in prose inside `README.md`. Rejected because it is hard to validate and easy to drift.

2. Keep baseline documentation additive and non-invasive to runtime code.
Reasoning: The proposal scope is documentation-first; coupling this change to code refactors would blur intent and increase review risk.
Alternative considered: pairing baseline docs with opportunistic code cleanup. Rejected to preserve narrow, auditable scope.

3. Document ownership and update triggers in tasks.
Reasoning: Baseline documents become stale without explicit update points (for example, architecture or deployment changes). Tasks should include maintenance triggers and acceptance checks.
Alternative considered: no explicit maintenance plan. Rejected due to high drift risk.

## Risks / Trade-offs

- [Risk] Baseline content may become stale as the project evolves. -> Mitigation: define update triggers and acceptance checks in tasks; tie updates to change workflows.
- [Risk] Overly broad scope could produce verbose, low-signal documents. -> Mitigation: enforce a fixed section structure and concise summary-first writing.
- [Risk] Duplication with existing docs can create conflicting guidance. -> Mitigation: use baseline docs as index-and-summary layers with references to source-of-truth files.

## Migration Plan

1. Create proposal, spec, design, and task artifacts for the capability.
2. Implement baseline documentation files and link from `README.md` as needed.
3. Validate coverage against spec requirements before completion.
4. Future changes update baseline docs when architecture/workflow assumptions change.

Rollback strategy: if baseline documentation introduces confusion, revert doc changes and restore previous references without affecting runtime systems.

## Open Questions

- Should baseline documentation live as a single document or a small docs set (for example, architecture + operations + developer workflow)?
- What minimum acceptance checks should be enforced in CI versus manual review?
