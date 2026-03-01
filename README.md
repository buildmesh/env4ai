# EC2 AI Dev Environments

This repository helps developers spin up reproducible EC2 workstations for AI tooling.

Current environment:
- `gastown`: [Gas Town](https://github.com/steveyegge/gastown), preconfigured with dependencies so it is usable out of the box.

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

### Start `gastown` environment

```bash
make gastown
```

This deploys the CDK stack, creates/starts the EC2 workstation, and prints SSH config instructions.

After applying the SSH config update instructions, run:

```bash
ssh gastown-workstation
```

Note: AWS creates `aws-ec2-spot-fleet-tagging-role` automatically the first time Spot Fleet needs it.

Optional AMI lifecycle controls are available through environment variables:

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

Behavior:
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
- There is currently no `AMI_SAVE`/`AMI_TAG` Make variable in this repo.
- To preserve the current workstation before destroy, create and wait for an AMI manually, then run stop:

```bash
# Example: create a named AMI from your current workstation instance
aws ec2 create-image \
  --instance-id <instance-id> \
  --name gastown_20260301 \
  --no-reboot

# Wait until the image is usable before destroy
aws ec2 wait image-available --image-ids <ami-id>

# Then destroy the stack
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

### Stop/destroy `gastown` environment

```bash
make gastown ACTION=STOP
```

This destroys the deployed stack and stops billing for the workstation resources.

Save-on-stop note:
- Current `ACTION=STOP` flow does not accept an AMI save variable in this repository state.
- To preserve instance state as an AMI, create the image manually before stop, then deploy later with `AMI_LOAD=<tag>`.

### Enter the tooling container

```bash
make
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
- `aws/iam/gastown/` - IAM policy files
