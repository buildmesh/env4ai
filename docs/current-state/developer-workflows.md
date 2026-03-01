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

## CDK App Workflows

From [`aws/gastown/README.md`](../../aws/gastown/README.md):

- `uv sync`: install/update dependencies for CDK app.
- `uv run cdk ls|synth|deploy|diff`: CDK lifecycle commands.

## Post-Deploy Access Workflow

After deployment:

1. Run helper script (typically via `make gastown` output flow):
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

## Contributor Checklist For New Changes

Before opening a change:

1. Confirm which command entrypoint is affected (`Makefile`, CDK app, helper scripts, docs).
2. Run relevant tests (`make test`) for modified infrastructure logic.
3. Update `docs/current-state/` when workflow, topology, or ownership assumptions change.
