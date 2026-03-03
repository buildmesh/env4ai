# Developer Workflows Baseline

## Prerequisites

Authoritative prerequisites are documented in [`README.md`](../../README.md):

- Docker + Docker Compose
- GNU Make
- AWS account access
- AWS CLI profile configured with region in `~/.aws/config`
- EC2 key pair and local key file setup
- `secrets/aws_acct` file for default account resolution

## Core Commands

From [`Makefile`](../../Makefile):

- `make` or `make aws`: open shell in AWS tooling container.
- `make gastown`: deploy/start workstation infrastructure (`ACTION=START`) through shared deploy orchestration.
- `make gastown ACTION=STOP`: destroy stack and stop workstation resources through shared stop orchestration.
- `make test`: run unit tests in `aws/gastown/tests/unit`.
- `AMI_LOAD=<tag> make gastown`: deploy from exact AMI name `gastown_<tag>`.
- `AMI_LIST=1 make gastown`: list environment AMIs (`gastown_*`) without deploy.
- `AMI_LIST=1 AMI_PICK=1 make gastown`: list, select, and deploy from chosen AMI.
- `AMI_SAVE=1 AMI_TAG=<tag> make gastown ACTION=STOP`: save AMI `gastown_<tag>` before destroy, and abort destroy if save fails.

## AMI Option Behavior And Rollback

Operational behavior (entrypoint [`aws/scripts/deploy_workstation.py`](../../aws/scripts/deploy_workstation.py), shared implementation in [`aws/workstation_core/ami_lifecycle.py`](../../aws/workstation_core/ami_lifecycle.py) and [`aws/workstation_core/orchestration.py`](../../aws/workstation_core/orchestration.py)):

- `AMI_LOAD=<tag>` resolves `<environment>_<tag>` and deploys with the matched AMI ID.
- `AMI_LIST=1` prints matching AMIs and exits without deploying.
- `AMI_LIST=1 AMI_PICK=1` prints AMIs, prompts for selection, then deploys with the selected AMI ID.
- `AMI_PICK=1` without `AMI_LIST=1` fails fast.
- `AMI_LOAD` and `AMI_LIST` together fail fast.

Rollback guidance for disabling AMI options and returning to default base-image deploy behavior:

- For one command, run plain deploy with no AMI variables:
  - `make gastown`
- If AMI variables are exported in your shell, clear them first:
  - `unset AMI_LOAD AMI_LIST AMI_PICK`
- If automation sets AMI variables, remove them (or set `AMI_LIST=0` / `AMI_PICK=0`) and run standard deploy:
  - `make gastown`
- Expected rollback result: deploy proceeds without AMI override context and uses the default Ubuntu image path.

Validation and failure behavior:
- `AMI_PICK=1` without `AMI_LIST=1` fails with a validation error.
- `AMI_LOAD` together with `AMI_LIST=1` fails with a validation error.
- Missing `AMI_LOAD` target name (`<environment>_<tag>`) fails before CDK deploy.

Save-on-stop workflow status:
- `AMI_SAVE=1` with `AMI_TAG=<tag>` saves `<environment>_<tag>` from the running workstation before destroy.
- Destroy is gated by AMI creation/availability; failures abort destroy.
- Without `AMI_SAVE`, stop behavior remains direct destroy.

## New Environment Onboarding From Shared Core

Use these steps to add a new environment with minimal copy/paste and no hardcoded naming drift.

1. Define one canonical spec in `aws/<environment>/environment_config.py`:
   - Export `ENVIRONMENT_SPEC` as an `EnvironmentSpec`.
   - Keep environment-specific knobs only: `environment_key`, `display_name`, `bootstrap_files`, `default_ami_selector`, `instance_type`, `volume_size`, `spot_price`.
2. Use derived names from the spec instead of hardcoded strings:
   - `ENVIRONMENT_SPEC.stack_name`
   - `ENVIRONMENT_SPEC.spot_fleet_logical_id`
   - AMI name format `<environment_key>_<tag>`
3. Wire the app/stack to accept `environment_spec`:
   - App passes `ENVIRONMENT_SPEC` into the stack constructor.
   - Stack uses `environment_spec.construct_id(...)` and shared helpers from `workstation_core.cdk_helpers`.
