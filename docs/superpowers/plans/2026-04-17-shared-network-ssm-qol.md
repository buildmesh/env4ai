# Shared Network And SSM Quality-Of-Life Implementation Plan

> **For agentic workers:** Implement this plan task-by-task, keeping changes small, test-backed, and sequential. Preserve existing safety checks around shared network destruction and avoid unrelated refactors.

**Goal:** Improve deploy-time and interactive ergonomics for shared AWS workstation infrastructure by treating `Env4aiNetworkStack` as long-lived shared infrastructure, removing unnecessary public networking for `ACCESS_MODE=ssm`, hardening the launcher SSM convenience helper, and exposing shared-network teardown in interactive mode.

**Architecture:** `Env4aiNetworkStack` remains the owner of shared networking and all reusable SSM infrastructure. `WorkstationStack` continues to consume shared resources conditionally based on `ACCESS_MODE`, but environment deploy orchestration should only create the shared network stack when it is missing, not redeploy it every time. Public connectivity is tied to SSH-capable modes only. Interactive shared-network teardown must reuse the existing shared-network destroy orchestration and guardrails.

**Tech Stack:** Python 3, AWS CDK, boto3, shell scripting for instance init, unittest, Make, Markdown documentation in `docs/superpowers/plans`

---

## Goals

- Treat `Env4aiNetworkStack` as shared static infrastructure.
- Automatically deploy `Env4aiNetworkStack` on environment deploy only when it does not already exist.
- Stop routine environment deploys from modifying `Env4aiNetworkStack` when it already exists.
- Ensure environments using `ACCESS_MODE=ssh` no longer fail because shared network deploy/update is triggered unnecessarily.
- Remove public IP and Elastic IP usage from `ACCESS_MODE=ssm` environments.
- Preserve current public connectivity behavior for `ACCESS_MODE=ssh` and `ACCESS_MODE=both`.
- Harden the launcher-generated `ssm` helper script without changing its core purpose.
- Add an interactive action to destroy `Env4aiNetworkStack` by reusing the existing destroy flow.

## Non-Goals

- Do not implement the Docker/repository layout refactor discussed separately.
- Do not redesign `Env4aiNetworkStack` ownership or move SSM resources out of it.
- Do not change the meaning of `ACCESS_MODE` values.
- Do not remove or weaken existing safety checks that block shared-network destroy when environment stacks still exist.

## Current Architecture Summary

Relevant files and responsibilities:

- `aws/base_stack/workstation/env4ai_network_stack.py`
  - Defines `Env4aiNetworkStack`
  - Already creates the shared VPC, IGW, SSM endpoint subnet, SSM interface endpoints, SSM SGs, and shared EC2 SSM role/profile
  - Already behaves independently of `ACCESS_MODE`

- `aws/base_stack/workstation/workstation_stack.py`
  - Defines `WorkstationStack`
  - Accepts `access_mode`
  - Conditionally attaches SSH and/or SSM resources
  - Currently always maps public IP on launch

- `aws/workstation_core/orchestration.py`
  - Contains deploy orchestration
  - Currently unconditionally deploys `Env4aiNetworkStack` before environment deploy
  - Contains shared-network destroy logic and CloudFormation stack discovery helpers

- `aws/workstation_core/interactive_workstation.py`
  - Shared interactive menu, action parsing, gating, and dispatch logic

- `aws/scripts/interactive_workstation.py`
  - Interactive CLI entrypoint

- `aws/scripts/destroy_shared_network.py`
  - Existing CLI wrapper around shared-network destroy orchestration

- `aws/launcher/init/deps.sh`
  - Installs packages and writes the launcher-local `ssm` helper script

## Verified Current State

The implementing agent should assume the following are true unless the repository changes before implementation begins:

- `Env4aiNetworkStack` already always includes SSM resources and is not the source of the access-mode bug.
- The current bug comes from deploy orchestration redeploying the shared network stack on every environment deploy.
- Shared-network destroy orchestration already exists and already blocks destroy when environment stacks still exist.
- `ACCESS_MODE=ssm` still inherits public-IP/EIP behavior because networking/orchestration are not yet fully gated by access mode.
- The launcher `ssm` helper currently works, but is brittle because it hardcodes region and lacks robust argument/error handling.

## Assumptions

