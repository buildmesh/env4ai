# EC2 AI Dev Environments

This repository helps developers spin up reproducible EC2 workstations for AI tooling.

## Available Environments

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

Run `make` to open the interactive workstation lifecycle menu. The menu auto-discovers available environments from modules under `aws/`.

### Interactive Menu

| Action | What it does |
|--------|--------------|
| **Deploy with default AMI** | Provisions a new EC2 workstation using the environment's standard base image |
| **Deploy with AMI list + pick** | Lists your saved AMIs for this environment, lets you choose one, then deploys |
| **Save current state as AMI** | Snapshots your running workstation to a named AMI for later restore |
| **Destroy stack** | Tears down the running workstation and all associated resources |
| **Destroy stack + save AMI first** | Saves an AMI snapshot, then destroys — preserves state before shutting down |
| **Refresh status** | Re-checks live stack status from AWS |
| **Switch environment** | Changes the active environment (e.g. from `gastown` to `builder`) |
| **Quit** | Exits the menu |

AMI names use the format `<environment>_<tag>` (for example `gastown_20260301`). Menu actions are gated by current stack state — deploy is disabled when a stack is already running, and save/destroy are disabled when no stack exists. Destructive actions require explicit confirmation.

> **Note:** AWS creates `aws-ec2-spot-fleet-tagging-role` automatically the first time Spot Fleet needs it.

Bootstrap script lookup order:
- `aws/<environment>/init/<script>`
- `aws/common/init/<script>`

If the same script exists in both places, the environment-local copy wins and deploy output prints a collision message showing which file was used.

---

## Advanced: Non-Interactive Workflows

The `make` targets and environment variables below provide the same operations as the interactive menu — useful for scripting or when you prefer to skip the menu.

### Direct targets

```bash
# Deploy
make gastown
make builder

# Destroy
make gastown ACTION=STOP
make builder ACTION=STOP
```

### AMI lifecycle

| Interactive step | Equivalent command |
|-----------------|--------------------|
| Deploy with default AMI | `make gastown` |
| Deploy from a specific saved AMI | `AMI_LOAD=20260301 make gastown` |
| Deploy with AMI list + pick | `AMI_LIST=1 AMI_PICK=1 make gastown` |
| List saved AMIs only (no deploy) | `AMI_LIST=1 make gastown` |
| Destroy stack + save AMI first | `AMI_SAVE=1 AMI_TAG=20260302 make gastown ACTION=STOP` |

Run bootstrap scripts even when deploying from a saved AMI:

```bash
AMI_LOAD=20260301 AMI_BOOTSTRAP=1 make gastown
```

**Behavior notes:**
- `AMI_LOAD` and `AMI_LIST` are mutually exclusive; invalid combinations fail fast.
- `AMI_PICK=1` is only valid with `AMI_LIST=1`.
- AMI list/load modes run an IAM preflight and fail early with remediation if `ec2:DescribeImages` is missing.
- If the requested AMI is missing, deploy fails before the Spot request is created.
- If AMI creation fails or does not become `available` before timeout, destroy is aborted.

To clear AMI flags and return to default behavior:

```bash
unset AMI_LOAD AMI_LIST AMI_PICK AMI_SAVE AMI_TAG
```

### Enter the tooling container

To open a shell inside the Docker container with AWS/CDK tooling directly:

```bash
make aws
```

To print where each bootstrap script resolves during `cdk deploy`, pass:

```bash
cdk deploy -c verbose_bootstrap_resolution=true
```

---

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
- `aws/common/init/` - shared bootstrap scripts reused across environments
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