4. Wire `Makefile` start/stop entrypoints through shared scripts:
   - Start: `cd /home/user/<environment> && uv run ../scripts/deploy_workstation.py --environment <environment> --stack-dir /home/user/<environment> --stack-name <DisplayName>WorkstationStack`
   - Stop: `cd /home/user/<environment> && uv run ../scripts/stop_workstation.py --environment <environment> --stack-dir /home/user/<environment> --stack-name <DisplayName>WorkstationStack`
5. Validate required command behaviors for the new environment:
   - AMI list: `AMI_LIST=1 make <environment>`
   - AMI load: `AMI_LOAD=20260301 make <environment>`
   - AMI pick: `AMI_LIST=1 AMI_PICK=1 make <environment>`
   - AMI save-on-stop: `AMI_SAVE=1 AMI_TAG=20260302 make <environment> ACTION=STOP`
   - Legacy/default behavior: `make <environment>` and `make <environment> ACTION=STOP`

IAM requirements for onboarding/testing:
- `ec2:DescribeImages` is required for AMI list/load preflight and lookup.
- Save-on-stop requires IAM permissions for Spot Fleet instance resolution and AMI create/wait operations used by `aws/workstation_core/ami_lifecycle.py`.

Rollback to legacy behavior:
1. Clear AMI lifecycle variables: `unset AMI_LOAD AMI_LIST AMI_PICK AMI_SAVE AMI_TAG`.
2. Run default deploy/stop commands with no AMI flags.

## CDK App Workflows

From [`aws/gastown/README.md`](../../aws/gastown/README.md):

- `uv sync`: install/update dependencies for CDK app.
- `uv run cdk ls|synth|deploy|diff`: CDK lifecycle commands.

## Post-Deploy Access Workflow

After deployment:

1. Run helper script (invoked automatically by `make gastown` deploy flow):
   - [`aws/scripts/check_instance.py`](../../aws/scripts/check_instance.py)
2. Use printed SSH config snippet.
3. Connect with `ssh gastown-workstation` once SSH config is updated.

## Test Workflow

- Unit tests are under [`aws/gastown/tests/unit`](../../aws/gastown/tests/unit).
- Standard invocation: `make test`.
- Tests cover CDK app configuration logic and stack behavior contracts.

## Troubleshooting Entry Points

- Region/account resolution errors: inspect [`aws/gastown/app.py`](../../aws/gastown/app.py) and mounted secrets/config.
- Instance discovery/SSH issues: inspect [`aws/scripts/check_instance.py`](../../aws/scripts/check_instance.py).
- Stack-level provisioning behavior: inspect [`aws/gastown/gastown_workstation/gastown_workstation_stack.py`](../../aws/gastown/gastown_workstation/gastown_workstation_stack.py).
- AMI load/list/pick behavior and errors: inspect shared modules [`aws/workstation_core/ami_lifecycle.py`](../../aws/workstation_core/ami_lifecycle.py) and [`aws/workstation_core/orchestration.py`](../../aws/workstation_core/orchestration.py) first, then wrapper [`aws/scripts/deploy_workstation.py`](../../aws/scripts/deploy_workstation.py).

## Rollback To Legacy Flow

When AMI lifecycle options cause issues, return to the baseline workflow:

1. Remove AMI environment variables (`unset AMI_LOAD AMI_LIST AMI_PICK AMI_SAVE AMI_TAG`).
2. Deploy with no AMI flags (`make gastown`).
3. Stop with no AMI flags (`make gastown ACTION=STOP`).

## Contributor Checklist For New Changes

Before opening a change:

1. Confirm which command entrypoint is affected (`Makefile`, CDK app, helper scripts, docs).
2. Run relevant tests for changed modules:
   - `make test` for `aws/gastown` unit coverage.
   - `cd aws/workstation_core && uv run python -m unittest discover -s tests/unit -v` for shared-core contracts/helpers.
   - Environment-specific stack unit tests if the environment has its own test suite.
3. Update `docs/current-state/` when workflow, topology, or ownership assumptions change.