- All environments deploy into one shared VPC and one shared IGW owned by `Env4aiNetworkStack`.
- `Env4aiNetworkStack` is intended to be long-lived shared infrastructure, not per-environment mutable infrastructure.
- Shared network existence should be determined from CloudFormation state in the active account/region.
- For the launcher helper, instance `Name` tags are correct and only one matching running instance exists.
- Existing unit-test suites should be updated or extended instead of replaced.
- The external deploy and interactive command interfaces should remain familiar unless explicitly changed by this plan.

## Constraints

- Use reviewable diffs only.
- Use `apply_patch` for manual file edits.
- Avoid unrelated refactors.
- Add or update unit tests for all Python logic changes.
- Preserve backward-compatible behavior except where this plan explicitly changes behavior.
- Keep documentation aligned with actual deploy/runtime behavior.

## Key Decisions

### Decision 1: Shared network deployment is existence-based

Environment deploy must:

- deploy `Env4aiNetworkStack` automatically when missing
- skip shared-network deploy when it already exists

It must not update the shared network stack every time an environment is deployed.

### Decision 2: Shared network existence is checked through CloudFormation

Determine whether `Env4aiNetworkStack` exists by using CloudFormation stack discovery in the active account/region, reusing orchestration patterns already present in the repo.

### Decision 3: Public connectivity is tied to SSH-enabled access modes

Use one consistent policy across CDK stack behavior and deploy orchestration:

- `ssh`: public IP and EIP required
- `ssm`: public IP and EIP not required
- `both`: public IP and EIP required

### Decision 4: Interactive shared-network teardown reuses existing orchestration

Do not duplicate destroy logic in the interactive layer. The interactive menu should dispatch into the existing shared-network destroy path and preserve the current preflight guardrails.

### Decision 5: Launcher SSM helper remains a shell helper, just safer

Keep the user-facing model of a local `ssm` script that connects by environment name. Improve robustness through argument validation, safe shell behavior, dynamic region resolution, and clearer failure modes.

## Desired End State

After implementation:

- Environment deploys automatically create `Env4aiNetworkStack` only on first use.
- Existing shared-network stacks are left untouched during routine environment deploys.
- `ACCESS_MODE=ssh` deploys no longer fail due to unnecessary attempts to modify the shared network stack.
- `ACCESS_MODE=ssm` environments:
  - do not receive a public IP
  - do not allocate or use an EIP
  - do not require SSH ingress or key pair behavior
  - still receive the shared SSM SG/profile resources needed for Session Manager
- `ACCESS_MODE=ssh` and `ACCESS_MODE=both` preserve current public connectivity behavior.
- Interactive mode includes a confirmed action to destroy `Env4aiNetworkStack`.
- The launcher `ssm` helper validates usage, resolves region dynamically, and fails clearly when lookup is invalid.

## Interfaces And Affected Files

### Shared network deploy gating

- Modify: `aws/workstation_core/orchestration.py`
- Test: `aws/workstation_core/tests/unit/test_deploy_orchestration.py`
- Test: `aws/base_stack/tests/unit/test_deploy_workstation.py`

Potentially relevant:

- `aws/base_stack/tests/unit/test_app.py`
- `aws/base_stack/tests/unit/test_check.py`

Expected interface behavior:

- Existing deploy entrypoints keep their current CLI/API surface.
- Internal orchestration may add a helper such as `shared_network_stack_exists(...) -> bool`, or equivalent internal logic.
- `deploy_shared_network_stack(...)` can remain as the implementation for first-use creation.

### Public IP / EIP access-mode gating

- Modify: `aws/base_stack/workstation/workstation_stack.py`
- Modify: `aws/workstation_core/orchestration.py`
- Test: `aws/base_stack/tests/unit/test_workstation_stack.py`
- Test: `aws/workstation_core/tests/unit/test_deploy_orchestration.py`
- Test: `aws/base_stack/tests/unit/test_deploy_workstation.py`

Potentially relevant:

- `aws/scripts/check_instance.py`
- tests that currently assume EIP data is always present

Expected interface behavior:

- `WorkstationStack` derives whether public addressing is needed from `access_mode`.
- Deploy orchestration derives the same policy when deciding whether to allocate/use EIP.
- Post-deploy flows remain valid for all access modes.

### Launcher SSM convenience helper

