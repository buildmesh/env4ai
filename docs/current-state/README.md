# Project Current-State Baseline

## Purpose

This baseline captures the current implementation state of the repository so contributors can quickly orient, plan changes, and verify impact areas without reverse-engineering code.

## Time Of Capture

- Captured on: 2026-02-28
- Scope: Repository state in this branch at capture time

## Baseline Structure

This baseline is maintained as a small linked documentation set:

1. [Architecture](./architecture.md)
2. [Infrastructure And Deployment](./infrastructure.md)
3. [Developer Workflows](./developer-workflows.md)

Reason for this structure: a single large document would mix concerns and be harder to keep accurate; separate focused docs are easier to update and review.

## Start Here (Onboarding Path)

1. Read [Developer Workflows](./developer-workflows.md) to set up tooling and run key commands.
2. Read [Architecture](./architecture.md) to understand repository boundaries and responsibilities.
3. Read [Infrastructure And Deployment](./infrastructure.md) to understand AWS deployment resources and operational entry points.

## Change Impact Analysis Path

When planning or reviewing a change:

1. Locate affected area in [Architecture](./architecture.md).
2. Trace deployment/runtime impact in [Infrastructure And Deployment](./infrastructure.md).
3. Validate command/test impact in [Developer Workflows](./developer-workflows.md).
4. Align requirements and task updates in [`openspec/changes/`](../../openspec/changes).

## Requirement Coverage Matrix

| Requirement | Coverage location |
| --- | --- |
| Scope coverage (architecture/code/infra/workflows) | [Architecture](./architecture.md), [Infrastructure](./infrastructure.md), [Developer Workflows](./developer-workflows.md) |
| Navigability and source references | All baseline docs include source file references |
| Time-of-capture and assumptions | This file: "Time Of Capture" and "Assumptions / Unknowns" |
| Maintenance triggers | This file: "Maintenance Triggers" |
| Onboarding usability | This file: "Start Here" and [Developer Workflows](./developer-workflows.md) |

## Assumptions / Unknowns

- Local developer machine prerequisites are inferred from `README.md`, `Makefile`, `docker-compose.yaml`, and `aws/Dockerfile`; no additional unpublished setup scripts were found.
- Runtime cost and security posture depend on AWS account defaults and local profile settings; those account-specific controls are out of repository scope.
- No `docs/PLANNING.md` file exists in this repository at capture time.

## Maintenance Triggers

Update this baseline when any of the following changes occur:

1. Top-level repository structure or module ownership changes (for example, new primary environment directory, renamed major paths).
2. AWS/CDK stack topology changes (networking, security group rules, compute type, spot fleet behavior).
3. Local workflow entrypoints change (`Makefile`, Docker Compose service contract, setup prerequisites, test command paths).
4. Contributor-facing setup/deployment instructions in root `README.md` change materially.
5. OpenSpec workflow conventions or artifact paths change in ways that affect planning/apply flow.

## Maintenance Process

1. Update the relevant baseline doc(s) in `docs/current-state/`.
2. Update capture date and assumptions in this file when facts change.
3. Ensure every new assertion includes a source file path reference.
4. Include baseline updates in the same change that introduced the underlying behavior change.
