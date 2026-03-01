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
- `make gastown`: deploy/start workstation infrastructure (`ACTION=START`).
- `make gastown ACTION=STOP`: destroy stack and stop workstation resources.
- `make test`: run unit tests in `aws/gastown/tests/unit`.
- `AMI_LOAD=<tag> make gastown`: deploy from exact AMI name `gastown_<tag>`.
- `AMI_LIST=1 make gastown`: list environment AMIs (`gastown_*`) without deploy.
- `AMI_LIST=1 AMI_PICK=1 make gastown`: list, select, and deploy from chosen AMI.

## AMI Option Behavior And Rollback

Operational behavior (implemented in [`aws/scripts/deploy_workstation.py`](../../aws/scripts/deploy_workstation.py)):

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
- No `AMI_SAVE`/`AMI_TAG` variable is currently implemented in `Makefile`.
- Operators must manually create and wait for an AMI before running `make gastown ACTION=STOP` when preservation is required.

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
- AMI load/list/pick behavior and errors: inspect [`aws/scripts/deploy_workstation.py`](../../aws/scripts/deploy_workstation.py).

## Rollback To Legacy Flow

When AMI lifecycle options cause issues, return to the baseline workflow:

1. Remove AMI environment variables (`unset AMI_LOAD AMI_LIST AMI_PICK`).
2. Deploy with no AMI flags (`make gastown`).
3. Stop with no AMI flags (`make gastown ACTION=STOP`).

## Contributor Checklist For New Changes

Before opening a change:

1. Confirm which command entrypoint is affected (`Makefile`, CDK app, helper scripts, docs).
2. Run relevant tests (`make test`) for modified infrastructure logic.
3. Update `docs/current-state/` when workflow, topology, or ownership assumptions change.