- Modify: `aws/launcher/init/deps.sh`

Potential testing:

- add a lightweight structural test if the repo already has an appropriate pattern
- otherwise validate via targeted inspection and any existing shell/script checks

Expected interface behavior:

- generated script remains named `ssm`
- script still accepts an environment/instance name argument
- script still starts an SSM session for the matching running instance

### Interactive shared-network destroy

- Modify: `aws/workstation_core/interactive_workstation.py`
- Modify: `aws/scripts/interactive_workstation.py` only if needed by interface changes
- Test: `aws/base_stack/tests/unit/test_interactive_workstation.py`
- Test: `aws/workstation_core/tests/unit/test_interactive_workstation.py`

Potentially relevant:

- `aws/scripts/destroy_shared_network.py`
- `aws/base_stack/tests/unit/test_destroy_shared_network.py`
- `aws/workstation_core/tests/unit/test_shared_network_destroy.py`

Expected interface behavior:

- interactive menu includes a distinct action to destroy the shared network
- action requires explicit confirmation
- actual destroy continues to be blocked by backend guardrails if environment stacks still exist

## Architecture Changes

### A. Shared network deploy flow

Current problem:

- `run_deploy_lifecycle(...)` unconditionally deploys `Env4aiNetworkStack` before each environment deploy.

Target behavior:

- resolve profile/region as today
- check whether `Env4aiNetworkStack` exists
- if missing, deploy it
- if present, skip shared-network deploy
- continue with environment deploy

Important details:

- existence means stack is present and not terminally deleted
- reuse shared network stack name from configuration rather than repeating string literals
- reuse existing CloudFormation discovery patterns where possible

### B. Public addressing and Elastic IP policy

Current problem:

- `WorkstationStack` always maps public IP on launch
- deploy orchestration always allocates/uses EIP

Target policy matrix:

- `ssh`
  - public IP: yes
  - EIP: yes
  - SSH SG/key behavior: yes
  - SSM SG/profile: no

- `ssm`
  - public IP: no
  - EIP: no
  - SSH SG/key behavior: no
  - SSM SG/profile: yes

- `both`
  - public IP: yes
  - EIP: yes
  - SSH SG/key behavior: yes
  - SSM SG/profile: yes

Implementation guidance:

- derive one internal flag representing whether public connectivity is required
- apply that flag consistently in both CDK stack construction and deploy orchestration
- avoid partial fixes where only one of public IP or EIP is disabled

### C. Interactive shared-network destroy

Current problem:

- shared-network destroy exists, but is not exposed in the interactive menu

Target behavior:

- menu includes a shared-network destroy action
- action is available regardless of selected environment deployment state
- explicit confirmation is required
- actual execution reuses the existing destroy path and backend guardrails

Implementation guidance:

- update menu rendering
- update action parsing
- update action availability
- update action dispatch
- route through the existing runner abstraction to `../scripts/destroy_shared_network.py`, or reuse the same orchestration path through an equivalent existing wrapper

### D. Launcher SSM helper hardening

Current problem:

- helper script works but is fragile
- region is hardcoded
- missing-argument and empty-result cases are not handled robustly

Target behavior:

- validate required argument presence
- use safe shell options
- resolve region from AWS CLI/runtime context rather than hardcoding
- fail clearly if no valid instance ID is returned
- `exec` the final `aws ssm start-session` command

Do not overcomplicate:

- no need to support multiple matches
- no need for advanced selection logic
- no need to redesign launcher bootstrapping around a different scripting system

## Testing Strategy

### Shared network deploy gating

Add or update tests to verify:

- when the shared network stack does not exist, deploy lifecycle calls `deploy_shared_network_stack(...)`
- when the shared network stack already exists, deploy lifecycle does not call `deploy_shared_network_stack(...)`
- deploy continues normally after either branch

Likely test files:

- `aws/workstation_core/tests/unit/test_deploy_orchestration.py`
- `aws/base_stack/tests/unit/test_deploy_workstation.py`

### Public IP / EIP gating

Add or update tests to verify:

- `ACCESS_MODE=ssm` creates a workstation subnet without public IP mapping
- `ACCESS_MODE=ssh` still maps public IP
- `ACCESS_MODE=both` still maps public IP
- deploy orchestration skips EIP allocation for `ACCESS_MODE=ssm`
- deploy orchestration still allocates EIP for `ssh` and `both`

