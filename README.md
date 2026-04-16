# EC2 AI Dev Environments

This repository helps developers spin up reproducible EC2 workstations for AI tooling.

## Shared Network Model

All workstation environments now deploy into one shared VPC and one shared Internet Gateway owned by `Env4aiNetworkStack`.

- Environment deploy automatically deploys or updates `Env4aiNetworkStack` first.
- Environment destroy removes only the selected workstation stack and leaves the shared network intact.
- Shared-network teardown is a separate operator command and is blocked while any workstation stacks still exist.

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

   `aws/iam/deployer-policy.json`

2. For the very first env4ai run in an AWS account, also create a second customer-managed IAM policy using:

   `aws/iam/first-run-bootstrap-policy.json`

3. Attach `deployer-policy.json` to the IAM user used by your local AWS `default` profile.

4. Attach `first-run-bootstrap-policy.json` to that same IAM user temporarily, only for the first-run Spot Fleet bootstrap described below.

5. If you will use `ACCESS_MODE=ssh` or `ACCESS_MODE=both`, create an EC2 key pair in **AWS Management Console > EC2 > Network & Security > Key Pairs**:
   - Name: `aws_key`
   - Download the private key and place it at:

     `~/.ssh/aws_key.pem`

6. Create the account-id secret file (default source for AWS account):

   ```bash
   mkdir -p secrets
   echo "<YOUR_AWS_ACCOUNT_ID>" > secrets/aws_acct
   ```

   By default this is mounted as Docker secret `aws_acct` at `/run/secrets/aws_acct`. You can override account resolution using options/environment variables (for example `CDK_DEFAULT_ACCOUNT`).

### First-Run Spot Fleet Bootstrap

env4ai deploys Spot Fleet through CDK and the AWS API. In that path, you should not assume AWS will create the required Spot roles for you during a normal deploy.

Before the first successful `make <environment>` run in a new AWS account:

1. Temporarily attach `aws/iam/first-run-bootstrap-policy.json` to the IAM user that will run env4ai.
2. Create the Spot service-linked roles once:

   ```bash
   aws iam create-service-linked-role --aws-service-name spot.amazonaws.com
   aws iam create-service-linked-role --aws-service-name spotfleet.amazonaws.com
   ```

3. Create the Spot Fleet tagging role once:

   ```bash
   aws iam create-role \
     --role-name aws-ec2-spot-fleet-tagging-role \
     --assume-role-policy-document '{
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Principal": {
             "Service": "spotfleet.amazonaws.com"
           },
           "Action": "sts:AssumeRole"
         }
       ]
     }'

   aws iam attach-role-policy \
     --role-name aws-ec2-spot-fleet-tagging-role \
     --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole
   ```

4. Run your first deploy.
5. After the first deploy succeeds, detach `aws/iam/first-run-bootstrap-policy.json` from the IAM user. Keep `aws/iam/deployer-policy.json` attached for normal env4ai use.

## Usage

Run `make` to open the interactive workstation lifecycle menu. The menu auto-discovers available environments from modules under `aws/`.

### Interactive Menu

| Action | What it does |
|--------|--------------|
| **Deploy with default AMI** | Provisions a new EC2 workstation using the environment's standard base image |
| **Deploy with AMI list + pick** | Lists your saved AMIs for this environment, lets you choose one, then deploys |
| **Save current state as AMI** | Snapshots your running workstation to a named AMI for later restore |
| **Destroy stack** | Tears down the running workstation resources while leaving the shared network intact |
| **Destroy stack + save AMI first** | Saves an AMI snapshot, then destroys — preserves state before shutting down |
| **Refresh status** | Re-checks live stack status from AWS |
| **Switch environment** | Changes the active environment (e.g. from `gastown` to `builder`) |
| **Quit** | Exits the menu |

AMI names use the format `<environment>_<tag>` (for example `gastown_20260301`). Menu actions are gated by current stack state — deploy is disabled when a stack is already running, and save/destroy are disabled when no stack exists. Destructive actions require explicit confirmation.

