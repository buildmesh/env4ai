## Context

Today each `make <environment>` deployment launches a Spot instance from a fixed Ubuntu Jammy AMI and applies bootstrap `userData` every time. `make <environment> ACTION=STOP` destroys the stack without preserving the current machine image. This change adds an optional image lifecycle around that flow: save instance state to an environment-scoped AMI at stop-time, and load or list saved AMIs at deploy-time.

Key constraints:
- Existing users must keep current behavior when no new AMI arguments are passed.
- AMI names should be deterministic and human-readable: `<environment>_<tag>`.
- The deploy path must support both explicit tag input and discoverability (list available AMIs).

## Goals / Non-Goals

**Goals:**
- Add a stop-time option to create an AMI from the current instance before `cdk destroy`.
- Add deploy-time options to load a saved AMI by tag or list/select available AMIs for an environment.
- Keep deploy/stop command ergonomics centered on `make <environment>`.
- Make AMI selection deterministic and fail fast when an expected AMI does not exist.
- Preserve default bootstrap-based behavior when AMI options are omitted.

**Non-Goals:**
- Automatic AMI pruning/retention policies.
- Cross-environment AMI sharing rules or replication across regions/accounts.
- Replacing current bootstrap logic for default deployments.
- Building a long-running catalog service for AMI metadata.

## Decisions

1. Add explicit Make arguments for save/load/list behavior
- Decision: Extend existing `make <environment>` interface with optional variables (for example `AMI_TAG`, `AMI_LOAD_TAG`, `AMI_LIST`) rather than changing positional targets.
- Rationale: Keeps compatibility with current target naming and minimizes disruption.
- Alternatives considered:
  - Add new top-level Make targets (`save-ami`, `deploy-from-ami`): rejected due to fragmented UX and duplicated environment parsing.
  - Add an interactive shell wrapper: rejected due to automation friction in CI and scripts.

2. Use EC2 image APIs directly in orchestration scripts
- Decision: Use `aws ec2 create-image`, `describe-images`, and wait/poll operations in the lifecycle scripts that currently invoke CDK deploy/destroy.
- Rationale: This is the smallest change to existing architecture and keeps AMI operations explicit and auditable.
- Alternatives considered:
  - Model AMI creation in CDK resources: rejected because AMI snapshotting here is an operational action tied to teardown flow, not persistent desired state.
  - Use SSM automation documents: rejected as additional operational complexity for an initial feature.

3. AMI naming and lookup strategy is exact-match by `<environment>_<tag>`
- Decision: Save flow writes AMI Name exactly as `<environment>_<tag>`. Load flow resolves the most recent matching available image by exact Name and optional owner filter.
- Rationale: Predictable naming enables deterministic reuse and simple shell-driven lookup.
- Alternatives considered:
  - Prefix-only search with partial tag matching: rejected because ambiguous matches increase risk of booting wrong state.
  - Storing mapping in a local state file: rejected due to drift and portability issues.

4. Deploy path branches on AMI source and controls bootstrap behavior
- Decision: When `AMI_LOAD_TAG` is set (or selected from list), pass selected AMI ID into CDK context/parameters for launch template/Spot request and skip bootstrap `userData` by default.
- Rationale: Saved AMI already contains machine state; rerunning full bootstrap undermines the value and may cause config drift.
- Alternatives considered:
  - Always run bootstrap even for loaded AMI: rejected due to longer startup and risk of destructive re-provisioning.
  - Never allow bootstrap override: rejected because some teams may still want post-boot patch steps.

5. List UX supports both non-interactive output and optional choose step
- Decision: `AMI_LIST=1` prints environment-scoped AMIs (`<environment>_*`) sorted by creation date. If combined with load intent and no explicit tag, allow select-first/choose behavior in script-friendly form.
- Rationale: Users asked to see available AMIs and pick one; output-first design stays automation-friendly.
- Alternatives considered:
  - Purely interactive picker: rejected because it blocks non-TTY automation.
  - List-only without selection handoff: rejected because it adds manual copy/paste friction.

## Risks / Trade-offs

- [Saving AMI takes time and may delay teardown] -> Mitigation: print clear progress and support timeout/fail-fast behavior before destroy.
- [AMI creation fails and leaves stack running] -> Mitigation: treat save as transactional precondition only when flag is provided; on failure, abort destroy with actionable error.
- [Wrong AMI selected when names collide] -> Mitigation: enforce exact `<environment>_<tag>` lookup and optionally filter owners/account.
- [Skipping bootstrap may miss required runtime updates] -> Mitigation: document behavior and allow an explicit override flag to run limited bootstrap steps if needed.
- [Additional AWS API calls increase permissions surface] -> Mitigation: document required IAM actions and validate permissions early.

## Migration Plan

1. Introduce new optional Make/environment variables and wire them into existing deploy/stop orchestration scripts.
2. Implement stop-time AMI create flow:
   - Resolve running instance ID for the environment stack.
   - Create AMI with name `<environment>_<tag>`.
   - Wait for AMI availability (or fail with timeout).
   - Continue to `cdk destroy` only on success.
3. Implement deploy-time AMI list/load flow:
   - For list mode, print available AMIs matching `<environment>_*`.
   - For load mode, resolve AMI ID by `<environment>_<tag>` and pass it to CDK.
   - Branch bootstrap behavior for loaded AMI path.
4. Update docs (`README.md`) with examples:
   - Save on stop.
   - Deploy from tag.
   - List available AMIs.
5. Rollback strategy:
   - Disable AMI flags and use existing default deploy/stop paths.
   - Revert orchestration changes if needed; no persistent schema/data migration is required.

## Open Questions

- Should the save workflow default to reboot/no-reboot during AMI creation, or expose that as an advanced option?
  - Decision: Default to reboot for filesystem consistency
- When listing AMIs, should we include only `available` state or include pending/failed with annotations?
  - Decision: Include pending/failed but mark non-`available` state AMIs as such so the user knows it is in progress (or failed and needs to be retried) but can't actually use it until it is `available`
- For "pick one" UX, do we prefer explicit `AMI_LOAD_TAG=<tag>` after listing, or add a dedicated `AMI_PICK=latest|prompt` option?
  - Decision: For best UX, allow the user to pick from the list, then proceed with deploy using the selected AMI, to avoid making the user having to issue another command
- Should we include extra AMI tags (environment, creator, timestamp) beyond the Name for governance and cleanup tooling?
  - Decision: Show only the Name, and make sure to list only AMIs for the environment (e.g. for 'make gastown AMI_LIST=1', show only AMIs with a Name like "gastown_*"
