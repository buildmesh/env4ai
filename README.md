# EC2 AI Dev Environments

This repository helps developers spin up reproducible EC2 workstations for AI tooling.

Current environment:
- `gastown`: [Gas Town](https://github.com/steveyegge/gastown), preconfigured with dependencies so it is usable out of the box.
- `builder`: Android-focused builder workstation profile.

## Prerequisites

- Docker + Docker Compose
- GNU Make
- AWS account access
- AWS CLI configured with a profile in `~/.aws/config` that includes a `region` value (`~/.aws` is mounted into the container)

## One-Time Setup

1. In **AWS Management Console**, create a customer-managed IAM policy using:

   `aws/iam/gastown/deployer-policy.json`

2. Attach that policy to the IAM user used by your local AWS `default` profile.

3. Create an EC2 key pair in **AWS Management Console > EC2 > Network & Security > Key Pairs**:
   - Name: `aws_key`
   - Download the private key and place it at:

     `~/.ssh/aws_key.pem`

4. Create the account-id secret file (default source for AWS account):

   ```bash
   mkdir -p secrets
   echo "<YOUR_AWS_ACCOUNT_ID>" > secrets/aws_acct
   ```

   By default this is mounted as Docker secret `aws_acct` at `/run/secrets/aws_acct`. You can override account resolution using options/environment variables (for example `CDK_DEFAULT_ACCOUNT`).

## Usage

### Interactive-first workflow (default)

```bash
make
```

`make` now opens the interactive workstation lifecycle menu (`make interactive`).
The environment picker is auto-discovered from valid environment modules under
`aws/` (directories with `environment_config.py` that expose `ENVIRONMENT_SPEC`).

Interactive menu actions:
- Deploy with default AMI
- Deploy with AMI list + pick
- Save current state as AMI
- Destroy stack
- Destroy stack + save AMI first
- Refresh status
- Switch environment
- Quit

Note: AWS creates `aws-ec2-spot-fleet-tagging-role` automatically the first time
Spot Fleet needs it.

### Advanced / compatibility commands

Existing explicit targets remain available for automation and backwards compatibility:

```bash
# Deploy/start one environment directly
make gastown
make builder

# Destroy one environment directly
make gastown ACTION=STOP
make builder ACTION=STOP
```

Optional AMI lifecycle controls remain available for direct target usage:

```bash
# Deploy using an exact AMI name: gastown_20260301
AMI_LOAD=20260301 make gastown

# Deploy from saved AMI and force bootstrap scripts to run again
AMI_LOAD=20260301 AMI_BOOTSTRAP=1 make gastown

# List AMIs matching gastown_* and exit without deploy
AMI_LIST=1 make gastown

# List AMIs and choose one interactively, then deploy
AMI_LIST=1 AMI_PICK=1 make gastown
```

Advanced behavior notes:
- `AMI_LOAD=<tag>` resolves AMI name `<environment>_<tag>` exactly and deploys with that AMI ID.
- `AMI_BOOTSTRAP=1` runs bootstrap userData even when deploying from a saved AMI (default is skip for restored AMIs).
- If requested AMI is missing, deploy fails before Spot request creation.
- `AMI_LIST=1` shows environment-scoped AMIs with ID/state/creation date for operator choice.
- `AMI_PICK=1` is only valid with `AMI_LIST=1`; invalid combinations fail fast.
- `AMI_LOAD` and `AMI_LIST` are mutually exclusive; invalid combinations fail fast.
- AMI list/load modes run an IAM preflight before deploy mutation steps and fail early with remediation if `ec2:DescribeImages` is missing.
- Without AMI options, deploy behavior remains unchanged and uses the default Ubuntu base image.

AMI naming convention and states:
- Use AMI names in the format `<environment>_<tag>` (for example `gastown_20260301`).
- Listed states come from EC2 image state (for example `pending`, `available`, `failed`).
- Deploy from a listed AMI should use an `available` image; `pending` images are still creating and may fail to launch.

Save-on-stop workflow:
- `AMI_SAVE=1` with `AMI_TAG=<tag>` saves AMI `<environment>_<tag>` from the current running workstation instance before destroy.
- If AMI creation fails or does not become `available` before timeout, destroy is aborted.

```bash
# Save current workstation as AMI gastown_20260302, then destroy stack
AMI_SAVE=1 AMI_TAG=20260302 make gastown ACTION=STOP

# Default stop behavior is unchanged when AMI_SAVE is not set
make gastown ACTION=STOP
```

Rollback to legacy behavior:
- Remove AMI lifecycle env vars from your shell/session:

```bash
unset AMI_LOAD AMI_LIST AMI_PICK
```

- Use the original commands:
  - Deploy: `make gastown`
  - Stop: `make gastown ACTION=STOP`

### Enter the tooling container

```bash
make aws
```

This opens a shell inside the Docker container with AWS/CDK tooling.

## Notes

- Region is read from `~/.aws/config` (active profile).
- Region/account can be overridden with options/environment variables (for example `CDK_DEFAULT_REGION`, `CDK_DEFAULT_ACCOUNT`, and `--region` where supported by scripts/commands).
- SSH is currently open on port 22 to anywhere (`0.0.0.0/0`); restrict this before broader use.
- Costs apply while infrastructure is running.

## Project Layout

- `Makefile` - primary entrypoints
- `docker-compose.yaml` - local container + AWS config mount + secrets wiring
- `aws/gastown/` - CDK app, stack, init scripts, and tests
- `aws/builder/` - CDK app, stack, init scripts, and tests
- `aws/workstation_core/` - shared package for cross-environment workstation contracts/helpers
  - includes canonical `EnvironmentSpec` model used to derive stack/logical naming consistently
- `aws/iam/gastown/` - IAM policy files

## Adding A New Environment From Shared Core

Use `aws/workstation_core` as the single source of truth and only keep environment-specific values in the environment module.

1. Create `<env>/environment_config.py` with one `ENVIRONMENT_SPEC` (`EnvironmentSpec`) instance.
2. Set the required per-environment knobs in that spec:
   - `environment_key` (for AMI naming and SSH alias)
   - `display_name` (for CloudFormation/construct naming)
   - `bootstrap_files`
   - `default_ami_selector`
   - `instance_type`, `volume_size`, `spot_price`
3. Keep naming derived from the spec properties instead of hardcoded literals:
   - Stack name: `ENVIRONMENT_SPEC.stack_name`
   - Spot Fleet logical id: `ENVIRONMENT_SPEC.spot_fleet_logical_id`
   - Saved AMI prefix: `ENVIRONMENT_SPEC.ami_prefix` (`<environment>_`)
4. Wire the target in `Makefile` using the shared scripts pattern used by `gastown`:
   - Start/deploy: `cd /home/user/<env> && uv run ../scripts/deploy_workstation.py --environment <env> --stack-dir /home/user/<env> --stack-name <DisplayName>WorkstationStack`
   - Stop/destroy: `cd /home/user/<env> && uv run ../scripts/stop_workstation.py --environment <env> --stack-dir /home/user/<env> --stack-name <DisplayName>WorkstationStack`
5. Validate AMI lifecycle behavior for the new environment:
   - List only: `AMI_LIST=1 make <env>`
   - Load exact AMI name: `AMI_LOAD=20260301 make <env>` (resolves `<env>_20260301`)
   - List + pick: `AMI_LIST=1 AMI_PICK=1 make <env>`
   - Save on stop: `AMI_SAVE=1 AMI_TAG=20260302 make <env> ACTION=STOP`
   - Legacy/default deploy (no AMI flags): `make <env>`

IAM note:
- AMI list/load flows require `ec2:DescribeImages`.
- Save-on-stop requires permissions used by `create_image` and AMI state checks in `aws/workstation_core/ami_lifecycle.py`.

Rollback path:
- Unset AMI flags and run normal commands:
  - `unset AMI_LOAD AMI_LIST AMI_PICK AMI_SAVE AMI_TAG`
  - `make <env>`
  - `make <env> ACTION=STOP`