> **Note:** env4ai’s deploy path uses CDK/API-based Spot Fleet provisioning. Complete the one-time Spot Fleet bootstrap in [First-Run Spot Fleet Bootstrap](#first-run-spot-fleet-bootstrap) before the first deploy in a new AWS account.

### Access Modes

Use `ACCESS_MODE` to choose how a workstation is reached at deploy time:

- `ACCESS_MODE=ssh` keeps the existing behavior: SSH ingress from the internet, the EC2 key pair requirement, and SSH config guidance after deploy.
- `ACCESS_MODE=ssm` attaches the shared SSM instance profile and SSM client security group, does not open inbound SSH, does not require the EC2 key pair, and prints an `aws ssm start-session` command after deploy.
- `ACCESS_MODE=both` keeps SSH enabled and also attaches the shared SSM resources so the workstation can be reached through either method.

Examples:

```bash
make gastown ACCESS_MODE=ssh
make gastown ACCESS_MODE=ssm
make gastown ACCESS_MODE=both
```

If you use `ACCESS_MODE=ssm` or `ACCESS_MODE=both`, install the AWS Session Manager plugin on the machine where you will run `aws ssm start-session`.

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
make gastown ACCESS_MODE=ssm
make gastown ACCESS_MODE=both

# Destroy
make gastown ACTION=STOP
make builder ACTION=STOP

# Destroy shared network after all workstation stacks are gone
make shared-network-destroy
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
- Every deploy ensures `Env4aiNetworkStack` exists before the environment stack is deployed.
- `ACCESS_MODE` defaults to `ssh` unless an environment overrides `default_access_mode`.
- `ACCESS_MODE=ssm` omits SSH ingress and the EC2 key pair from the workstation launch.
- `ACCESS_MODE=both` keeps SSH enabled and also attaches the shared SSM role/profile and SSM client security group.
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
- The shared `env4ai` VPC uses `10.0.0.0/16`; each environment must define a unique `subnet_cidr` inside that range.
- `Env4aiNetworkStack` now also owns the shared Systems Manager interface endpoints, SSM security groups, and the EC2 instance role/profile used for Session Manager access.
- `ACCESS_MODE=ssh` and `ACCESS_MODE=both` keep SSH open on port 22 to anywhere (`0.0.0.0/0`); `ACCESS_MODE=ssm` avoids public SSH ingress.
- Costs apply while infrastructure is running.

## Project Layout

- `Makefile` - primary entrypoints
- `docker-compose.yaml` - local container + AWS config mount + secrets wiring
- `aws/gastown/` - CDK app, stack, init scripts, and tests
- `aws/builder/` - CDK app, stack, init scripts, and tests
- `aws/common/init/` - shared bootstrap scripts reused across environments
- `aws/scripts/destroy_shared_network.py` - explicit shared-network teardown command with preflight checks
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
   - `subnet_cidr` (unique subnet inside the shared `10.0.0.0/16` VPC)
   - `instance_type`, `volume_size`, `spot_price`
3. Keep naming derived from the spec properties instead of hardcoded literals:
   - Stack name: `ENVIRONMENT_SPEC.stack_name`
   - Spot Fleet logical id: `ENVIRONMENT_SPEC.spot_fleet_logical_id`
   - Saved AMI prefix: `ENVIRONMENT_SPEC.ami_prefix` (`<environment>_`)
4. Wire the target in `Makefile` using the shared scripts pattern used by `gastown`:
   - Start/deploy: `cd /home/user/<env> && uv run ../scripts/deploy_workstation.py --environment <env> --stack-dir /home/user/<env> --stack-name <DisplayName>WorkstationStack`
   - Stop/destroy: `cd /home/user/<env> && uv run ../scripts/stop_workstation.py --environment <env> --stack-dir /home/user/<env> --stack-name <DisplayName>WorkstationStack`
   - Shared-network destroy: `cd /home/user/gastown && uv run ../scripts/destroy_shared_network.py`
5. Validate AMI lifecycle behavior for the new environment:
   - List only: `AMI_LIST=1 make <env>`
   - Load exact AMI name: `AMI_LOAD=20260301 make <env>` (resolves `<env>_20260301`)
   - List + pick: `AMI_LIST=1 AMI_PICK=1 make <env>`
   - Save on stop: `AMI_SAVE=1 AMI_TAG=20260302 make <env> ACTION=STOP`
   - Legacy/default deploy (no AMI flags): `make <env>`

IAM note:
- AMI list/load flows require `ec2:DescribeImages`.
- Save-on-stop requires permissions used by `create_image` and AMI state checks in `aws/workstation_core/ami_lifecycle.py`.