Likely test files:

- `aws/base_stack/tests/unit/test_workstation_stack.py`
- `aws/workstation_core/tests/unit/test_deploy_orchestration.py`

### Interactive shared-network destroy

Add or update tests to verify:

- menu parsing accepts the new action
- availability includes the new action in the intended states
- dispatch requires confirmation
- dispatch invokes the shared-network destroy command path
- cancellation behaves correctly

Likely test files:

- `aws/base_stack/tests/unit/test_interactive_workstation.py`
- `aws/workstation_core/tests/unit/test_interactive_workstation.py`

### Launcher helper

If feasible, add a lightweight structural assertion for the generated script behavior, such as:

- argument validation exists
- region is not hardcoded
- script validates resolved instance ID before starting session

If no suitable shell-script testing pattern exists in the repo, validate by code review and targeted runtime inspection.

## Step-By-Step Task Breakdown

### Task 1: Refactor shared network deploy orchestration

**Files:**

- Modify: `aws/workstation_core/orchestration.py`
- Test: `aws/workstation_core/tests/unit/test_deploy_orchestration.py`
- Test: `aws/base_stack/tests/unit/test_deploy_workstation.py`

- [ ] Add or adapt an orchestration helper that determines whether `Env4aiNetworkStack` exists in the current account/region.
- [ ] Reuse shared network stack naming from `get_shared_network_config()` or equivalent shared config rather than hardcoding the stack name.
- [ ] Update `run_deploy_lifecycle(...)` so it deploys the shared network only when missing.
- [ ] Preserve current region/profile resolution and error behavior.
- [ ] Add focused tests covering both branches: shared network absent and shared network present.
- [ ] Re-run deploy orchestration tests and confirm they no longer assume unconditional shared-network deploy.

**Acceptance criteria:**

- First environment deploy in a clean account/region auto-creates `Env4aiNetworkStack`.
- Subsequent environment deploys skip shared-network deploy if the stack already exists.

### Task 2: Gate public IP and EIP behavior by access mode

**Files:**

- Modify: `aws/base_stack/workstation/workstation_stack.py`
- Modify: `aws/workstation_core/orchestration.py`
- Test: `aws/base_stack/tests/unit/test_workstation_stack.py`
- Test: `aws/workstation_core/tests/unit/test_deploy_orchestration.py`
- Test: `aws/base_stack/tests/unit/test_deploy_workstation.py`

- [ ] Derive a single internal policy flag representing whether public connectivity is required based on `access_mode`.
- [ ] Use that flag in `WorkstationStack` to control subnet public-IP mapping.
- [ ] Preserve SSH SG ingress and key behavior only for SSH-capable modes.
- [ ] Preserve shared SSM SG/profile attachment for `ssm` and `both`.
- [ ] Update deploy orchestration to skip EIP allocation/usage for `ACCESS_MODE=ssm`.
- [ ] Ensure post-deploy flows tolerate absent EIP information in SSM-only mode.
- [ ] Add/update tests covering `ssh`, `ssm`, and `both` behavior consistently.

**Acceptance criteria:**

- `ACCESS_MODE=ssm` deploys do not map public IP and do not allocate EIP.
- `ACCESS_MODE=ssh` and `ACCESS_MODE=both` preserve current public connectivity behavior.

### Task 3: Harden the launcher SSM convenience helper

**Files:**

- Modify: `aws/launcher/init/deps.sh`
- Test: add a lightweight structural test only if a suitable repo pattern exists

- [ ] Review the heredoc-generated helper in `aws/launcher/init/deps.sh`.
- [ ] Update the helper to validate required argument presence.
- [ ] Replace the hardcoded region with dynamic AWS region resolution.
- [ ] Add validation for empty or invalid resolved instance ID values.
- [ ] Use safer shell behavior and `exec` the final `aws ssm start-session` command.
- [ ] Preserve installation path, ownership, and user-facing helper name unless a minimal safety improvement requires a small adjustment.
- [ ] Add structural validation if feasible; otherwise document the change clearly and verify by inspection.

**Acceptance criteria:**

- Running the helper without an argument fails clearly.
- The helper no longer hardcodes region.
- The helper fails clearly when instance lookup returns no valid instance ID.
- The helper starts the session directly for a valid environment name.

