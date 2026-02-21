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

### Stop/destroy `gastown` environment

```bash
make gastown ACTION=STOP
```

This destroys the deployed stack and stops billing for the workstation resources.

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