### Task 4: Add shared-network teardown to interactive mode

**Files:**

- Modify: `aws/workstation_core/interactive_workstation.py`
- Modify: `aws/scripts/interactive_workstation.py` only if needed
- Test: `aws/base_stack/tests/unit/test_interactive_workstation.py`
- Test: `aws/workstation_core/tests/unit/test_interactive_workstation.py`

- [ ] Add a new interactive action for destroying the shared network.
- [ ] Update menu text and action parsing consistently.
- [ ] Decide and implement availability behavior.
  Recommended behavior: always visible and available in the menu, with actual execution still guarded by backend shared-network checks.
- [ ] Require explicit confirmation before invoking shared-network destroy.
- [ ] Dispatch through the existing runner abstraction to the existing shared-network destroy script/path.
- [ ] Add tests for parsing, availability, confirmation, cancellation, and command invocation.
- [ ] Confirm existing shared-network destroy tests still pass unchanged, unless a small interface update requires test maintenance.

**Acceptance criteria:**

- Interactive mode exposes a confirmed action to destroy `Env4aiNetworkStack`.
- The action reuses the existing safe destroy path.
- Destruction remains blocked when environment stacks still exist.

## Recommended Implementation Order

Implement in this order:

1. Shared network deploy gating
2. Public IP / EIP gating by access mode
3. Launcher helper hardening
4. Interactive shared-network destroy

Reasoning:

- Tasks 1 and 2 affect deploy/runtime infrastructure semantics and should be stabilized first.
- Task 3 is isolated and low risk.
- Task 4 is mostly UI/action wiring on top of existing orchestration.

## Risks And Mitigations

### Risk: incorrect shared-network existence detection

If existence detection is wrong, deploy may skip required shared-network creation or attempt unnecessary updates.

Mitigation:

- reuse existing CloudFormation stack discovery patterns already used by shared-network destroy logic
- add tests for both missing and existing stack states

### Risk: inconsistent SSM-only networking behavior

If only EIP or only public IP is disabled, behavior may remain inconsistent.

Mitigation:

- derive one public-connectivity policy flag
- apply it consistently in both CDK and orchestration layers

### Risk: interactive menu regression

Adding an action can break parsing, numbering, or tests.

Mitigation:

- update rendering, parsing, availability, and tests together
- keep action naming explicit and stable

### Risk: overengineering the launcher helper

Making the helper too clever may reduce reliability.

Mitigation:

- keep the helper minimal
- improve only shell safety, validation, and region handling

## Validation Checklist

Before the work is considered complete, verify:

- deploy orchestration unit tests pass
- workstation stack unit tests pass
- interactive workstation unit tests pass
- shared-network destroy tests still pass
- README is updated to reflect the new behavior

Behavior validation:

- first environment deploy in a clean account/region auto-creates `Env4aiNetworkStack`
- later environment deploys skip shared-network deploy if it already exists
- `ACCESS_MODE=ssm` deploys do not request public IP or EIP
- `ACCESS_MODE=ssh` and `ACCESS_MODE=both` preserve current connectivity behavior
- interactive mode exposes shared-network destroy and uses the existing safe destroy path

## Documentation Updates

Update `README.md` to reflect:

- environment deploy auto-creates `Env4aiNetworkStack` only when it is missing
- routine environment deploys do not redeploy the shared network stack every time
- `ACCESS_MODE=ssm` avoids public IP / Elastic IP usage
- interactive mode includes a shared-network destroy action

Keep README wording aligned with implemented behavior. Remove any wording that implies shared-network deploy is unconditional on every environment deploy.

## Deliverables

- updated orchestration logic for shared-network existence-based deploy behavior
- updated workstation stack and deploy orchestration behavior for `ACCESS_MODE=ssm` networking
- hardened launcher-generated `ssm` helper
- interactive shared-network destroy menu action
- updated unit tests
- updated README documentation

## Summary Of Intent

The core architectural principle is that `Env4aiNetworkStack` is shared, long-lived infrastructure and should not be continuously reconciled as part of each environment deploy. Environments should depend on its existence, not mutate it by default. Separately, SSM-only environments should behave like private SSM-managed instances rather than public SSH hosts. The interactive experience should expose the already-existing shared-network teardown flow, and the launcher SSM helper should be made safer without changing its purpose.
